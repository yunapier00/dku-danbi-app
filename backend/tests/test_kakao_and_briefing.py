"""카카오 웹훅, 콜백 전송, 모닝 브리핑의 현재 동작을 고정한다."""
import asyncio
from datetime import date, datetime, time
from types import SimpleNamespace

import pytest

from app.core.timeutil import today_kst
from app.crawlers.errors import CrawlerError
from app.db.models import ChatHistory
from app.services.kakao_service import KAKAO_SECRET_HEADER
from conftest import get_settings, new_session


def kakao_body(utterance="안녕", user_id="kakao-1", callback_url="https://callback.test/abc"):
    user_request = {"utterance": utterance, "user": {"id": user_id}}
    if callback_url is not None:
        user_request["callbackUrl"] = callback_url
    return {"userRequest": user_request}


def add_chats_on(api, user_id, day, n):
    at_noon = datetime.combine(day, time(12, 0))
    db = new_session()
    try:
        for i in range(n):
            db.add(ChatHistory(user_id=user_id, query=f"q{i}", answer="a", created_at=at_noon))
        db.commit()
    finally:
        db.close()


def add_today_chats(api, user_id, n):
    # 운영 코드가 사용하는 것과 같은 기준(today_kst)으로 "오늘"을 정한다. date.today()(서버 로컬 시간대)를
    # 쓰면 테스트를 실행하는 시각에 따라(KST 자정 전후) 간헐적으로 어긋날 수 있다.
    add_chats_on(api, user_id, today_kst(), n)


def text_of(payload):
    return payload["template"]["outputs"][0]["simpleText"]["text"]


# ---------------------------------------------------------------- 웹훅
def test_kakao_accepts_and_replies_via_callback(api, client, fake_httpx, monkeypatch):
    calls = []

    def fake_generate(query, history, user_id):
        calls.append((query, history, user_id))
        return "카카오 답변", "general"

    monkeypatch.setattr(api, "generate_chat_response", fake_generate)

    r = client.post("/api/kakao", json=kakao_body("도서관", "kakao-1"))

    assert r.json() == {"useCallback": True}
    assert calls == [("도서관", "", "kakao-1")]  # 카카오는 history를 항상 빈 문자열로 넘긴다
    (url, kwargs), = fake_httpx.posts
    assert url == "https://callback.test/abc"
    assert kwargs["json"] == {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": "카카오 답변"}}]},
    }


def test_kakao_without_callback_url_returns_error_text(client):
    r = client.post("/api/kakao", json=kakao_body(callback_url=None))

    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "2.0"
    assert "콜백 URL 에러" in text_of(body)


def test_kakao_blocks_after_daily_limit(api, client, fake_httpx):
    assert get_settings().kakao_daily_limit == 3
    add_today_chats(api, "kakao-1", 3)

    r = client.post("/api/kakao", json=kakao_body(user_id="kakao-1"))

    assert r.status_code == 200
    assert text_of(r.json()) == "하루 질문 한도 3회 초과\n내일 다시 찾아와주세요!"
    assert fake_httpx.posts == []


def test_kakao_allows_when_below_limit_and_counts_per_user(api, client, fake_httpx, monkeypatch):
    monkeypatch.setattr(api, "generate_chat_response", lambda q, h, u: ("ok", "general"))
    add_today_chats(api, "kakao-1", 2)
    add_today_chats(api, "kakao-other", 5)  # 다른 유저의 사용량은 영향 없음

    assert client.post("/api/kakao", json=kakao_body(user_id="kakao-1")).json() == {"useCallback": True}


def test_kakao_ignores_yesterdays_usage(api, client, fake_httpx, monkeypatch):
    monkeypatch.setattr(api, "generate_chat_response", lambda q, h, u: ("ok", "general"))
    db = new_session()
    try:
        for i in range(5):
            db.add(ChatHistory(user_id="kakao-1", query="q", answer="a", created_at=datetime(2020, 1, 1, 12, 0)))
        db.commit()
    finally:
        db.close()

    assert client.post("/api/kakao", json=kakao_body(user_id="kakao-1")).json() == {"useCallback": True}


