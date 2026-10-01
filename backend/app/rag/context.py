"""LLM 프롬프트의 [참고 정보] 에 들어갈 컨텍스트 문자열을 만든다."""
from datetime import date
from typing import Iterable

from langchain_core.documents import Document

MENU_FAILURE_CONTEXT = "식단 정보를 가져오는데 실패했습니다."
NOTICE_FAILURE_CONTEXT = "공지사항을 가져오는데 실패했습니다."

_SEPARATOR = "\n\n---\n\n"


def format_documents(docs: Iterable[Document]) -> str:
    entries = []
    for doc in docs:
        src = doc.metadata.get("출처", "Unknown")
        other_metadata = {k: v for k, v in doc.metadata.items() if k != "출처"}
        meta_str = ", ".join(f"{k}: {v}" for k, v in other_metadata.items())
        content = doc.page_content.replace("\n", " ")
        if meta_str:
            entries.append(f"📄 [파일명: {src} | 메타정보: {meta_str}]\n내용: {content}")
        else:
            entries.append(f"📄 [파일명: {src}]\n내용: {content}")
    return _SEPARATOR.join(entries)


def format_menu_context(menu_text: str, today: date) -> str:
    return f"[오늘 날짜: {today}]\n\n{menu_text}"


def format_notice_context(board_name: str, notice_text: str) -> str:
    return f"[실시간 {board_name} 최신 공지사항]\n\n{notice_text}"
