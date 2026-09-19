# 단비 (Danbi)

### 단국대학교 죽전캠퍼스 AI 어시스턴트

단비(Danbi)는 **단국대학교 죽전캠퍼스 학생들을 위한 AI 기반 학교 정보 챗봇**입니다.

학교생활에 필요한 학사 정보, 캠퍼스 시설 및 위치, 학식, 공지사항 등의 정보를 자연어로 질문하면 관련 데이터를 검색하고 AI가 이해하기 쉬운 형태로 답변합니다.

또한 웹 애플리케이션뿐만 아니라 **카카오톡 챗봇**을 통해서도 이용할 수 있도록 구현했습니다.

---

## 주요 기능

### 1. RAG 기반 학교 정보 검색

학교 관련 데이터를 벡터 데이터베이스에 저장하고 사용자의 질문과 관련성이 높은 문서를 검색하여 답변 생성에 활용합니다.

* Google Gemini Embedding 기반 문서 임베딩
* Chroma Vector Store
* BM25 키워드 검색
* BM25 + Vector Search Ensemble
* 검색된 문서를 기반으로 Gemini가 최종 답변 생성
* 한국어 자연어 질문 지원

```text
사용자 질문
    ↓
질문 유형 분류
    ↓
┌───────────────────────────────┐
│                               │
│ 학식 → 실시간 크롤링           │
│ 공지 → 실시간 크롤링           │
│ 일반 질문 → RAG 검색           │
│                               │
└───────────────────────────────┘
    ↓
검색 결과 / 크롤링 데이터
    ↓
Google Gemini
    ↓
최종 답변
```

---

### 2. Hybrid Retrieval

일반적인 질문에는 **BM25와 Vector Search를 결합한 Hybrid Search**를 사용합니다.

```text
                사용자 질문
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
      BM25 검색             Vector 검색
          │                     │
          └──────────┬──────────┘
                     ↓
              Ensemble Retriever
                (0.7 : 0.3)
                     ↓
                 관련 문서
                     ↓
                  Gemini
```

BM25는 정확한 키워드 검색에 강하고, Vector Search는 의미 기반 검색에 강하기 때문에 두 검색 방식을 결합하여 검색 성능을 보완하도록 구성했습니다.

---

### 3. 실시간 학식 조회

학식과 관련된 질문은 저장된 문서를 검색하는 대신 **실시간 크롤링**을 수행합니다.

예시:

```text
오늘 학식 뭐야?
학생식당 메뉴 알려줘
오늘 점심 뭐 나와?
```

질문을 `menu` 카테고리로 분류한 후 단국대학교 학식 데이터를 크롤링하고, 현재 날짜와 함께 Gemini에 전달하여 답변을 생성합니다.

---

### 4. 실시간 공지사항 조회

공지사항 관련 질문은 단국대학교 게시판을 직접 크롤링하여 최신 정보를 가져옵니다.

지원 대상에는 다음과 같은 게시판이 포함됩니다.

* 학사공지
* 모바일시스템공학과
* SW 관련 행사/공지

최신 게시글을 가져온 후 Gemini를 이용하여 학생이 이해하기 쉬운 형태로 전달합니다.

---

### 5. 자동 모닝 브리핑

APScheduler를 이용하여 정해진 시간에 최신 공지사항을 자동으로 확인합니다.

```text
매일 09:00
    ↓
최신 공지사항 크롤링
    ↓
Gemini 요약
    ↓
오늘의 단국대 모닝 브리핑 생성
    ↓
사용자 채팅 기록에 자동 등록
```

사용자가 직접 질문하지 않아도 채팅방에서 당일 주요 공지사항을 확인할 수 있도록 구현했습니다.

> 현재 개발/테스트 환경에서는 주기적인 테스트 실행을 위해 1분 간격 스케줄도 등록되어 있습니다. 실제 운영 환경에서는 매일 오전 9시 스케줄만 사용하는 것을 권장합니다.

---

### 6. Google OAuth 로그인

웹 서비스에서는 Google OAuth를 이용한 로그인을 지원합니다.

로그인 과정:

```text
사용자
  ↓
Google 로그인
  ↓
Google OAuth 인증
  ↓
이메일 / 사용자 정보 획득
  ↓
사용자 DB 확인 및 가입
  ↓
JWT 발급
  ↓
웹 클라이언트
```

발급된 JWT를 이용하여 사용자를 인증하며, 사용자별 채팅 기록을 별도로 관리합니다.

단국대학교 이메일 계정만 허용하도록 제한할 수 있는 로직도 구현되어 있습니다.

