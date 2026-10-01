from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import api_server  # 조립 루트. 속성은 호출 시점에 조회하므로 테스트의 monkeypatch 가 그대로 반영된다.
from app.api.deps import get_current_user
from app.core.constants import BRIEFING_QUERY
from app.db.models import User
from app.db.repositories import ChatRepository
from app.db.session import get_db
from app.schemas.chat import ChatRequest

router = APIRouter()


@router.get("/api/web/history")
def get_web_chat_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 현재 로그인한 유저(이메일)의 최근 대화 기록 50개를 오래된 순으로 가져옵니다.
    history_records = ChatRepository(db).recent_for_user(current_user.email, limit=50)

    chat_history = []
    for record in history_records:
        # 1. 유저가 보낸 질문
        if record.query and record.query != BRIEFING_QUERY:
            chat_history.append({
                "message": record.query,
                "sender": "user",
                "direction": "outgoing"
            })

        # 2. 단비가 보낸 답변 (브리핑 포함)
        if record.answer:
            chat_history.append({
                "message": record.answer,
                "sender": "Danbi",
                "direction": "incoming"
            })

    return {"history": chat_history}


@router.post("/api/web/chat")
def web_chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_user)):
    # 🔒 JWT 토큰이 검증된 사람만 여기까지 들어올 수 있음
    # 파라미터로 구글 이메일(current_user.email)을 넘겨 DB에 기록되게 합니다.
    answer, category = api_server.chat_service.respond(request.query, request.history, current_user.email)

    return {
        "answer": answer,
        "category": category
    }
