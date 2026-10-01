"""Google OAuth 로그인 플로우: 인증 URL 생성, 코드 교환, 사용자 upsert, JWT 발급."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.core.config import Settings
from app.db.repositories import UserRepository
from app.db.session import session_scope

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
STATE_TTL_SECONDS = 300
STATE_TYPE = "state"  # state 토큰과 로그인 세션 토큰을 서로 바꿔 쓰지 못하게 구분하는 표시


class GoogleAuthError(Exception):
    """구글 토큰 교환/사용자 정보 조회 실패. 메시지는 사용자에게 그대로 노출해도 되는 문구만 담는다."""


class DomainNotAllowedError(Exception):
    """허용되지 않은 이메일 도메인. AuthService.complete_login 의 검사가 주석 처리되어 있어 현재는 발생하지 않는다."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"허용되지 않은 이메일입니다: {email}")


def is_dankook_email(email: str) -> bool:
    """단국대학교 이메일 주소인지 확인한다. 도메인 제한을 켤 때 쓸 수 있도록 구현해 두었다 (기본은 비활성)."""
    return bool(email) and email.lower().endswith("@dankook.ac.kr")


class AuthService:
    def __init__(self, settings: Settings):
        self._settings = settings

    # ---- 로그인 시작 ----
    def build_login_url(self) -> str:
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": self._issue_state(),
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def _issue_state(self) -> str:
        """로그인 CSRF 방지용 state. 서버에 아무것도 저장하지 않고, 서명된 토큰 자체로 검증한다(짧은 TTL)."""
        expire = datetime.now(timezone.utc) + timedelta(seconds=STATE_TTL_SECONDS)
        payload = {"typ": STATE_TYPE, "nonce": secrets.token_urlsafe(16), "exp": expire}
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def verify_state(self, state: str) -> bool:
        if not state:
            return False
        try:
            payload = jwt.decode(state, self._settings.jwt_secret_key, algorithms=[self._settings.jwt_algorithm])
        except JWTError:
            return False
        return payload.get("typ") == STATE_TYPE

    # ---- 콜백 처리 ----
    async def complete_login(self, code: str) -> str:
        """구글 인가 코드를 우리 서버 JWT로 교환한다. 처음 로그인하는 유저는 가입시킨다."""
        async with httpx.AsyncClient() as client:
            access_token = await self._exchange_code(client, code)
            if not access_token:
                raise GoogleAuthError("Google 인증 실패")
            email, name = await self._fetch_profile(client, access_token)

        if not email:
            raise GoogleAuthError("Google 인증 실패")

        # 🛡️ 단국대 학생 방어막 (외부인 차단 로직)
        # 필요 시 아래 두 줄의 주석을 해제하세요. is_dankook_email() 은 구현되어 테스트도 되어 있습니다.
        # if not is_dankook_email(email):
        #     raise DomainNotAllowedError(email)

        self._upsert_user(email, name)
        return self._issue_access_token(email)

    async def _exchange_code(self, client: httpx.AsyncClient, code: str) -> Optional[str]:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self._settings.google_client_id,
                "client_secret": self._settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self._settings.google_redirect_uri,
            },
        )
        return response.json().get("access_token")

    async def _fetch_profile(self, client: httpx.AsyncClient, access_token: str) -> Tuple[Optional[str], Optional[str]]:
        response = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        info = response.json()
        return info.get("email"), info.get("name")

    def _upsert_user(self, email: str, name: Optional[str]) -> None:
        with session_scope() as db:
            repo = UserRepository(db)
            if repo.get_by_email(email) is None:
                repo.add(email=email, name=name)

    def _issue_access_token(self, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._settings.access_token_expire_minutes)
        return jwt.encode(
            {"sub": email, "exp": expire}, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm
        )