---

### 7. 사용자별 대화 기록

SQLAlchemy + SQLite를 이용하여 사용자별 대화 기록을 저장합니다.

저장되는 주요 정보:

* 사용자 ID
* 질문
* AI 답변
* 질문 카테고리
* 검색된 컨텍스트
* 의도 파악 시간
* 검색/크롤링 시간
* 답변 생성 시간
* 전체 처리 시간
* 생성 시간

이를 통해 사용자가 다시 접속했을 때 이전 대화 내용을 확인할 수 있습니다.

---

### 8. 카카오톡 챗봇 연동

웹 애플리케이션뿐만 아니라 카카오톡 챗봇 API를 통해 단비를 사용할 수 있도록 구현했습니다.

```text
카카오톡
    ↓
/api/kakao
    ↓
사용자 질문 및 사용자 ID 확인
    ↓
일일 사용량 확인
    ↓
Background Task
    ↓
RAG / 크롤링
    ↓
Gemini
    ↓
카카오 콜백
    ↓
답변 전송
```

카카오톡 사용자별로 질문 횟수를 관리하며 현재 설정된 일일 질문 제한은 **3회**입니다.

---

## 프로젝트 구조

```text
dku-danbi-app/
│
├── app/
│   └── data/
│       └── chroma_db_dd2/
│
├── backend/
│   ├── api_server.py
│   ├── crawler_1947.py
│   ├── crawler_notice.py
│   ├── database.py
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

---

## 기술 스택

### Backend

| 기술            | 용도              |
| ------------- | --------------- |
| Python        | 백엔드 및 AI 처리     |
| FastAPI       | REST API 서버     |
| LangChain     | RAG 파이프라인 구성    |
| Google Gemini | LLM / Embedding |
| Chroma        | Vector Database |
| BM25          | 키워드 기반 검색       |
| BeautifulSoup | 웹 크롤링           |
| Requests      | HTTP 요청         |
| SQLAlchemy    | ORM             |
| SQLite        | 사용자 및 대화 데이터 저장 |
| APScheduler   | 자동 브리핑 스케줄링     |
| JWT           | 사용자 인증          |
| Google OAuth  | 로그인             |
| Loguru        | 서버 로그 관리        |

### Frontend

| 기술             | 용도                          |
| -------------- | --------------------------- |
| React          | 사용자 인터페이스                   |
| Vite           | Frontend 개발 환경 및 빌드         |
| React Markdown | AI 답변 Markdown 렌더링          |
| Remark GFM     | GitHub Flavored Markdown 지원 |
| ChatScope      | 채팅 UI                       |

---

##  RAG 처리 구조

단비의 일반적인 질문 처리 과정은 다음과 같습니다.

### Step 1. 질문 분류

현재 질문의 유형을 확인합니다.

```text
학식 관련 질문
    → menu

공지사항 관련 질문
    → notice

그 외 학교 관련 질문
    → general
```

---

### Step 2. 데이터 검색

`general` 질문의 경우 BM25와 Vector Search를 함께 사용합니다.

```python
EnsembleRetriever(
    retrievers=[
        bm25_retriever,
        vectorstore.as_retriever(search_kwargs={"k": 3})
    ],
    weights=[0.7, 0.3]
)
```

검색 결과 중 상위 문서를 Gemini에 전달합니다.

---

### Step 3. 답변 생성

검색된 문서와 사용자 질문을 Prompt에 포함하여 Gemini가 답변을 생성합니다.

특히 다음과 같은 답변 규칙을 적용했습니다.

* 캠퍼스가 명시되지 않은 경우 죽전캠퍼스를 기본으로 가정
* 참고 정보에 천안/충남 정보가 있는 경우 천안캠퍼스로 판단
* 내부 검색용 Level 정보는 사용자에게 그대로 노출하지 않고 자연어로 변환

---

## 성능 측정

질문 처리 과정에서 각 단계별 소요 시간을 측정합니다.

```text
1. 의도 파악
        ↓
2. DB 검색 / 크롤링
        ↓
3. Gemini 답변 생성
        ↓
전체 처리 시간
```

예시 로그:

```text
==================================================
사용자 질문: 학생식당 오늘 메뉴 뭐야?

[성능 측정 리포트]
총 소요 시간: 2.31초

 ├─ 1. 의도 파악 (LLM) : 0.01초
 ├─ 2. DB 검색/크롤링  : 0.72초
 └─ 3. 답변 생성 (LLM) : 1.58초