def test_kakao_malformed_body_returns_use_callback_false(client):
    r = client.post("/api/kakao", json={"unexpected": "shape"})
    assert r.json() == {"useCallback": False}


def test_kakao_daily_limit_uses_kst_today_not_server_local_date(api, client, fake_httpx, monkeypatch):
    """버그 수정: 예전엔 서버 로컬 시간대의 date.today() 와 KST 로 저장된 기록을 비교해, 서버가 UTC로
    돌면 KST 00~09시 사이에 사용량 집계가 어긋날 수 있었다."""
    import app.api.routes.kakao as kakao_route

    fixed_kst_today = date(2026, 3, 15)
    monkeypatch.setattr(kakao_route, "today_kst", lambda: fixed_kst_today)
    add_chats_on(api, "kakao-1", fixed_kst_today, 3)

    r = client.post("/api/kakao", json=kakao_body(user_id="kakao-1"))

    assert "하루 질문 한도" in text_of(r.json())


# ---------------------------------------------------------------- 웹훅 서명 검증
def test_webhook_allowed_when_no_secret_is_configured(api, client, fake_httpx, monkeypatch):
    monkeypatch.delenv("KAKAO_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(api, "generate_chat_response", lambda q, h, u: ("ok", "general"))

    assert client.post("/api/kakao", json=kakao_body()).json() == {"useCallback": True}


def test_webhook_rejected_when_secret_configured_and_header_missing(api, client, monkeypatch):
    monkeypatch.setenv("KAKAO_WEBHOOK_SECRET", "top-secret")

    r = client.post("/api/kakao", json=kakao_body())

    assert r.status_code == 401


def test_webhook_rejected_when_secret_configured_and_header_wrong(api, client, monkeypatch):
    monkeypatch.setenv("KAKAO_WEBHOOK_SECRET", "top-secret")

    r = client.post("/api/kakao", json=kakao_body(), headers={KAKAO_SECRET_HEADER: "wrong-value"})

    assert r.status_code == 401


def test_webhook_accepted_when_secret_header_matches(api, client, fake_httpx, monkeypatch):
    monkeypatch.setenv("KAKAO_WEBHOOK_SECRET", "top-secret")
    monkeypatch.setattr(api, "generate_chat_response", lambda q, h, u: ("ok", "general"))

    r = client.post("/api/kakao", json=kakao_body(), headers={KAKAO_SECRET_HEADER: "top-secret"})

    assert r.json() == {"useCallback": True}


def test_webhook_rejection_does_not_leak_into_daily_limit_or_callback(api, client, fake_httpx, monkeypatch):
    monkeypatch.setenv("KAKAO_WEBHOOK_SECRET", "top-secret")

    client.post("/api/kakao", json=kakao_body(user_id="kakao-1"))  # 헤더 없이 거부됨

    assert fake_httpx.posts == []


# ---------------------------------------------------------------- 콜백 전송
def test_callback_sends_error_message_when_generation_fails(api, fake_httpx, monkeypatch):
    def boom(*args):
        raise RuntimeError("llm down")

    monkeypatch.setattr(api, "generate_chat_response", boom)

    asyncio.run(api.process_and_send_callback("질문", "https://callback.test/x", "kakao-1"))

    (url, kwargs), = fake_httpx.posts
    assert url == "https://callback.test/x"
    assert text_of(kwargs["json"]) == "서버 내부 오류가 발생했습니다."


def test_callback_failure_is_logged_as_error_not_success(api, fake_httpx, monkeypatch):
    """버그 수정: 예전엔 실패해도 '카카오 콜백 비동기 전송 성공' 으로 로그가 남았다."""
    from loguru import logger as loguru_logger

    def boom(*args):
        raise RuntimeError("llm down")

    monkeypatch.setattr(api, "generate_chat_response", boom)

    records = []
    sink_id = loguru_logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        asyncio.run(api.process_and_send_callback("질문", "https://callback.test/x", "kakao-1"))
    finally:
        loguru_logger.remove(sink_id)

    kakao_records = [r for r in records if "kakao-1" in r["message"]]
    assert kakao_records, "카카오 콜백 관련 로그가 전혀 남지 않았다"
    assert all(r["level"].name == "ERROR" for r in kakao_records)
    assert not any("성공" in r["message"] for r in kakao_records)


# ---------------------------------------------------------------- 모닝 브리핑
@pytest.fixture
def make_briefing(api, fake_llm):
    from app.services.briefing_service import BriefingService

    def _make(fetch_notice=None, llm=None):
        calls = []

        def default_fetch(board):
            calls.append(board)
            return "공지 원문"

        service = BriefingService(llm=llm or fake_llm, fetch_notice=fetch_notice or default_fetch)
        return service, calls

    return _make


def test_briefing_writes_one_message_per_user(make_briefing, fake_llm, make_user, all_chat_rows):
    make_user("a@dankook.ac.kr")
    make_user("b@dankook.ac.kr")
    fake_llm.content = [{"text": "요약 "}, {"text": "본문"}]
    service, fetch_calls = make_briefing()

    assert service.deliver() == 2

    assert fetch_calls == ["모바일시스템공학과"]
    assert "공지 원문" in fake_llm.prompts[0]
    rows = all_chat_rows()
    assert sorted(r.user_id for r in rows) == ["a@dankook.ac.kr", "b@dankook.ac.kr"]
    for row in rows:
        assert row.query == "[자동 브리핑]"
        assert row.answer == "**📢 [오늘의 단국대 모닝 브리핑]**\n\n요약 본문"
        assert row.category == "notice"
        assert row.retrieved_context == "스케줄러 자동 발송"
        assert (row.step1_time, row.step2_time, row.step3_time, row.total_time) == (0.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize("error", [RuntimeError("crawler down"), CrawlerError("서버 연결 중 오류가 발생했습니다: x")])
def test_briefing_swallows_crawler_errors_and_writes_nothing(make_briefing, fake_llm, make_user, all_chat_rows, error):
    """버그 수정: 크롤링 실패 시 오류 문구를 요약한 브리핑이 전 사용자에게 저장되던 문제."""
    make_user()

    def boom(board):
        raise error

    service, _ = make_briefing(fetch_notice=boom)

    assert service.deliver() == 0  # 예외가 밖으로 나오면 안 된다

    assert all_chat_rows() == []
    assert fake_llm.prompts == []  # 오류 문구를 LLM 에 요약시키지도 않는다


def test_briefing_writes_nothing_when_llm_fails(make_briefing, make_user, all_chat_rows):
    make_user()

    class BrokenLLM:
        def invoke(self, prompt):
            raise RuntimeError("quota")

    service, _ = make_briefing(llm=BrokenLLM())

    assert service.deliver() == 0
    assert all_chat_rows() == []


def test_scheduler_job_delegates_to_briefing_service(api, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "briefing_service", SimpleNamespace(deliver=lambda: calls.append(1)))

    api.deliver_morning_briefing_to_db()

    assert calls == [1]


def test_scheduler_registers_daily_9am_job(api):
    """lifespan이 등록하는 잡: 매일 09:00 (Asia/Seoul) 한 개."""
    import asyncio as aio
    import apscheduler.schedulers.background as bg

    registered = []
    original = bg.BackgroundScheduler

    class SpyScheduler(original):
        def add_job(self, func, trigger=None, **kwargs):
            registered.append((func, trigger, kwargs))
            return super().add_job(func, trigger, **kwargs)

    async def run():
        async with api.lifespan(api.app):
            pass

    api.BackgroundScheduler = SpyScheduler
    try:
        aio.run(run())
    finally:
        api.BackgroundScheduler = original

    assert len(registered) == 1
    func, trigger, kwargs = registered[0]
    assert func is api.deliver_morning_briefing_to_db
    assert trigger == "cron"
    assert (kwargs["hour"], kwargs["minute"]) == (9, 0)
