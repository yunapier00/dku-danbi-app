

import os
import re
import time
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from sqlalchemy import func
from database import SessionLocal, ChatHistory, User


from fastapi.middleware.cors import CORSMiddleware

# 기존 랭체인 도구들
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from crawler_1947 import get_dankook_menu

from langchain_classic.retrievers import EnsembleRetriever

from collections import defaultdict

from datetime import datetime, date, timedelta, timezone
from loguru import logger
from jose import jwt
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, HTTPException, Depends

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
# rotation="00:00": 매일 자정에 새로운 로그 파일 생성
# retention="7 days": 7일이 지난 로그 파일은 자동 삭제
logger.add("logs/danbi_chat_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="INFO")

load_dotenv()
DB_PATH = "/app/data/chroma_db_dd2"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
# 토큰 감별 함수
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="유효하지 않은 토큰입니다. 다시 로그인해주세요.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 1. 우리가 만든 비밀키(JWT_SECRET_KEY)로 토큰 열어보기
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 2. DB에 진짜 있는 유저인지 최종 확인
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise credentials_exception
        return user # 검증이 완료된 유저 객체 반환
    finally:
        db.close()


def deliver_morning_briefing_to_db():
    print("⏰ [스케줄러] 아침 9시! 유저들의 채팅방에 브리핑을 전송합니다...")
    try:
        from crawler_notice import get_latest_notice
        briefing_text = get_latest_notice("모바일시스템공학과")
        summary_prompt = f"다음은 단국대학교 공지사항 Top3입니다. 학생들에게 핵심만 전달될 수 있도록 게시글 하나당 3~4줄로 친절하게 요약해주세요:\n\n{briefing_text}"
        summary_response = llm.invoke(summary_prompt)
        raw_content = getattr(summary_response, 'content', str(summary_response))
        if isinstance(raw_content, list):
            summarized_text = "".join([item.get("text", "") for item in raw_content if isinstance(item, dict)])
        else:
            summarized_text = str(raw_content)
        

        final_message = f"**📢 [오늘의 단국대 모닝 브리핑]**\n\n{summarized_text}"

        db = SessionLocal()
        try:
            users = db.query(User).all()
            count = 0
            for user in users:
                # 모든 유저의 채팅 기록에 단비의 브리핑 메시지를 강제 추가합니다.
                new_msg = ChatHistory(
                    user_id=user.email,      # 웹 채팅 엔드포인트와 동일하게 email을 id로 사용
                    query="[자동 브리핑]",     # 유저가 보낸 게 아니라는 표시
                    answer=final_message,
                    category="notice",
                    retrieved_context="스케줄러 자동 발송",
                    step1_time=0.0, step2_time=0.0, step3_time=0.0, total_time=0.0
                )
                db.add(new_msg)
                count += 1
            db.commit()
            print(f"✅ {count}명의 유저에게 브리핑 전송 완료!")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 브리핑 전송 에러: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # 🌟 일단 테스트할 때는 'cron' 대신 아래 줄을 써서 1분마다 작동하는지 확인해보세요!
    scheduler.add_job(deliver_morning_briefing_to_db, 'interval', minutes=1)
    
    # 실전용 (매일 아침 9시)
    scheduler.add_job(deliver_morning_briefing_to_db, 'cron', hour=9, minute=0)
    
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="단국대 AI 서버", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 테스트 단계에서만 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    history: str = ""  
    user_id: str = "default_user"  # 카카오톡 유저 식별자를 받기 위해 추가


print(" 서버  로딩 중...")
llm = ChatGoogleGenerativeAI(model="models/gemini-flash-latest", temperature=0)
embedding_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embedding_model, collection_name="campus_rules")

try:
    data = vectorstore.get()
    docs = [Document(page_content=t, metadata=m or {}) for t, m in zip(data['documents'], data['metadatas'])]
    
    def clean_tokenizer(text: str) -> List[str]:
        return re.sub(r"[^가-힣a-zA-Z0-9]", " ", text).split()
        
    bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=clean_tokenizer)
    bm25_retriever.k = 3
    print(" AI  로딩 완료!")
