import os
import time
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def get_dankook_menu():
    driver = None

    try:
        print("🚀 단국대학교 학식 크롤러 시작")

        chrome_options = Options()

        # Railway/Linux 서버용 옵션
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--window-size=1920,1080")

        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        if os.name == "nt":
            # ==========================================
            # Windows 로컬 환경
            # ==========================================
            print("💻 Windows 환경 감지")

            from webdriver_manager.chrome import ChromeDriverManager

            driver_path = ChromeDriverManager().install()

            print(f"ChromeDriver: {driver_path}")

            service = Service(driver_path)

        else:
            # ==========================================
            # Linux / Railway 환경
            # ==========================================
            print("🚂 Linux/Railway 환경 감지")

            # Chromium 탐색
            chromium_candidates = [
                shutil.which("chromium"),
                shutil.which("chromium-browser"),
                shutil.which("google-chrome"),
                shutil.which("google-chrome-stable"),

                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",

                "/nix/var/nix/profiles/default/bin/chromium",
                "/root/.nix-profile/bin/chromium",
            ]

            chromium_path = next(
                (
                    path
                    for path in chromium_candidates
                    if path and os.path.exists(path)
                ),
                None
            )

            # ChromeDriver 탐색
            chromedriver_candidates = [
                shutil.which("chromedriver"),

                "/usr/bin/chromedriver",
                "/usr/local/bin/chromedriver",

                "/nix/var/nix/profiles/default/bin/chromedriver",
                "/root/.nix-profile/bin/chromedriver",
            ]

            chromedriver_path = next(
                (
                    path
                    for path in chromedriver_candidates
                    if path and os.path.exists(path)
                ),
                None
            )

            print(f"🔍 Chromium 경로: {chromium_path}")
            print(f"🔍 ChromeDriver 경로: {chromedriver_path}")

            if not chromium_path:
                raise RuntimeError(
                    "❌ Chromium을 찾을 수 없습니다. "
                    "Railway에 Chromium이 설치되어 있는지 확인해주세요."
                )

            if not chromedriver_path:
                raise RuntimeError(
                    "❌ ChromeDriver를 찾을 수 없습니다. "
                    "Railway에 ChromeDriver가 설치되어 있는지 확인해주세요."
                )

            chrome_options.binary_location = chromium_path

            service = Service(chromedriver_path)

        # ==========================================
        # Selenium 실행
        # ==========================================

        print("🌐 Selenium WebDriver 실행")

        driver = webdriver.Chrome(
            service=service,
            options=chrome_options
        )

        url = "https://cms.dankook.ac.kr/web/kor/1947_commons"

        print(f"🌐 접속: {url}")

        driver.get(url)

        # 페이지 로딩 대기
        time.sleep(3)

        print(f"📄 현재 페이지: {driver.title}")

        # body 전체 텍스트 추출
        body = driver.find_element(
            By.TAG_NAME,
            "body"
        )

        text = body.text.strip()

        if not text:
            raise RuntimeError(
                "페이지에서 텍스트를 가져오지 못했습니다."
            )

        print("✅ 학식 메뉴 크롤링 성공")

        return (
            "🍽️ [1947 학식 메뉴 요약]\n\n"
            + text
        )

    except Exception as e:
        error_msg = f"Selenium 크롤러 구동 실패: {e}"

        print(f"❌ {error_msg}")

        raise Exception(error_msg) from e

    finally:
        if driver is not None:
            try:
                driver.quit()
                print("🧹 Selenium 종료")
            except Exception:
                pass


if __name__ == "__main__":
    print(
        " 크롤러 단독 테스트를 시작합니다...\n"
    )

    try:
        result = get_dankook_menu()
        print(result)

    except Exception as e:
        print(f"\n❌ 최종 실패: {e}")
