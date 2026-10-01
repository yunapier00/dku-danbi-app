"""Repository 와 session_scope 의 동작을 고정한다."""
from datetime import date, datetime, time, timedelta

import pytest

from app.db.models import ChatHistory, User
from conftest import new_session


def scope():
    from app.db.session import session_scope

    return session_scope()


def repos():
    from app.db.repositories import ChatRepository, UserRepository

    return ChatRepository, UserRepository


# ---------------------------------------------------------------- session_scope
def test_session_scope_commits_on_success(api):
    _, UserRepository = repos()

    with scope() as db:
        UserRepository(db).add(email="a@dankook.ac.kr", name="a")

    check = new_session()
    try:
        assert check.query(User).count() == 1
    finally:
        check.close()


def test_session_scope_rolls_back_and_reraises_on_error(api):
    _, UserRepository = repos()

    with pytest.raises(RuntimeError, match="boom"):
        with scope() as db:
            UserRepository(db).add(email="a@dankook.ac.kr", name="a")
            db.flush()
            raise RuntimeError("boom")

    check = new_session()
    try:
        assert check.query(User).count() == 0
    finally:
        check.close()


def test_get_db_yields_session_and_closes_it(api):
    from app.db.session import get_db

    gen = get_db()
    db = next(gen)
    assert db.execute(__import__("sqlalchemy").text("select 1")).scalar() == 1
    with pytest.raises(StopIteration):
        next(gen)


# ---------------------------------------------------------------- UserRepository
def test_user_repository_add_get_and_list(api):
    _, UserRepository = repos()

    with scope() as db:
        repo = UserRepository(db)
        assert repo.get_by_email("a@dankook.ac.kr") is None
        repo.add(email="a@dankook.ac.kr", name="a")
        repo.add(email="b@dankook.ac.kr", name=None)

    with scope() as db:
        repo = UserRepository(db)
        assert repo.get_by_email("a@dankook.ac.kr").name == "a"
        assert sorted(u.email for u in repo.list_all()) == ["a@dankook.ac.kr", "b@dankook.ac.kr"]


# ---------------------------------------------------------------- ChatRepository
def _seed(user_id, minutes_from_base, base=datetime(2026, 1, 1, 12, 0)):
    db = new_session()
    try:
        db.add(ChatHistory(user_id=user_id, query=f"q{minutes_from_base}", answer="a", category="general",
                           created_at=base + timedelta(minutes=minutes_from_base)))
        db.commit()
    finally:
        db.close()


def test_chat_repository_add_stores_all_fields(api):
    ChatRepository, _ = repos()

    with scope() as db:
        ChatRepository(db).add(
            user_id="u", query="q", answer="a", category="menu", retrieved_context="ctx",
            step1_time=0.1, step2_time=0.2, step3_time=0.3, total_time=0.6,
        )

    check = new_session()
    try:
        row = check.query(ChatHistory).one()
    finally:
        check.close()
    assert (row.user_id, row.query, row.answer, row.category, row.retrieved_context) == ("u", "q", "a", "menu", "ctx")
    assert (row.step1_time, row.step2_time, row.step3_time, row.total_time) == (0.1, 0.2, 0.3, 0.6)


def test_recent_for_user_returns_latest_n_oldest_first(api):
    ChatRepository, _ = repos()
    for i in range(5):
        _seed("u", i)
    _seed("other", 99)

    with scope() as db:
        records = ChatRepository(db).recent_for_user("u", limit=3)
        queries = [r.query for r in records]  # commit 후에는 객체가 만료되므로 블록 안에서 읽는다

    assert queries == ["q2", "q3", "q4"]


def test_count_for_user_on_counts_only_that_user_and_day(api):
    ChatRepository, _ = repos()
    today_noon = datetime.combine(date.today(), time(12, 0))
    for _ in range(2):
        _seed("u", 0, base=today_noon)
    _seed("u", 0, base=datetime(2020, 1, 1, 12, 0))
    _seed("other", 0, base=today_noon)

    with scope() as db:
        repo = ChatRepository(db)
        assert repo.count_for_user_on("u", date.today()) == 2
        assert repo.count_for_user_on("u", date(2020, 1, 1)) == 1
        assert repo.count_for_user_on("nobody", date.today()) == 0
