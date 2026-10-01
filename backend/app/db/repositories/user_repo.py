from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    """User 테이블 접근. commit 은 호출하는 쪽(session_scope)이 책임진다."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def add(self, *, email: str, name: Optional[str]) -> User:
        user = User(email=email, name=name)
        self.db.add(user)
        return user

    def list_all(self) -> List[User]:
        return self.db.query(User).all()
