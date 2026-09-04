import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

def get_dankook_menu():

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        if os.name == 'nt':
            # 1. 윈도우 환경
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        else:
            from webdriver_manager.chrome import ChromeDriverManager
            from webdriver_manager.core.os_manager import ChromeType
            chrome_options.binary_location = "/usr/bin/chromium"
            
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())

        driver = webdriver.Chrome(service=service, options=chrome_options)
        url = "https://cms.dankook.ac.kr/web/kor/1947_commons"
        driver.get(url)
        time.sleep(3)
        text = driver.find_element(By.TAG_NAME, "body").text
        driver.quit()

        return f"🍽️ [1947 학식 메뉴 요약]\n\n{text}"

    except Exception as e:
        return f"❌ 크롤링 중 오류 발생: {e}"

if __name__ == "__main__":
    print("🚀 스마트 크롤러 단독 테스트를 시작합니다... (약 3초 소요)\n")
    print(get_dankook_menu())