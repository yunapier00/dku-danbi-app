from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ChatHistory


class ChatRepository:
    """ChatHistory 테이블 접근. commit 은 호출하는 쪽(session_scope)이 책임진다."""

    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        *,
        user_id: str,
        query: str,
        answer: str,
        category: str,
        retrieved_context: Optional[str] = None,
        step1_time: Optional[float] = None,
        step2_time: Optional[float] = None,
        step3_time: Optional[float] = None,
        total_time: Optional[float] = None,
    ) -> ChatHistory:
        record = ChatHistory(
            user_id=user_id,
            query=query,
            answer=answer,
            category=category,
            retrieved_context=retrieved_context,
            step1_time=step1_time,
            step2_time=step2_time,
            step3_time=step3_time,
            total_time=total_time,
        )
        self.db.add(record)
        return record

    def recent_for_user(self, user_id: str, limit: int = 50) -> List[ChatHistory]:
        """해당 유저의 최근 기록 `limit`개를 오래된 순으로 반환한다."""
        records = (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        records.reverse()
        return records

    def count_for_user_on(self, user_id: str, day: date) -> int:
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id, func.date(ChatHistory.created_at) == day)
            .count()
        )
