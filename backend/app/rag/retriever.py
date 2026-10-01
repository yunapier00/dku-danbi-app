"""Chroma(벡터) + BM25(키워드) 하이브리드 검색."""
import re
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from loguru import logger

from app.core.config import Settings


def clean_tokenizer(text: str) -> List[str]:
    return re.sub(r"[^가-힣a-zA-Z0-9]", " ", text).split()


class RagRetriever:
    """BM25 가 있으면 BM25 + 벡터 앙상블, 없으면 벡터 검색만 사용한다."""

    def __init__(self, vectorstore, bm25_retriever: Optional[BM25Retriever], *, k: int, bm25_weight: float, vector_weight: float):
        self.bm25 = bm25_retriever
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": k})
        if bm25_retriever is not None:
            self._retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=[bm25_weight, vector_weight],
            )
        else:
            self._retriever = vector_retriever

    def retrieve(self, query: str) -> List[Document]:
        return self._retriever.invoke(query)


def build_bm25(vectorstore, k: int) -> Optional[BM25Retriever]:
    """벡터 DB 의 전체 문서로 BM25 인덱스를 만든다. 실패하면 None (벡터 검색만 사용)."""
    try:
        data = vectorstore.get()
        docs = [Document(page_content=text, metadata=meta or {}) for text, meta in zip(data["documents"], data["metadatas"])]
        bm25 = BM25Retriever.from_documents(docs, preprocess_func=clean_tokenizer)
        bm25.k = k
        return bm25
    except Exception as e:
        logger.error(f"❌ BM25 인덱스 생성 실패 (벡터 검색만 사용합니다): {e}")
        return None


def build_retriever(settings: Settings, embedding_model) -> RagRetriever:
    vectorstore = Chroma(
        persist_directory=settings.chroma_db_path,
        embedding_function=embedding_model,
        collection_name=settings.chroma_collection,
    )
    return RagRetriever(
        vectorstore,
        build_bm25(vectorstore, settings.retriever_k),
        k=settings.retriever_k,
        bm25_weight=settings.bm25_weight,
        vector_weight=settings.vector_weight,
    )
