"""애플리케이션 설정의 단일 출처.

환경변수 이름과 기본값은 리팩토링 이전 코드와 동일하다.
`get_settings()`는 호출 시점의 환경변수를 읽는다(캐시하지 않음).
"""
import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# 기존 코드에 하드코딩되어 있던 운영 프런트엔드 주소 (CORS_ORIGINS 미설정 시 그대로 사용)
DEFAULT_CORS_ORIGINS = "https://keen-passion-production-9012.up.railway.app"


def _csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() not in ("0", "false", "no", "off", "")


@dataclass(frozen=True)
class Settings:
    # --- 저장소 ---
    database_url: str
    chroma_db_path: str

    # --- 인증 ---
    google_client_id: Optional[str]
    google_client_secret: Optional[str]
    google_redirect_uri: Optional[str]
    jwt_secret_key: Optional[str]
    jwt_algorithm: str
    access_token_expire_minutes: int

    # --- 웹 ---
    frontend_url: str
    cors_origins: List[str]

    # --- 정책 ---
    kakao_daily_limit: int

    # --- 크롤러 ---
    crawler_verify_ssl: bool
    menu_cache_ttl_seconds: int
    notice_cache_ttl_seconds: int

    # --- 카카오 웹훅 ---
    # 설정하면 요청 헤더(KAKAO_SECRET_HEADER)와 대조해 검증한다. 미설정 시 검증을 건너뛴다(기존 배포 호환).
    # 카카오 i 오픈빌더 '스킬' 설정의 스킬 서버 HTTP 헤더에 같은 이름/값을 등록해야 한다.
    kakao_webhook_secret: Optional[str]

    # --- 모델 / 검색 (환경변수 아님, 코드 상수) ---
    llm_model: str = "models/gemini-flash-latest"
    embedding_model: str = "models/gemini-embedding-001"
    chroma_collection: str = "campus_rules"
    retriever_k: int = 3
    bm25_weight: float = 0.7
    vector_weight: float = 0.3

    # --- 스케줄러 / 로그 (환경변수 아님, 코드 상수) ---
    scheduler_timezone: str = "Asia/Seoul"
    briefing_hour: int = 9
    briefing_minute: int = 0
    log_dir: str = "logs"

    def missing_required(self) -> List[str]:
        """웹 로그인에 필요하지만 비어 있는 환경변수 이름 목록."""
        required = {
            "JWT_SECRET_KEY": self.jwt_secret_key,
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "GOOGLE_REDIRECT_URI": self.google_redirect_uri,
        }
        return [name for name, value in required.items() if not value]


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:////app/data/danbi_chat.db"),
        chroma_db_path=os.getenv("CHROMA_DB_PATH", "./chroma_db_dd3"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI"),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173"),
        cors_origins=_csv(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
        kakao_daily_limit=int(os.getenv("KAKAO_DAILY_LIMIT", 3)),
        crawler_verify_ssl=_bool(os.getenv("CRAWLER_VERIFY_SSL", "true")),
        menu_cache_ttl_seconds=int(os.getenv("MENU_CACHE_TTL_SECONDS", 1800)),
        notice_cache_ttl_seconds=int(os.getenv("NOTICE_CACHE_TTL_SECONDS", 300)),
        kakao_webhook_secret=os.getenv("KAKAO_WEBHOOK_SECRET"),
    )
