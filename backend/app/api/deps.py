from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import User
from app.db.repositories import UserRepository
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# 토큰 감별 함수
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cfg = get_settings()
    credentials_exception = HTTPException(
        status_code=401,
        detail="유효하지 않은 토큰입니다. 다시 로그인해주세요.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 1. 우리가 만든 비밀키(JWT_SECRET_KEY)로 토큰 열어보기
        payload = jwt.decode(token, cfg.jwt_secret_key, algorithms=[cfg.jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 2. DB에 진짜 있는 유저인지 최종 확인
    user = UserRepository(db).get_by_email(email)
    if user is None:
        raise credentials_exception
    return user  # 검증이 완료된 유저 객체 반환
