from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.core.timeutil import get_kst_now
from app.db.base import Base


class ChatHistory(Base):
    """대화 기록. user_id는 웹은 이메일, 카카오는 카카오 사용자 ID가 들어간다."""

    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)

    # 잦은 조회가 발생하는 user_id에 index=True (Rate Limit 쿼리 최적화)
    user_id = Column(String, index=True)

    query = Column(Text)
    answer = Column(Text)
    category = Column(String)

    # KST를 기본값으로 설정하고, 날짜 기반 조회를 위해 index=True
    created_at = Column(DateTime, default=get_kst_now, index=True)

    retrieved_context = Column(Text, nullable=True)  # 가져온 문서 내용
    step1_time = Column(Float, nullable=True)        # 의도 파악 소요 시간
    step2_time = Column(Float, nullable=True)        # DB 검색/크롤링 소요 시간
    step3_time = Column(Float, nullable=True)        # 답변 생성 소요 시간
    total_time = Column(Float, nullable=True)        # 전체 소요 시간


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # 구글 로그인에서 받아온 이메일로 유저를 식별한다.
    email = Column(String, unique=True, index=True, nullable=False)

    name = Column(String, nullable=True)

    created_at = Column(DateTime, default=get_kst_now)