except Exception as e:
    print(f" DB 로딩 에러: {e}")


def classify_intent(query: str, llm) -> str:
    q_clean = query.replace(" ", "")
    menu_keywords = ["학식", "학생식당", "학생 식당"]
    if any(k in q_clean for k in menu_keywords): return "menu"

    notice_keywords = ["[공지]"]
    if any(k in q_clean for k in notice_keywords):
        return "notice" 
    # """    
    # prompt = f"질문 '{query}'의 의도를 분석하여 다음 중 하나를 단어만(영어) 출력하세요:\n1. rule\n2. general\n답변:"
    # try:
    #     res = llm.invoke(prompt)
    #     tag = res.content.strip().lower()
    #     if "rule" in tag: return "rule"
    #     return "general"
    # except: return "general"
    # """
    return "general"

def generate_answer(llm, context: str, query: str, history: str) -> str:
    prompt_template = PromptTemplate.from_template("""
    당신은 **단국대학교 죽전캠퍼스**의 AI 비서입니다.
    아래 [핵심 원칙]과 [답변 가이드]를 따르세요.                                  
    
    [핵심 원칙]
    1. **기본 가정:** 사용자가 질문에서 캠퍼스(죽전/천안)를 명시하지 않았다면 무조건 '죽전캠퍼스'로 간주하세요.
    2. **천안 식별:** [참고 정보]에 '충남' 또는 '천안' 명시 시에만 천안으로 판단하세요.
    3. 내부 기준 숨기기 : 제공된 정보의 [Level 1] ~ [Level 6] 같은 표기는 당신이 건물의 상대적 위치를 파악하기 위한 내부 좌표일 뿐입니다. 실제 답변을 작성할 때는 "Level 4에 위치해 있습니다"라는 말을 쓰지 말고, "상단부에 있습니다", "어느 건물 위쪽에 있습니다" 등 자연스러운 일상 용어로 번역해서 설명하세요.                                              
    
    [이전 대화 기록]
    {history}

    [참고 정보]
    {context}

    질문: {question}
    답변:
    """)
    final_prompt = prompt_template.format(context=context, question=query, history=history)
    response = llm.invoke(final_prompt)
    content = getattr(response, 'content', str(response))
    if isinstance(content, list): 
        return "".join([x.get('text', '') for x in content if isinstance(x, dict)])
    return str(content)

