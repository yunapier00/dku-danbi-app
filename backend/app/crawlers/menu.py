"""1947 학식 메뉴 크롤러 (동적 페이지라 Selenium 사용)."""
import os
import threading
import time
from datetime import date
from typing import Callable, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

from app.core.config import get_settings
from app.core.timeutil import today_kst
from app.crawlers.cache import TTLCache
from app.crawlers.errors import CrawlerError

MENU_URL = "https://cms.dankook.ac.kr/web/kor/1947_commons"
RENDER_WAIT_SECONDS = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"

# webdriver-manager로 내려받은 드라이버 경로는 프로세스 동안 한 번만 확인한다.
# (CHROMEDRIVER_PATH 가 설정되어 있으면 이 캐시/다운로드 자체를 타지 않는다.)
_driver_path: Optional[str] = None
_driver_path_lock = threading.Lock()


def _chromedriver_path(settings) -> str:
    if settings.chromedriver_path:
        return settings.chromedriver_path

    global _driver_path
    with _driver_path_lock:
        if _driver_path is None:
            if os.name == "nt":
                _driver_path = ChromeDriverManager().install()
            else:
                _driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
        return _driver_path


def create_chrome_driver():
    settings = get_settings()
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={USER_AGENT}")

    # CHROME_BINARY_PATH 미설정 시 기존 동작 그대로: Windows는 시스템 Chrome, 그 외는 /usr/bin/chromium 가정.
    binary_path = settings.chrome_binary_path or (None if os.name == "nt" else "/usr/bin/chromium")
    if binary_path:
        options.binary_location = binary_path

    return webdriver.Chrome(service=Service(_chromedriver_path(settings)), options=options)


class MenuCrawler:
    def __init__(
        self,
        *,
        driver_factory: Callable = create_chrome_driver,
        cache_ttl_seconds: float = 1800,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = today_kst,
    ):
        self._driver_factory = driver_factory
        self._sleep = sleep
        self._today = today
        self._cache = TTLCache(cache_ttl_seconds)

    def get_menu(self) -> str:
        """오늘 학식 메뉴를 LLM 컨텍스트용 텍스트로 반환한다. 실패 시 CrawlerError.

        캐시 키에 날짜를 넣어, 자정이 지나면 전날 메뉴가 재사용되지 않는다.
        """
        return self._cache.get_or_load(self._today().isoformat(), self._fetch_uncached)

    def _fetch_uncached(self) -> str:
        driver = None
        try:
            driver = self._driver_factory()
            driver.get(MENU_URL)
            self._sleep(RENDER_WAIT_SECONDS)
            text = driver.find_element(By.TAG_NAME, "body").text
        except Exception as e:
            raise CrawlerError(f"크롤링 중 오류 발생: {e}") from e
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        return f"🍽️ [1947 학식 메뉴 요약]\n\n{text}"


if __name__ == "__main__":
    print("🚀 스마트 크롤러 단독 테스트를 시작합니다... (약 3초 소요)\n")
    print(MenuCrawler().get_menu())
