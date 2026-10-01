from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from loguru import logger

import api_server  # 조립 루트. 속성은 호출 시점에 조회하므로 테스트의 monkeypatch 가 그대로 반영된다.
from app.core.config import get_settings
from app.core.timeutil import today_kst
from app.db.repositories import ChatRepository
from app.db.session import session_scope
from app.services.kakao_service import KAKAO_SECRET_HEADER, is_authorized_webhook, kakao_text_response

router = APIRouter()


@router.post("/api/kakao")
async def kakao_chat(
    request: Request,
    background_tasks: BackgroundTasks,
    x_danbi_kakao_secret: Optional[str] = Header(default=None, alias=KAKAO_SECRET_HEADER),
):
    settings = get_settings()

    # 0. 카카오 오픈빌더가 보낸 요청인지 확인 (KAKAO_WEBHOOK_SECRET 미설정 시 건너뜀 - 기존 배포 호환)
    if not is_authorized_webhook(x_danbi_kakao_secret, settings.kakao_webhook_secret):
        logger.warning("❌ 카카오 웹훅 요청의 서명이 올바르지 않습니다.")
        raise HTTPException(status_code=401, detail="유효하지 않은 요청입니다.")

    try:
        body = await request.json()

        user_message = body["userRequest"]["utterance"]
        user_id = body["userRequest"]["user"]["id"]

        # 1. 오늘(KST) 날짜 기준으로 해당 유저의 질문 횟수를 카운트
        with session_scope() as db:
            daily_count = ChatRepository(db).count_for_user_on(user_id, today_kst())

        # 2. 제한 횟수를 초과했는지 검사
        if daily_count >= settings.kakao_daily_limit:
            return kakao_text_response(f"하루 질문 한도 {settings.kakao_daily_limit}회 초과\n내일 다시 찾아와주세요!")

        # 3. 통과했다면 콜백 처리를 진행
        callback_url = body["userRequest"].get("callbackUrl")

        if callback_url:
            background_tasks.add_task(api_server.process_and_send_callback, user_message, callback_url, user_id)
            return {"useCallback": True}

        return kakao_text_response("콜백 URL 에러 ")

    except Exception as e:
        logger.error(f"❌ 카카오 API 수신 에러: {e}")
        return {"useCallback": False}