==================================================
```

이를 통해 AI 응답 지연이 어느 단계에서 발생하는지 확인할 수 있도록 구성했습니다.

---

# Google OAuth 설정

Google Cloud Console에서 OAuth Client를 생성한 후 Redirect URI를 Backend 주소와 일치시켜야 합니다.


실제 서버에 배포하는 경우에는 배포된 Backend 주소로 변경해야 합니다.

---

# API

## Web Chat

```http
POST /api/web/chat
```

JWT 인증이 필요합니다.

Request:

```json
{
  "query": "도서관은 어디에 있어?",
  "history": ""
}
```

Response:

```json
{
  "answer": "도서관은 ...",
  "category": "general"
}
```

---

## Chat History

```http
GET /api/web/history
```

현재 로그인한 사용자의 최근 대화 기록을 반환합니다.

---

## Google Login

```http
GET /api/auth/login
```

Google OAuth 로그인 페이지로 이동합니다.

---

## Google OAuth Callback

```http
GET /api/auth/callback
```

Google 인증 완료 후 JWT를 발급합니다.

---

## Kakao Chatbot

```http
POST /api/kakao
```

카카오톡 챗봇의 사용자 질문을 받아 처리합니다.

---

# 🗄️ 데이터베이스

SQLite를 사용하며 주요 테이블은 다음과 같습니다.

### `users`

사용자 정보를 저장합니다.

```text
id
email
name
created_at
```

### `chat_history`

사용자의 질문과 AI 답변을 저장합니다.

```text
id
user_id
query
answer
category
created_at
retrieved_context
step1_time
step2_time
step3_time
total_time
```

---


# 💡 프로젝트의 특징

### 1. 단순 LLM 챗봇이 아닌 학교 특화 AI

일반적인 LLM에 학교 정보를 질문하는 방식이 아니라 학교 데이터를 별도로 구축하고 검색 결과를 기반으로 답변하도록 구성했습니다.

### 2. 정적 데이터와 실시간 데이터를 분리

```text
학교 시설 / 규정 / 캠퍼스 정보
        ↓
       RAG

학식 / 최신 공지사항
        ↓
    실시간 크롤링
```

정보의 특성에 따라 서로 다른 데이터 처리 방식을 적용했습니다.

### 3. 다양한 검색 방법 결합

BM25의 키워드 검색과 Vector Search의 의미 기반 검색을 결합하여 단일 검색 방식의 한계를 보완했습니다.

### 4. Web + Kakao 지원

하나의 AI 처리 로직을 기반으로 웹 애플리케이션과 카카오톡 챗봇에서 모두 사용할 수 있도록 API를 구성했습니다.

---

# 📷 서비스 화면

> 서비스 화면 및 실제 사용 예시는 프로젝트 진행에 따라 추가할 예정입니다.

```text
┌─────────────────────────────────────┐
│          단비 (Danbi)          로그아웃 │
├─────────────────────────────────────┤
│                                     │
│  안녕하세요! 단국대학교 죽전캠퍼스      │
│  AI 어시스턴트 단비입니다.             │
│                                     │
│                         사용자 질문   │
│                                     │
│  단비의 AI 답변                      │
│                                     │
├─────────────────────────────────────┤
│ 질문을 입력해주세요.              전송 │
└─────────────────────────────────────┘
```

---

# 👨‍💻 개발 목적

단국대학교 학생들이 학교생활에 필요한 정보를 보다 빠르고 편리하게 찾을 수 있도록 **학교 특화 AI 어시스턴트**를 개발하는 것을 목표로 했습니다.

특히 단순한 LLM 호출에 그치지 않고,

* 데이터 수집
* 데이터 검색
* Hybrid Retrieval
* LLM 기반 답변 생성
* 실시간 웹 크롤링
* 사용자 인증
* 대화 기록 관리
* 외부 플랫폼 연동
* 비동기 처리
* 자동화된 공지 브리핑

까지 하나의 서비스로 연결하는 것을 목표로 했습니다.

---

# 📚 주요 기술 키워드

```text
RAG
LLM
Google Gemini
LangChain
Hybrid Search
BM25
Vector Search
ChromaDB
FastAPI
React
Vite
Google OAuth
JWT
SQLAlchemy
SQLite
BeautifulSoup
Web Crawling
APScheduler
Kakao Chatbot
Docker
```

---

# 📄 License

This project was developed for educational and portfolio purposes.

학교 사이트에서 수집되는 정보 및 데이터의 저작권과 이용 정책은 각 원문 제공 기관의 정책을 따릅니다.
