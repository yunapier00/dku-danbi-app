# 학식 크롤러(app/crawlers/menu.py)가 Selenium + 실제 Chromium 브라우저를 필요로 한다.
# Railway의 기본(Docker 없는) 빌드는 Python만 설치하고 브라우저는 설치하지 않으므로,
# 여기서 apt로 Chromium과 버전이 맞는 chromedriver를 함께 설치해둔다.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BINARY_PATH=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 운영 DB(/app/data)와 Chroma 인덱스 경로는 환경변수(DATABASE_URL, CHROMA_DB_PATH)로 그대로 설정한다.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
