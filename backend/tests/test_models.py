"""ORM 모델 기본 동작(기본값, 제약)을 고정한다."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import User
from conftest import new_session


def test_created_at_defaults_to_kst(api):
    db = new_session()
    try:
        db.add(User(email="kst@dankook.ac.kr"))
        db.commit()
        user = db.query(User).one()
    finally:
        db.close()

    expected = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
    assert abs((user.created_at - expected).total_seconds()) < 5


def test_user_email_is_unique(api):
    db = new_session()
    try:
        db.add(User(email="dup@dankook.ac.kr"))
        db.commit()
        db.add(User(email="dup@dankook.ac.kr"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_user_email_is_required(api):
    db = new_session()
    try:
        db.add(User(email=None))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
