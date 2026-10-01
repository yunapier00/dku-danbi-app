"""조립 루트(composition root).

서비스(LLM/검색/크롤러/인증)를 조립하고 FastAPI 앱과 스케줄러를 구성한다.
HTTP 라우팅 자체는 app/api/routes/* 에 있다 — 그 라우터들은 이 모듈을 `import api_server` 로 참조하고
요청 처리 시점에 `api_server.chat_service` 식으로 속성을 조회하므로, 여기서 이름을 재할당하면(테스트의
monkeypatch 포함) 라우터 쪽에도 그대로 반영된다.
"""
import asyncio
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.crawlers.menu import MenuCrawler
from app.crawlers.notice import NoticeCrawler
from app.db.session import init_db
from app.rag.llm import build_embeddings, build_llm
from app.rag.retriever import build_retriever
from app.services.auth_service import AuthService
from app.services.briefing_service import BriefingService
from app.services.chat_service import ChatService
from app.services.kakao_service import kakao_text_response

settings = get_settings()
setup_logging(settings.log_dir)


# ---------------------------------------------------------------- 서비스 조립
logger.info("서버 로딩 중...")
llm = build_llm(settings)
retriever = build_retriever(settings, build_embeddings(settings))
menu_crawler = MenuCrawler(cache_ttl_seconds=settings.menu_cache_ttl_seconds)
notice_crawler = NoticeCrawler(
    verify_ssl=settings.crawler_verify_ssl,
    cache_ttl_seconds=settings.notice_cache_ttl_seconds,
)
chat_service = ChatService(
    llm=llm,
    retriever=retriever,
    fetch_menu=menu_crawler.get_menu,
    fetch_notice=notice_crawler.get_text,
)
briefing_service = BriefingService(llm=llm, fetch_notice=notice_crawler.get_text)
auth_service = AuthService(settings)
logger.info("AI 로딩 완료!")


def generate_chat_response(query: str, history: str, user_id: str):
    return chat_service.respond(query, history, user_id)


def deliver_morning_briefing_to_db():
    briefing_service.deliver()


async def process_and_send_callback(user_message: str, callback_url: str, user_id: str):
    try:
        answer, _category = await asyncio.to_thread(generate_chat_response, user_message, "", user_id)
        payload = kakao_text_response(answer)

        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=payload)

        logger.info(f"카카오 콜백 비동기 전송 성공 - User ID: {user_id}")

    except Exception as e:
        # 버그 수정: 예전에는 이 분기에서도 "전송 성공"으로 로그가 남았다.
        logger.error(f"❌ 카카오 콜백 처리 실패 - User ID: {user_id}, 에러: {e}")
        error_payload = kakao_text_response("서버 내부 오류가 발생했습니다.")
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=error_payload)


# ---------------------------------------------------------------- 앱
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    missing = settings.missing_required()
    if missing:
        logger.warning(f"필수 환경변수가 설정되지 않았습니다 (웹 로그인 불가): {', '.join(missing)}")
    if not settings.kakao_webhook_secret:
        logger.info(
            "KAKAO_WEBHOOK_SECRET 이 설정되지 않아 카카오 웹훅 요청을 검증하지 않습니다. "
            "카카오 i 오픈빌더 '스킬' 설정에 헤더를 추가하고 이 값을 설정하면 검증이 켜집니다."
        )

    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    # 매일 아침 9시 브리핑
    scheduler.add_job(deliver_morning_briefing_to_db, 'cron', hour=settings.briefing_hour, minute=settings.briefing_minute)

    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="단국대 AI 서버", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터는 app 과 위 서비스들이 준비된 뒤에 등록한다. 각 라우터 모듈은 `import api_server` 로 이 모듈을
# 참조하며, 핸들러 안에서 api_server.chat_service 처럼 속성을 조회하므로 여기서는 모듈만 있으면 된다.
from app.api.routes import auth as auth_routes  # noqa: E402
from app.api.routes import chat as chat_routes  # noqa: E402
from app.api.routes import kakao as kakao_routes  # noqa: E402

app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(kakao_routes.router)