@app.get("/api/web/history")
def get_web_chat_history(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        # 현재 로그인한 유저(이메일)의 대화 기록을 오래된 순으로 50개 가져옵니다.
        history_records = db.query(ChatHistory).filter(
            ChatHistory.user_id == current_user.email
        ).order_by(ChatHistory.created_at.desc()).limit(50).all()
        history_records.reverse()

        chat_history = []
        for record in history_records:
            # 1. 유저가 보낸 질문
            if record.query and record.query != "[자동 브리핑]":
                chat_history.append({
                    "message": record.query,
                    "sender": "user",
                    "direction": "outgoing"
                })
            
            # 2. 단비가 보낸 답변 (브리핑 포함)
            if record.answer:
                chat_history.append({
                    "message": record.answer,
                    "sender": "Danbi",
                    "direction": "incoming"
                })

        return {"history": chat_history}
    finally:
        db.close()
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    query = request.query
    history = request.history
    user_id = request.user_id #



    total_start_time = time.time()

    step1_start = time.time()
    category = classify_intent(query, llm)
    step1_time = time.time() - step1_start
    
    context_text = ""
    source_info = ""


    step2_start = time.time()
    if category == "menu":
        try:
            crawled_data = get_dankook_menu()
            context_text = f"[오늘 날짜: {datetime.date.today()}]\n\n{crawled_data}"
        except Exception as e: # 🌟 에러의 정체를 변수 e로 잡습니다.
            context_text = "식단 정보를 가져오는데 실패했습니다."
            logger.error(f"❌ 학식 크롤링 에러 원인: {e}") # 로그 파일에 기록
            print(f"❌ 학식 크롤링 에러 원인: {e}") # 터미널 화면에 출력
    elif category == "notice":
            print("    실시간으로 최신 공지사항을 가져오는 중...")
            try:
                
                from crawler_notice import get_latest_notice
                
                
                department = "학사공지" # 기본값
                if "모바일시스템공학과" in query or "모시공" in query:
                    department = "모바일시스템공학과"
                elif "SW행사" in query or "소융대행사" in query:
                    department = "SW중심대학사업단"
                 
                
                crawled_data = get_latest_notice(department)
                context_text = f"[실시간 {department} 최신 공지사항]\n\n{crawled_data}"
                source_info = f"{department} 게시판 실시간 검색"
                
            except Exception as e:
                context_text = "공지사항을 가져오는데 실패했습니다."
                print(f"❌ 크롤링 에러: {e}")
    else:
        if category == "general":
            retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vectorstore.as_retriever(search_kwargs={"k": 3})],
                weights=[0.7, 0.3]
        )

        else:
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3, "filter": {"category": category}})
        
        found_docs = retriever.invoke(query)
        context_entries = []
        for doc in found_docs:
            src = doc.metadata.get("출처", "Unknown")

            other_metadata = {k: v for k, v in doc.metadata.items() if k != "출처"}
            meta_str = ", ".join([f"{k}: {v}" for k, v in other_metadata.items()])

            content = doc.page_content.replace("\n", " ")
            if meta_str:
                entry = f"📄 [파일명: {src} | 메타정보: {meta_str}]\n내용: {content}"
            else:
                entry = f"📄 [파일명: {src}]\n내용: {content}"

            context_entries.append(entry)
        context_text = "\n\n---\n\n".join(context_entries)
    step2_time = time.time() - step2_start

   
    step3_start = time.time()
    answer = generate_answer(llm, context_text, query, history)
    step3_time = time.time() - step3_start
    
    
    total_time = time.time() - total_start_time

    
    print("\n" + "="*50)
    print(f" 사용자 질문: {query}")
    print(f" 라우터가 판단한 의도(Category): [{category.upper()}]")
    
    print("📚 [검색된 문서 출처]")
    if category == "menu" or category == "notice":
        print(" └─ 🌐 (실시간 크롤링) 식단 데이터")
    else:
        
        if not found_docs:
            print(" └─ ⚠️ 검색된 문서가 없습니다.")
        else:
            for i, doc in enumerate(found_docs):
                src = doc.metadata.get("출처", "Unknown")
                print(f" └─ 📄 {i+1}순위 문서: {src}")
    print("\n" + "="*50)
    print(f"🙋 사용자 질문: {query}")
    print(f"⏱️ [성능 측정 리포트] 총 소요 시간: {total_time:.2f}초")
    print(f" ├─ 1. 의도 파악 (LLM) : {step1_time:.2f}초")
    print(f" ├─ 2. DB 검색/크롤링  : {step2_time:.2f}초")
    print(f" └─ 3. 답변 생성 (LLM) : {step3_time:.2f}초")
    print("="*50 + "\n")


    db = SessionLocal()
    try:
        new_log = ChatHistory(
            user_id=user_id, 
            query=query,
            answer=answer,
            category=category,

            retrieved_context=context_text,         # 검색된 문서 내용 또는 크롤링 텍스트
            step1_time=round(step1_time, 2),        # 의도 파악 시간 (소수점 2자리)
            step2_time=round(step2_time, 2),        # 검색/크롤링 시간
            step3_time=round(step3_time, 2),        # 답변 생성 시간
            total_time=round(total_time, 2)         # 전체 수행 시간
        )
        db.add(new_log)
        db.commit()
    finally:
        db.close()

    return {
        "answer": answer,
        "category": category 
    }

