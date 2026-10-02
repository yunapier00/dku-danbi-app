"""AuthService 단위 테스트. state 토큰 발급/검증, 도메인 검사 헬퍼(현재는 호출부에서 주석 처리됨)."""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import Settings
from app.services.auth_service import AuthService, is_dankook_email


@pytest.fixture
def settings():
    return Settings(
        database_url="sqlite:///:memory:",
        chroma_db_path=".",
        google_client_id="cid",
        google_client_secret="secret",
        google_redirect_uri="http://testserver/api/auth/callback",
        jwt_secret_key="unit-test-secret",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        frontend_url="http://front.test",
        cors_origins=[],
        kakao_daily_limit=3,
        crawler_verify_ssl=True,
        menu_cache_ttl_seconds=0,
        notice_cache_ttl_seconds=0,
        kakao_webhook_secret=None,
        chrome_binary_path=None,
        chromedriver_path=None,
    )


@pytest.fixture
def auth_service(settings):
    return AuthService(settings)


# ---------------------------------------------------------------- is_dankook_email
@pytest.mark.parametrize(
    "email, expected",
    [
        ("student@dankook.ac.kr", True),
        ("STUDENT@DANKOOK.AC.KR", True),
        ("student@gmail.com", False),
        ("notdankook.ac.kr", False),
        ("", False),
        (None, False),
    ],
)
def test_is_dankook_email(email, expected):
    assert is_dankook_email(email) is expected


# ---------------------------------------------------------------- state 발급/검증
def test_build_login_url_contains_client_settings_and_state(auth_service):
    from urllib.parse import parse_qs, urlparse

    params = parse_qs(urlparse(auth_service.build_login_url()).query)

    assert params["client_id"] == ["cid"]
    assert params["redirect_uri"] == ["http://testserver/api/auth/callback"]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert auth_service.verify_state(params["state"][0])


def test_verify_state_rejects_garbage(auth_service):
    assert auth_service.verify_state("") is False
    assert auth_service.verify_state("not-a-jwt") is False


def test_verify_state_rejects_token_signed_with_different_secret(settings):
    other = AuthService(Settings(**{**settings.__dict__, "jwt_secret_key": "a-different-secret"}))
    state = other.build_login_url()
    from urllib.parse import parse_qs, urlparse

    stolen_state = parse_qs(urlparse(state).query)["state"][0]

    assert AuthService(settings).verify_state(stolen_state) is False


def test_verify_state_rejects_expired_token(settings, auth_service):
    expired = jwt.encode(
        {"typ": "state", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert auth_service.verify_state(expired) is False


def test_verify_state_rejects_a_token_without_the_state_type(settings, auth_service):
    """state 와 같은 비밀키로 서명된 다른 종류의 토큰(예: 로그인 세션 토큰)은 typ 클레임으로 구분해 거부한다."""
    access_token = jwt.encode(
        {"sub": "student@dankook.ac.kr", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert auth_service.verify_state(access_token) is False


def test_each_issued_state_is_unique(auth_service):
    from urllib.parse import parse_qs, urlparse

    def state_of(url):
        return parse_qs(urlparse(url).query)["state"][0]

    assert state_of(auth_service.build_login_url()) != state_of(auth_service.build_login_url())
