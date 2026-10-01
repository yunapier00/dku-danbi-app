"""특성화 테스트 공통 픽스처.

리팩토링 전/후로 '현재 동작'이 유지되는지 확인하는 것이 목적이다.
외부 서비스(Gemini, Google OAuth, 실제 크롤링 대상)는 모두 가짜로 대체한다.
"""
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402,F401  (엔진을 만들지 않는 모듈만 최상단에서 import)
from app.db.models import ChatHistory, User  # noqa: E402


def new_session():
    """현재 app.db.session.SessionLocal 로 새 세션을 연다.

    app.db.session 은 import 시점에 DATABASE_URL 로 엔진을 만들기 때문에 최상단에서 import하면 안 된다.
    """
    from app.db.session import SessionLocal

    return SessionLocal()


@pytest.fixture(scope="session")
def api(tmp_path_factory):
    """api_server 모듈을 격리된 작업 디렉터리에서 한 번만 import한다.

    - Chroma DB는 열기만 해도 파일이 바뀔 수 있으므로 임시 디렉터리로 복사한다.
    - SQLite는 임시 파일을 쓰고, 로그(logs/)도 임시 디렉터리에 쌓인다.
    """
    work = tmp_path_factory.mktemp("work")
    shutil.copytree(BACKEND_DIR / "chroma_db_dd3", work / "chroma_db_dd3")

    mp = pytest.MonkeyPatch()
    mp.chdir(work)
    mp.syspath_prepend(str(BACKEND_DIR))
    mp.setenv("GOOGLE_API_KEY", "test-google-key")
    mp.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    mp.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    mp.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    mp.setenv("GOOGLE_REDIRECT_URI", "http://testserver/api/auth/callback")
    mp.setenv("DATABASE_URL", f"sqlite:///{(work / 'test.db').as_posix()}")

    import api_server
    from app.db.session import init_db

    init_db()  # lifespan 은 실행되지 않으므로 테이블을 직접 만든다.
    yield api_server
    mp.undo()


@pytest.fixture(autouse=True)
def clean_db(api):
    """테스트마다 테이블을 비운다."""
    def wipe():
        db = new_session()
        try:
            db.query(ChatHistory).delete()
            db.query(User).delete()
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()


class FakeLLM:
    """llm.invoke(prompt) 만 흉내낸다. 받은 prompt를 기록한다."""

    def __init__(self, content="가짜 답변"):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)


class FakeRetriever:
    """RagRetriever.retrieve(query) 만 흉내낸다."""

    def __init__(self, docs=()):
        self.docs = list(docs)
        self.queries = []

    def retrieve(self, query):
        self.queries.append(query)
        return list(self.docs)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def make_chat_service(api, fake_llm):
    """가짜 의존성으로 ChatService 를 만든다. 넘기지 않은 의존성은 기본 가짜를 쓴다."""
    from app.services.chat_service import ChatService

    def _make(*, llm=None, retriever=None, fetch_menu=None, fetch_notice=None, **kwargs):
        return ChatService(
            llm=llm or fake_llm,
            retriever=retriever or FakeRetriever(),
            fetch_menu=fetch_menu or (lambda: "메뉴본문"),
            fetch_notice=fetch_notice or (lambda board: f"{board}-공지본문"),
            **kwargs,
        )

    return _make


@pytest.fixture
def install_chat_service(api, monkeypatch, make_chat_service):
    """api_server 가 사용하는 chat_service 를 가짜 의존성 버전으로 교체한다."""

    def _install(**kwargs):
        service = make_chat_service(**kwargs)
        monkeypatch.setattr(api, "chat_service", service)
        return service

    return _install


@pytest.fixture
def client(api):
    from fastapi.testclient import TestClient

    # with 블록을 쓰지 않으므로 lifespan(스케줄러)은 실행되지 않는다.
    return TestClient(api.app)


@pytest.fixture
def make_user(api):
    def _make(email="student@dankook.ac.kr", name="학생"):
        db = new_session()
        try:
            db.add(User(email=email, name=name))
            db.commit()
        finally:
            db.close()
        return email

    return _make


@pytest.fixture
def auth_headers(api):
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    def _headers(email="student@dankook.ac.kr", *, expired=False):
        exp = datetime.now(timezone.utc) + timedelta(minutes=-5 if expired else 60)
        token = jwt.encode({"sub": email, "exp": exp}, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm)
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def all_chat_rows(api):
    def _rows():
        db = new_session()
        try:
            return db.query(ChatHistory).order_by(ChatHistory.id).all()
        finally:
            db.close()

    return _rows


class FakeResponse:
    def __init__(self, data=None, text="", status_code=200):
        self._data = data
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def fake_httpx(monkeypatch):
    """httpx.AsyncClient 를 가짜로 교체한다 (카카오 콜백, Google OAuth 용)."""
    import httpx

    class _State:
        posts = []
        gets = []
        post_response = FakeResponse({})
        get_response = FakeResponse({})
        post_error = None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            _State.posts.append((url, kwargs))
            if _State.post_error and len(_State.posts) == 1:
                raise _State.post_error
            return _State.post_response

        async def get(self, url, **kwargs):
            _State.gets.append((url, kwargs))
            return _State.get_response

    _State.posts = []
    _State.gets = []
    _State.post_response = FakeResponse({})
    _State.get_response = FakeResponse({})
    _State.post_error = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return _State
