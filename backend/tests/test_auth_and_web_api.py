"""웹 API(인증, 채팅, 기록)와 Google OAuth 콜백의 현재 동작을 고정한다."""
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from jose import jwt

from app.db.models import ChatHistory, User
from conftest import FakeResponse, get_settings, new_session


def add_chat(api, user_id, query, answer, created_at, category="general"):
    db = new_session()
    try:
        db.add(ChatHistory(user_id=user_id, query=query, answer=answer, category=category, created_at=created_at))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------- 토큰 검증
def test_history_requires_token(client):
    assert client.get("/api/web/history").status_code == 401


def test_history_rejects_garbage_token(client):
    r = client.get("/api/web/history", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_history_rejects_expired_token(client, make_user, auth_headers):
    make_user()
    assert client.get("/api/web/history", headers=auth_headers(expired=True)).status_code == 401


def test_history_rejects_valid_token_for_unknown_user(client, auth_headers):
    assert client.get("/api/web/history", headers=auth_headers("ghost@dankook.ac.kr")).status_code == 401


def test_history_rejects_token_without_sub(api, client, make_user):
    make_user()
    token = jwt.encode({"foo": "bar"}, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm)
    assert client.get("/api/web/history", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_history_rejects_unsigned_token(client, make_user):
    import base64
    import json

    make_user()

    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'student@dankook.ac.kr'})}."
    assert client.get("/api/web/history", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_history_rejects_token_signed_with_other_key(api, client, make_user):
    make_user()
    token = jwt.encode({"sub": "student@dankook.ac.kr"}, "other-secret", algorithm=get_settings().jwt_algorithm)
    assert client.get("/api/web/history", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ---------------------------------------------------------------- 대화 기록
def test_history_returns_messages_oldest_first_and_skips_briefing_query(api, client, make_user, auth_headers):
    email = make_user()
    make_user("other@dankook.ac.kr")
    base = datetime(2026, 1, 1, 12, 0, 0)
    add_chat(api, email, "질문1", "답변1", base)
    add_chat(api, email, "[자동 브리핑]", "브리핑 본문", base + timedelta(minutes=1))
    add_chat(api, email, "질문3", None, base + timedelta(minutes=2))
    add_chat(api, "other@dankook.ac.kr", "남의 질문", "남의 답변", base + timedelta(minutes=3))

    r = client.get("/api/web/history", headers=auth_headers(email))

    assert r.status_code == 200
    assert r.json() == {
        "history": [
            {"message": "질문1", "sender": "user", "direction": "outgoing"},
            {"message": "답변1", "sender": "Danbi", "direction": "incoming"},
            {"message": "브리핑 본문", "sender": "Danbi", "direction": "incoming"},
            {"message": "질문3", "sender": "user", "direction": "outgoing"},
        ]
    }


def test_history_is_limited_to_latest_50_records(api, client, make_user, auth_headers):
    email = make_user()
    base = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(55):
        add_chat(api, email, f"q{i}", f"a{i}", base + timedelta(minutes=i))

    history = client.get("/api/web/history", headers=auth_headers(email)).json()["history"]

    assert len(history) == 100  # 50 records x (질문 + 답변)
    assert history[0]["message"] == "q5"
    assert history[-1]["message"] == "a54"


# ---------------------------------------------------------------- 웹 채팅
def test_web_chat_requires_token(client):
    assert client.post("/api/web/chat", json={"query": "안녕"}).status_code == 401


def test_web_chat_returns_answer_and_stores_history_under_email(
    client, make_user, auth_headers, install_chat_service, all_chat_rows
):
    email = make_user()
    install_chat_service()

    r = client.post("/api/web/chat", json={"query": "오늘 학식", "history": ""}, headers=auth_headers(email))

    assert r.status_code == 200
    assert r.json() == {"answer": "가짜 답변", "category": "menu"}
    (row,) = all_chat_rows()
    assert row.user_id == email and row.query == "오늘 학식"


# ---------------------------------------------------------------- 로그인 리다이렉트
def test_login_redirects_to_google_with_client_settings(client):
    r = client.get("/api/auth/login", follow_redirects=False)

    assert r.status_code in (302, 307)
    location = r.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    params = parse_qs(urlparse(location).query)
    assert params["client_id"] == ["test-client-id"]
    assert params["redirect_uri"] == ["http://testserver/api/auth/callback"]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert len(params["state"][0]) > 20  # 서명된 CSRF state 토큰이 매번 발급된다


def test_login_issues_a_fresh_state_each_time(client):
    first = parse_qs(urlparse(client.get("/api/auth/login", follow_redirects=False).headers["location"]).query)
    second = parse_qs(urlparse(client.get("/api/auth/login", follow_redirects=False).headers["location"]).query)

    assert first["state"][0] != second["state"][0]


# ---------------------------------------------------------------- OAuth 콜백
def _stub_google(fake_httpx, *, access_token="google-access", email="new@dankook.ac.kr", name="새학생"):
    fake_httpx.post_response = FakeResponse({"access_token": access_token} if access_token else {})
    fake_httpx.get_response = FakeResponse({"email": email, "name": name})


def _get_valid_state(client) -> str:
    """실제 로그인 플로우처럼 /api/auth/login 이 발급한 state 를 가져온다."""
    location = client.get("/api/auth/login", follow_redirects=False).headers["location"]
    return parse_qs(urlparse(location).query)["state"][0]


def test_callback_rejects_missing_state(client, fake_httpx):
    _stub_google(fake_httpx)

    r = client.get("/api/auth/callback", params={"code": "abc"}, follow_redirects=False)

    assert r.status_code == 400
    assert r.json()["detail"] == "유효하지 않은 로그인 요청입니다. 다시 로그인해주세요."
    assert fake_httpx.posts == []  # 구글에 코드를 교환하러 가지도 않는다


def test_callback_rejects_tampered_or_foreign_state(client, fake_httpx):
    _stub_google(fake_httpx)

    r = client.get("/api/auth/callback", params={"code": "abc", "state": "not-a-real-token"}, follow_redirects=False)

    assert r.status_code == 400
    assert fake_httpx.posts == []


def test_callback_rejects_expired_state(api, client, fake_httpx):
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    expired_state = jwt.encode(
        {"typ": "state", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        get_settings().jwt_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )
    _stub_google(fake_httpx)

    r = client.get("/api/auth/callback", params={"code": "abc", "state": expired_state}, follow_redirects=False)

    assert r.status_code == 400


def test_an_access_token_cannot_be_reused_as_login_state(client, fake_httpx, auth_headers):
    """state 와 로그인 세션 토큰은 같은 비밀키로 서명되지만 typ 클레임으로 서로 바꿔 쓸 수 없다."""
    access_token = auth_headers()["Authorization"].removeprefix("Bearer ")
    _stub_google(fake_httpx)

    r = client.get("/api/auth/callback", params={"code": "abc", "state": access_token}, follow_redirects=False)

    assert r.status_code == 400


def test_callback_creates_user_and_redirects_with_jwt(api, client, fake_httpx, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://front.test")
    _stub_google(fake_httpx)

    r = client.get(
        "/api/auth/callback", params={"code": "abc", "state": _get_valid_state(client)}, follow_redirects=False
    )

    assert r.status_code in (302, 307)
    location = urlparse(r.headers["location"])
    assert f"{location.scheme}://{location.netloc}" == "http://front.test"
    token = parse_qs(location.query)["token"][0]
    payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
    assert payload["sub"] == "new@dankook.ac.kr"
    assert payload["exp"] > datetime.now().timestamp()

    db = new_session()
    try:
        user = db.query(User).filter_by(email="new@dankook.ac.kr").one()
        assert user.name == "새학생"
    finally:
        db.close()

    # 구글 토큰 교환 요청 내용
    (token_url, kwargs) = fake_httpx.posts[0]
    assert token_url == "https://oauth2.googleapis.com/token"
    assert kwargs["data"]["code"] == "abc"
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["client_id"] == "test-client-id"
    (userinfo_url, kwargs) = fake_httpx.gets[0]
    assert userinfo_url == "https://www.googleapis.com/oauth2/v2/userinfo"
    assert kwargs["headers"] == {"Authorization": "Bearer google-access"}


def test_callback_does_not_duplicate_existing_user(api, client, fake_httpx, make_user):
    make_user("new@dankook.ac.kr", "기존이름")
    _stub_google(fake_httpx)

    r = client.get(
        "/api/auth/callback", params={"code": "abc", "state": _get_valid_state(client)}, follow_redirects=False
    )

    assert r.status_code in (302, 307)
    db = new_session()
    try:
        assert db.query(User).count() == 1
    finally:
        db.close()


def test_callback_returns_400_when_google_gives_no_access_token(client, fake_httpx):
    _stub_google(fake_httpx, access_token=None)

    r = client.get(
        "/api/auth/callback", params={"code": "bad", "state": _get_valid_state(client)}, follow_redirects=False
    )

    assert r.status_code == 400
    assert r.json()["detail"] == "Google 인증 실패"
    assert fake_httpx.gets == []  # 토큰 교환이 실패하면 사용자 정보는 조회하지 않는다


def test_callback_currently_allows_non_school_email(api, client, fake_httpx):
    """현재 동작 고정: @dankook.ac.kr 도메인 제한은 (구현되어 테스트도 되어 있지만) 주석 처리되어 있어
    외부 계정도 가입된다. app/services/auth_service.py 의 주석 두 줄을 해제하면 켤 수 있다."""
    _stub_google(fake_httpx, email="outsider@gmail.com")

    r = client.get(
        "/api/auth/callback", params={"code": "abc", "state": _get_valid_state(client)}, follow_redirects=False
    )

    assert r.status_code in (302, 307)
    assert "token=" in r.headers["location"]
