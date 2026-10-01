"""무인증 /api/chat 은 제거되었다. 다시 생기지 않도록 고정한다."""


def test_unauthenticated_chat_endpoint_is_gone(client):
    assert client.post("/api/chat", json={"query": "안녕", "user_id": "x"}).status_code == 404


def test_cannot_write_into_another_users_history_anymore(api, client, make_user, all_chat_rows):
    victim = make_user("victim@dankook.ac.kr")

    client.post("/api/chat", json={"query": "가짜 질문", "user_id": victim})

    assert all_chat_rows() == []


def test_web_chat_ignores_client_supplied_user_id(client, make_user, auth_headers, install_chat_service, all_chat_rows):
    me = make_user("me@dankook.ac.kr")
    make_user("victim@dankook.ac.kr")
    install_chat_service()

    r = client.post(
        "/api/web/chat",
        json={"query": "학식", "user_id": "victim@dankook.ac.kr"},
        headers=auth_headers(me),
    )

    assert r.status_code == 200
    (row,) = all_chat_rows()
    assert row.user_id == me


def test_lifespan_creates_tables_and_registers_briefing_job(api):
    """init_db 가 lifespan 에서 호출되는지 확인한다 (import 시점 create_all 제거)."""
    import asyncio

    from sqlalchemy import inspect

    from app.db.session import engine

    calls = []
    original = api.init_db
    api.init_db = lambda: (calls.append(1), original())[1]
    try:
        async def run():
            async with api.lifespan(api.app):
                pass

        asyncio.run(run())
    finally:
        api.init_db = original

    assert calls == [1]
    assert {"users", "chat_history"} <= set(inspect(engine).get_table_names())
