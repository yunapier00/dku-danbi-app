"""Settings: 환경변수 이름/기본값이 리팩토링 이전 코드와 같은지 고정한다."""
import pytest

from app.core.config import DEFAULT_CORS_ORIGINS, get_settings

ENV_NAMES = [
    "DATABASE_URL", "CHROMA_DB_PATH", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
    "JWT_SECRET_KEY", "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES", "FRONTEND_URL", "CORS_ORIGINS",
    "KAKAO_DAILY_LIMIT",
    "CRAWLER_VERIFY_SSL", "MENU_CACHE_TTL_SECONDS", "NOTICE_CACHE_TTL_SECONDS",
    "KAKAO_WEBHOOK_SECRET",
    "CHROME_BINARY_PATH", "CHROMEDRIVER_PATH",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_match_previous_hardcoded_values(clean_env):
    s = get_settings()

    assert s.database_url == "sqlite:////app/data/danbi_chat.db"
    assert s.chroma_db_path == "./chroma_db_dd3"
    assert s.jwt_algorithm == "HS256"
    assert s.access_token_expire_minutes == 1440
    assert s.frontend_url == "http://localhost:5173"
    assert s.cors_origins == [DEFAULT_CORS_ORIGINS] == ["https://keen-passion-production-9012.up.railway.app"]
    assert s.kakao_daily_limit == 3
    assert s.crawler_verify_ssl is True
    assert (s.menu_cache_ttl_seconds, s.notice_cache_ttl_seconds) == (1800, 300)
    assert s.kakao_webhook_secret is None
    assert (s.chrome_binary_path, s.chromedriver_path) == (None, None)
    assert (s.llm_model, s.embedding_model) == ("models/gemini-flash-latest", "models/gemini-embedding-001")
    assert s.chroma_collection == "campus_rules"
    assert (s.retriever_k, s.bm25_weight, s.vector_weight) == (3, 0.7, 0.3)
    assert (s.scheduler_timezone, s.briefing_hour, s.briefing_minute) == ("Asia/Seoul", 9, 0)


def test_env_overrides_are_read_at_call_time(clean_env):
    clean_env.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    clean_env.setenv("KAKAO_DAILY_LIMIT", "10")
    assert get_settings().access_token_expire_minutes == 30
    assert get_settings().kakao_daily_limit == 10

    clean_env.setenv("FRONTEND_URL", "http://a.test")
    assert get_settings().frontend_url == "http://a.test"
    clean_env.setenv("FRONTEND_URL", "http://b.test")
    assert get_settings().frontend_url == "http://b.test"


def test_cors_origins_accepts_comma_separated_list(clean_env):
    clean_env.setenv("CORS_ORIGINS", " http://a.test , http://b.test ,, ")
    assert get_settings().cors_origins == ["http://a.test", "http://b.test"]


def test_missing_required_lists_unset_login_variables(clean_env):
    assert get_settings().missing_required() == [
        "JWT_SECRET_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
    ]

    clean_env.setenv("JWT_SECRET_KEY", "s")
    clean_env.setenv("GOOGLE_CLIENT_ID", "i")
    clean_env.setenv("GOOGLE_CLIENT_SECRET", "x")
    clean_env.setenv("GOOGLE_REDIRECT_URI", "http://cb")
    assert get_settings().missing_required() == []


def test_settings_are_immutable(clean_env):
    with pytest.raises(Exception):
        get_settings().kakao_daily_limit = 99


@pytest.mark.parametrize("raw, expected", [("true", True), ("1", True), ("False", False), ("0", False), ("off", False)])
def test_crawler_verify_ssl_parsing(clean_env, raw, expected):
    clean_env.setenv("CRAWLER_VERIFY_SSL", raw)
    assert get_settings().crawler_verify_ssl is expected


def test_kakao_webhook_secret_defaults_to_none_and_reads_env(clean_env):
    assert get_settings().kakao_webhook_secret is None
    clean_env.setenv("KAKAO_WEBHOOK_SECRET", "s3cr3t")
    assert get_settings().kakao_webhook_secret == "s3cr3t"


def test_chrome_paths_default_to_none_and_read_env(clean_env):
    assert (get_settings().chrome_binary_path, get_settings().chromedriver_path) == (None, None)

    clean_env.setenv("CHROME_BINARY_PATH", "/usr/bin/chromium")
    clean_env.setenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    s = get_settings()
    assert (s.chrome_binary_path, s.chromedriver_path) == ("/usr/bin/chromium", "/usr/bin/chromedriver")