from fastapi import Request, BackgroundTasks
#import requests
import httpx
import asyncio

async def process_and_send_callback(user_message: str, callback_url: str , user_id: str):
    
    try:
        answer, category = await asyncio.to_thread(generate_chat_response, user_message, "", user_id)

        payload = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": answer
                        }
                    }
                ]
            }
        }


        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=payload)

        logger.info(f"카카오 콜백 비동기 전송 성공 - User ID: {user_id}")
        
    except Exception as e:
        logger.info(f"카카오 콜백 비동기 전송 성공 - User ID: {user_id}")
        error_payload = {
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": "서버 내부 오류가 발생했습니다."}}]}
        }
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=error_payload)



DAILY_LIMIT = 3
@app.post("/api/kakao")
async def kakao_chat(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        
        user_message = body["userRequest"]["utterance"]
        user_id = body["userRequest"]["user"]["id"] 
        
        # 1. DB 세션을 열어 오늘 날짜 기준으로 해당 유저의 질문 횟수를 카운트
        db = SessionLocal()
        try:
            today = date.today()
            daily_count = db.query(ChatHistory).filter(
                ChatHistory.user_id == user_id,
                func.date(ChatHistory.created_at) == today 
            ).count()
        finally:
            db.close()

        # 2. 제한 횟수를 초과했는지 검사
        if daily_count >= DAILY_LIMIT:
            return {
                "version": "2.0",
                "template": {
                    "outputs": [
                        {
                            "simpleText": {
                                "text": f"하루 질문 한도 {DAILY_LIMIT}회 초과\n내일 다시 찾아와주세요!"
                            }
                        }
                    ]
                }
            }        

        # 3. 통과했다면 콜백 처리를 진행
        callback_url = body["userRequest"].get("callbackUrl")
        
        if callback_url:
            background_tasks.add_task(process_and_send_callback, user_message, callback_url, user_id)
            return {"useCallback": True}
            
        else:
            return {
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "콜백 URL 에러 "}}]
                }
            }

    except Exception as e:
        logger.error(f"❌ 카카오 API 수신 에러: {e}")
        return {"useCallback": False}



GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET= os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI= os.getenv("GOOGLE_REDIRECT_URI")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

@app.get("/api/auth/login")
def login_via_google():
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid email profile"
    )
    return RedirectResponse(url=google_auth_url)






@app.get("/api/auth/callback")
async def google_callback(code: str):
    # [Step 1] 구글이 준 'code'를 다시 구글에 주고 '액세스 토큰'으로 교환 (비동기 httpx 사용!)
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_REDIRECT_URI,
    }
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=token_data)
        access_token = token_res.json().get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="Google 인증 실패")

        # [Step 2] 구글 액세스 토큰을 이용해 유저의 실제 정보(이메일, 이름) 가져오기
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        userinfo_res = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        user_info = userinfo_res.json()
        
    email = user_info.get("email")
    name = user_info.get("name")

    # [Step 3] 🛡️ 단국대 학생 방어막 (외부인 차단 로직)
    # 아직 개발 테스트 중이라면 아래 두 줄은 주석(#) 처리 해두셔도 됩니다.
    # if not email.endswith("@dankook.ac.kr"):
    #     #raise HTTPException(status_code=403, detail="단국대학교 학생(@dankook.ac.kr)만 이용할 수 있습니다.")
    #     frontend_url = "http://localhost:5173"
    #     return RedirectResponse(url=f"{frontend_url}/?error=invalid_domain")

    # [Step 4] 데이터베이스에 유저 저장 (처음 온 유저면 가입, 있던 유저면 통과)
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.email == email).first()
        if not db_user:
            # 새로운 유저 생성
            db_user = User(email=email, name=name)
            db.add(db_user)
            db.commit()
    finally:
        db.close()

    # [Step 5] 🎫 우리 서버만의 JWT 토큰(자유이용권) 구워서 발급하기
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expire} # 토큰 안에 '이메일'과 '만료시간'을 숨겨 넣음
    
    custom_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # 최종적으로 프론트엔드(클라이언트)에게 토큰을 전달

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/?token={custom_jwt}")


