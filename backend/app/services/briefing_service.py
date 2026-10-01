"""모닝 브리핑: 최신 공지를 요약해 모든 사용자의 대화 기록에 추가한다."""
from typing import Callable

from loguru import logger

from app.core.constants import BRIEFING_CONTEXT, BRIEFING_QUERY
from app.crawlers.boards import BRIEFING_BOARD
from app.db.repositories import ChatRepository, UserRepository
from app.db.session import session_scope
from app.rag.llm import extract_text
from app.rag.prompts import build_briefing_message, build_briefing_prompt


class BriefingService:
    def __init__(self, *, llm, fetch_notice: Callable[[str], str], board_name: str = BRIEFING_BOARD):
        self._llm = llm
        self._fetch_notice = fetch_notice
        self._board_name = board_name

    def deliver(self) -> int:
        """브리핑을 전송하고 받은 사용자 수를 반환한다. 실패하면 아무것도 저장하지 않고 0 을 반환한다."""
        logger.info("⏰ [스케줄러] 아침 브리핑을 유저들의 채팅방에 전송합니다...")
        try:
            # 크롤링 실패는 예외로 올라오므로, 오류 문구가 요약되어 전 사용자에게 저장되는 일이 없다.
            notice_text = self._fetch_notice(self._board_name)
            summary = extract_text(self._llm.invoke(build_briefing_prompt(notice_text)))
            message = build_briefing_message(summary)

            with session_scope() as db:
                users = UserRepository(db).list_all()
                chat_repo = ChatRepository(db)
                for user in users:
                    # 웹 채팅과 동일하게 email 을 user_id 로 사용한다.
                    chat_repo.add(
                        user_id=user.email,
                        query=BRIEFING_QUERY,  # 유저가 보낸 게 아니라는 표시
                        answer=message,
                        category="notice",
                        retrieved_context=BRIEFING_CONTEXT,
                        step1_time=0.0,
                        step2_time=0.0,
                        step3_time=0.0,
                        total_time=0.0,
                    )
                count = len(users)
            logger.info(f"✅ {count}명의 유저에게 브리핑 전송 완료!")
            return count
        except Exception as e:
            logger.error(f"❌ 브리핑 전송 에러: {e}")
            return 0
