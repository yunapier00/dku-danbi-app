from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

import api_server  # 조립 루트. 속성은 호출 시점에 조회하므로 테스트의 monkeypatch 가 그대로 반영된다.
from app.core.config import get_settings
from app.services.auth_service import DomainNotAllowedError, GoogleAuthError

router = APIRouter()


@router.get("/api/auth/login")
def login_via_google():
    return RedirectResponse(url=api_server.auth_service.build_login_url())


@router.get("/api/auth/callback")
async def google_callback(code: str, state: str = ""):
    settings = get_settings()
    auth_service = api_server.auth_service

    # 로그인 CSRF 방지: /api/auth/login 이 발급한 state 와 일치(서명·만료 검증)하지 않으면 거부한다.
    if not auth_service.verify_state(state):
        raise HTTPException(status_code=400, detail="유효하지 않은 로그인 요청입니다. 다시 로그인해주세요.")

    try:
        token = await auth_service.complete_login(code)
    except GoogleAuthError:
        raise HTTPException(status_code=400, detail="Google 인증 실패")
    except DomainNotAllowedError:
        return RedirectResponse(url=f"{settings.frontend_url}/?error=invalid_domain")

    return RedirectResponse(url=f"{settings.frontend_url}/?token={token}")
