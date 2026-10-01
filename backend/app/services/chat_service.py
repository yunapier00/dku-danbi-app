"""질문 하나를 처리하는 유스케이스: 의도 분류 → 컨텍스트 수집(검색/크롤링) → 답변 생성 → 기록 저장."""
import time
from datetime import date
from typing import Callable, Tuple

from loguru import logger

from app.core.timeutil import today_kst
from app.crawlers.boards import resolve_board
from app.db.repositories import ChatRepository
from app.db.session import session_scope
from app.rag import intent
from app.rag.answer import generate_answer
from app.rag.context import (
    MENU_FAILURE_CONTEXT,
    NOTICE_FAILURE_CONTEXT,
    format_documents,
    format_menu_context,
    format_notice_context,
)


class ChatService:
    def __init__(
        self,
        *,
        llm,
        retriever,
        fetch_menu: Callable[[], str],
        fetch_notice: Callable[[str], str],
        timer: Callable[[], float] = time.perf_counter,
        today: Callable[[], date] = today_kst,
    ):
        self._llm = llm
        self._retriever = retriever
        self._fetch_menu = fetch_menu
        self._fetch_notice = fetch_notice
        self._timer = timer
        self._today = today

    def respond(self, query: str, history: str, user_id: str) -> Tuple[str, str]:
        """(답변, 카테고리) 를 반환하고 대화 기록을 저장한다."""
        timer = self._timer
        total_start = timer()

        step1_start = timer()
        category = intent.classify_intent(query)
        step1_time = timer() - step1_start

        step2_start = timer()
        context_text = self._collect_context(category, query)
        step2_time = timer() - step2_start

        step3_start = timer()
        answer = generate_answer(self._llm, context_text, query, history)
        step3_time = timer() - step3_start
        total_time = timer() - total_start

        self._save(
            user_id=user_id,
            query=query,
            answer=answer,
            category=category,
            context_text=context_text,
            timings=(step1_time, step2_time, step3_time, total_time),
        )
        return answer, category

    def _collect_context(self, category: str, query: str) -> str:
        if category == intent.MENU:
            try:
                return format_menu_context(self._fetch_menu(), self._today())
            except Exception as e:
                logger.error(f"❌ 학식 크롤링 에러 원인: {e}")
                return MENU_FAILURE_CONTEXT

        if category == intent.NOTICE:
            board_name = resolve_board(query)
            try:
                return format_notice_context(board_name, self._fetch_notice(board_name))
            except Exception as e:
                logger.error(f"❌ 크롤링 에러: {e}")
                return NOTICE_FAILURE_CONTEXT

        return format_documents(self._retriever.retrieve(query))

    def _save(self, *, user_id, query, answer, category, context_text, timings) -> None:
        """기록 저장 실패는 답변 반환을 막지 않는다. 롤백은 session_scope 가 처리한다."""
        step1, step2, step3, total = timings
        try:
            with session_scope() as db:
                ChatRepository(db).add(
                    user_id=user_id,
                    query=query,
                    answer=answer,
                    category=category,
                    retrieved_context=context_text,
                    step1_time=round(step1, 2),
                    step2_time=round(step2, 2),
                    step3_time=round(step3, 2),
                    total_time=round(total, 2),
                )
        except Exception as e:
            logger.error(f"❌ DB 저장 트랜잭션 실패 및 롤백됨: {e}")
