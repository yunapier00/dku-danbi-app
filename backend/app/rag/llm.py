from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.core.config import Settings


def build_llm(settings: Settings) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=settings.llm_model, temperature=0)


def build_embeddings(settings: Settings) -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(model=settings.embedding_model)


def extract_text(response: Any) -> str:
    """LLM 응답의 content 를 문자열로 꺼낸다. content 가 파트 리스트이면 dict 의 text 만 이어 붙인다."""
    content = getattr(response, "content", str(response))
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)
