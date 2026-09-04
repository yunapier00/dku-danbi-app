from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone

# SQLite 파일 경로
SQLALCHEMY_DATABASE_URL = "sqlite:////app/data/danbi_chat.db"

# SQLite 사용 시 스레드 설정
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 한국 표준시(KST)를 반환하는 헬퍼 함수
def get_kst_now():
    return datetime.now(timezone.utc) + timedelta(hours=9)

# 대화 기록 테이블 정의
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    
    # 잦은 조회가 발생하는 user_id에 index=True 추가 (Rate Limit 쿼리 최적화)
    user_id = Column(String, index=True) 
    
    query = Column(Text)
    answer = Column(Text)
    category = Column(String)
    
    # UTC 대신 KST를 기본값으로 설정하고, 날짜 기반 조회를 위해 index=True 추가
    created_at = Column(DateTime, default=get_kst_now, index=True)

    retrieved_context = Column(Text, nullable=True) # 가져온 문서 내용
    step1_time = Column(Float, nullable=True)       # 의도 파악 소요 시간
    step2_time = Column(Float, nullable=True)       # DB 검색/크롤링 소요 시간
    step3_time = Column(Float, nullable=True)       # 답변 생성 소요 시간
    total_time = Column(Float, nullable=True)       # 전체 소요 시간



class User(Base):
    __tablename__ = "users"

    # 고유 식별 번호 (1, 2, 3...)
    id = Column(Integer, primary_key=True, index=True)
    
    # 구글 로그인에서 받아올 핵심 정보 (이메일로 유저 식별)
    # unique=True: 중복 가입 방지, nullable=False: 필수 값
    email = Column(String, unique=True, index=True, nullable=False) 
    
    # 유저의 이름 (선택 사항)
    name = Column(String, nullable=True)
    
    # 가입일 (한국 시간 기준)
    created_at = Column(DateTime, default=get_kst_now)

# 테이블 생성
Base.metadata.create_all(bind=engine)