@app.post("/api/web/chat")
def web_chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_user)):
    # 🔒 JWT 토큰이 검증된 사람만 여기까지 들어올 수 있음
    # 파라미터로 구글 이메일(current_user.email)을 넘겨 DB에 기록되게 합니다.
    answer, category = generate_chat_response(request.query, request.history, current_user.email)
    
    return {
        "answer": answer,
        "category": category 
    }



def generate_chat_response(query: str, history: str, user_id: str):
    total_start_time = time.time()
    
    # [의도 파악]
    step1_start = time.time()
    category = classify_intent(query, llm)
    step1_time = time.time() - step1_start
    
    context_text = ""
    
    # [RAG 검색 및 크롤링]
    step2_start = time.time()
    if category == "menu":
        try:
            crawled_data = get_dankook_menu()
            context_text = f"[오늘 날짜: {date.today()}]\n\n{crawled_data}"
        except Exception as e:
            context_text = "식단 정보를 가져오는데 실패했습니다."
            logger.error(f"❌ 학식 크롤링 에러 원인: {e}") # 로그 파일에 기록
            print(f"❌ 학식 크롤링 에러 원인: {e}") # 터미널 화면에 출력
    elif category == "notice":
        try:
            from crawler_notice import get_latest_notice
            department = "학사공지" # 기본값
            if "모바일시스템공학과" in query or "모시공" in query: department = "모바일시스템공학과"
            elif "SW행사" in query or "소융대행사" in query: department = "SW중심대학사업단"
            
            crawled_data = get_latest_notice(department)
            context_text = f"[실시간 {department} 최신 공지사항]\n\n{crawled_data}"
        except Exception as e:
            context_text = "공지사항을 가져오는데 실패했습니다."
            logger.error(f"❌ 크롤링 에러: {e}")
    else:
        if category == "general":
            # 🛡️ BM25 방어 로직 적용
            if bm25_retriever is not None:
                retriever = EnsembleRetriever(
                    retrievers=[bm25_retriever, vectorstore.as_retriever(search_kwargs={"k": 3})],
                    weights=[0.7, 0.3]
                )
            else:
                retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        else:
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3, "filter": {"category": category}})
        
        found_docs = retriever.invoke(query)
        context_entries = []
        for doc in found_docs:
            src = doc.metadata.get("출처", "Unknown")
            other_metadata = {k: v for k, v in doc.metadata.items() if k != "출처"}
            meta_str = ", ".join([f"{k}: {v}" for k, v in other_metadata.items()])
            content = doc.page_content.replace("\n", " ")
            if meta_str:
                entry = f"📄 [파일명: {src} | 메타정보: {meta_str}]\n내용: {content}"
            else:
                entry = f"📄 [파일명: {src}]\n내용: {content}"
            context_entries.append(entry)
        context_text = "\n\n---\n\n".join(context_entries)
    step2_time = time.time() - step2_start

    # [답변 생성]
    step3_start = time.time()
    answer = generate_answer(llm, context_text, query, history)
    step3_time = time.time() - step3_start
    total_time = time.time() - total_start_time

    # DB 저장
    db = SessionLocal()
    try:
        new_log = ChatHistory(
            user_id=user_id, 
            query=query,
            answer=answer,
            category=category,
            retrieved_context=context_text,
            step1_time=round(step1_time, 2),
            step2_time=round(step2_time, 2),
            step3_time=round(step3_time, 2),
            total_time=round(total_time, 2)
        )
        db.add(new_log)
        db.commit() 
    except Exception as e:
        db.rollback() #  에러 시 원상복구
        logger.error(f"❌ DB 저장 트랜잭션 실패 및 롤백됨: {e}")
    finally:
        db.close()

    return answer, category