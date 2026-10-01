"""엔진 / 세션 관리.

엔진은 import 시점이 아니라 첫 사용 시점에 만든다(지연 초기화). 그래야 테스트처럼 DATABASE_URL 환경변수를
먼저 설정한 뒤 이 모듈이 쓰이는 순서를 꼭 지키지 않아도, 단순히 이 모듈을 import(다른 모듈 경유 포함)하는 것만으로
잘못된(기본) DB에 엔진이 고정되는 일이 없다.

- get_db: FastAPI 요청 단위 세션 (Depends 용)
- session_scope: 요청 밖(스케줄러, 서비스)에서 쓰는 트랜잭션 단위. 정상 종료 시 commit, 예외 시 rollback 후 재발생.
"""
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def _ensure_initialized() -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    database_url = get_settings().database_url
    # check_same_thread 는 SQLite 전용 옵션이다.
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=connect_args)
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def __getattr__(name: str):
    # `from app.db.session import engine` 형태의 접근을 지연 초기화로 지원한다 (PEP 562).
    if name == "engine":
        _ensure_initialized()
        return _engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def SessionLocal() -> Session:
    """새 세션을 하나 연다. 기존 코드와의 호환을 위해 sessionmaker 처럼 `SessionLocal()` 로 호출한다."""
    _ensure_initialized()
    return _session_factory()


def init_db() -> None:
    """모델에 정의된 테이블을 생성한다. 앱 시작 시(lifespan) 한 번 호출한다."""
    from app.db import models  # noqa: F401  (테이블 등록)

    _ensure_initialized()
    Base.metadata.create_all(bind=_engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
