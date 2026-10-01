"""의도 분류 / 컨텍스트 / 검색 / ChatService 처리 흐름의 동작을 고정한다."""
from datetime import date
from types import SimpleNamespace
from typing import Any, List

import pytest
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.crawlers.errors import CrawlerError
from app.rag.answer import generate_answer
from app.rag.context import format_documents
from app.rag.intent import classify_intent
from app.rag.llm import extract_text
from app.rag.retriever import RagRetriever, build_bm25
from conftest import FakeLLM, FakeRetriever


# ---------------------------------------------------------------- 의도 분류
@pytest.mark.parametrize(
    "query, expected",
    [
        ("오늘 학식 뭐야?", "menu"),
        ("학생식당 메뉴 알려줘", "menu"),
        ("학생 식당 어때", "menu"),  # 공백을 제거하고 비교하므로 "학생 식당" 도 매치된다
        ("[공지] 알려줘", "notice"),
        ("도서관은 어디에 있어?", "general"),
        ("공지사항 알려줘", "general"),  # 대괄호가 없으면 notice로 분류되지 않는다
        ("", "general"),
    ],
)
def test_classify_intent(query, expected):
    assert classify_intent(query) == expected


def test_classify_intent_menu_has_priority_over_notice():
    assert classify_intent("[공지] 학식") == "menu"


# ---------------------------------------------------------------- LLM 응답 / 프롬프트
def test_extract_text_from_string_and_parts():
    assert extract_text(SimpleNamespace(content="문자열")) == "문자열"
    assert extract_text(SimpleNamespace(content=[{"text": "가"}, {"text": "나"}, "무시", {"no_text": 1}])) == "가나"
    assert extract_text("content 속성이 없는 값") == "content 속성이 없는 값"


def test_generate_answer_fills_prompt_and_returns_string_content():
    llm = FakeLLM("답변입니다")
    answer = generate_answer(llm, "참고내용XYZ", "질문내용ABC", "이전대화QQQ")

    assert answer == "답변입니다"
    prompt = llm.prompts[0]
    assert "참고내용XYZ" in prompt
    assert "질문내용ABC" in prompt
    assert "이전대화QQQ" in prompt
    assert "죽전캠퍼스" in prompt


def test_generate_answer_does_not_reinterpret_braces_in_context():
    llm = FakeLLM()
    generate_answer(llm, "{question} {history}", "Q", "H")
    assert "{question} {history}" in llm.prompts[0]


# ---------------------------------------------------------------- 문서 포맷
DOC_A = Document(page_content="도서관은 중앙도서관 1층\n입구 옆에 있다", metadata={"출처": "campus.pdf", "캠퍼스": "죽전"})
DOC_B = Document(page_content="학생식당 운영시간 안내", metadata={"출처": "food.pdf"})
DOC_C = Document(page_content="기숙사 신청 방법", metadata={})

ENTRY_A = "📄 [파일명: campus.pdf | 메타정보: 캠퍼스: 죽전]\n내용: 도서관은 중앙도서관 1층 입구 옆에 있다"
ENTRY_B = "📄 [파일명: food.pdf]\n내용: 학생식당 운영시간 안내"
ENTRY_C = "📄 [파일명: Unknown]\n내용: 기숙사 신청 방법"


def test_format_documents():
    assert format_documents([DOC_A, DOC_B, DOC_C]) == f"{ENTRY_A}\n\n---\n\n{ENTRY_B}\n\n---\n\n{ENTRY_C}"
    assert format_documents([]) == ""


# ---------------------------------------------------------------- 하이브리드 검색
class FakeVectorRetriever(BaseRetriever):
    docs: List[Any] = []

    def _get_relevant_documents(self, query, *, run_manager=None):
        return list(self.docs)


class FakeVectorStore:
    def __init__(self, docs, get_result=None, get_error=None):
        self.docs = docs
        self.as_retriever_calls = []
        self._get_result = get_result
        self._get_error = get_error

    def as_retriever(self, **kwargs):
        self.as_retriever_calls.append(kwargs)
        return FakeVectorRetriever(docs=self.docs)

    def get(self):
        if self._get_error:
            raise self._get_error
        return self._get_result


def make_bm25(docs):
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = 3
    return retriever


def test_retriever_combines_bm25_and_vector_results():
    vs = FakeVectorStore([DOC_B, DOC_C])
    retriever = RagRetriever(vs, make_bm25([DOC_A]), k=3, bm25_weight=0.7, vector_weight=0.3)

    contents = {d.page_content for d in retriever.retrieve("도서관")}

    assert vs.as_retriever_calls == [{"search_kwargs": {"k": 3}}]
    assert contents == {DOC_A.page_content, DOC_B.page_content, DOC_C.page_content}


def test_retriever_uses_vector_only_when_bm25_is_missing():
    vs = FakeVectorStore([DOC_B])
    retriever = RagRetriever(vs, None, k=3, bm25_weight=0.7, vector_weight=0.3)

    assert [d.page_content for d in retriever.retrieve("식당")] == [DOC_B.page_content]


def test_build_bm25_from_vectorstore_documents():
    # BM25 는 문서가 너무 적으면 IDF 가 0 이 되므로 여러 건을 넣는다.
    vs = FakeVectorStore(
        [],
        get_result={
            "documents": ["도서관 위치 안내", "기숙사 신청 방법", "장학금 신청 기간", "수강 신청 일정"],
            "metadatas": [{"출처": "a"}, None, {}, {}],
        },
    )

    bm25 = build_bm25(vs, k=2)

    assert bm25.k == 2
    assert bm25.invoke("도서관")[0].page_content == "도서관 위치 안내"
    assert bm25.invoke("도서관")[0].metadata == {"출처": "a"}


def test_build_bm25_returns_none_instead_of_crashing_when_index_cannot_be_built():
    """버그 수정: 예전에는 실패 시 bm25_retriever 가 정의되지 않아 첫 검색에서 NameError 가 났다."""
    vs = FakeVectorStore([], get_error=RuntimeError("chroma broken"))

    assert build_bm25(vs, k=3) is None


# ---------------------------------------------------------------- ChatService: general
def test_general_question_uses_retriever_and_formats_context(make_chat_service, fake_llm, all_chat_rows):
    retriever = FakeRetriever([DOC_A, DOC_B])
    service = make_chat_service(retriever=retriever)

    answer, category = service.respond("도서관", "이전기록", "user-1")

    assert (answer, category) == ("가짜 답변", "general")
    assert retriever.queries == ["도서관"]
    prompt = fake_llm.prompts[0]
    assert f"{ENTRY_A}\n\n---\n\n{ENTRY_B}" in prompt
    assert "이전기록" in prompt
    assert ENTRY_A in all_chat_rows()[0].retrieved_context


# ---------------------------------------------------------------- ChatService: menu
def test_menu_question_prepends_today_and_uses_crawler(make_chat_service, fake_llm, all_chat_rows):
    service = make_chat_service(fetch_menu=lambda: "오늘의 메뉴: 김치찌개", today=lambda: date(2026, 9, 21))

    _, category = service.respond("오늘 학식 뭐야?", "", "user-1")

    expected_context = "[오늘 날짜: 2026-09-21]\n\n오늘의 메뉴: 김치찌개"
    assert category == "menu"
    assert expected_context in fake_llm.prompts[0]
    assert all_chat_rows()[0].retrieved_context == expected_context


@pytest.mark.parametrize("error", [RuntimeError("selenium down"), CrawlerError("크롤링 중 오류 발생: boom")])
def test_menu_failure_becomes_failure_context_and_error_text_never_reaches_llm(make_chat_service, fake_llm, error):
    def boom():
        raise error

    service = make_chat_service(fetch_menu=boom)

    _, category = service.respond("학식", "", "user-1")

    assert category == "menu"
    assert "식단 정보를 가져오는데 실패했습니다." in fake_llm.prompts[0]
    assert str(error) not in fake_llm.prompts[0]


# ---------------------------------------------------------------- ChatService: notice
@pytest.mark.parametrize(
    "query, board",
    [
        ("[공지] 알려줘", "학사공지"),
        ("[공지] 모바일시스템공학과", "모바일시스템공학과"),
        ("[공지] 모시공 소식", "모바일시스템공학과"),
        ("[공지] SW행사", "SW대회/행사"),
        ("[공지] 소융대행사", "SW대회/행사"),
    ],
)
def test_notice_board_routing(make_chat_service, fake_llm, query, board):
    calls = []

    def fetch_notice(name):
        calls.append(name)
        return f"{name}-공지본문"

    service = make_chat_service(fetch_notice=fetch_notice)

    _, category = service.respond(query, "", "user-1")

    assert category == "notice"
    assert calls == [board]
    assert f"[실시간 {board} 최신 공지사항]\n\n{board}-공지본문" in fake_llm.prompts[0]


@pytest.mark.parametrize("error", [RuntimeError("down"), CrawlerError("서버 연결 중 오류가 발생했습니다: x")])
def test_notice_failure_becomes_failure_context_and_error_text_never_reaches_llm(make_chat_service, fake_llm, error):
    def boom(board):
        raise error

    service = make_chat_service(fetch_notice=boom)

    service.respond("[공지]", "", "user-1")

    assert "공지사항을 가져오는데 실패했습니다." in fake_llm.prompts[0]
    assert str(error) not in fake_llm.prompts[0]


# ---------------------------------------------------------------- ChatService: 저장
def test_chat_is_persisted_with_rounded_timings(make_chat_service, all_chat_rows):
    # respond 는 timer 를 8번 호출한다: total 시작, (step1 시작/끝), (step2 시작/끝), (step3 시작/끝), total 끝
    ticks = iter(i * 0.123456 for i in range(8))
    service = make_chat_service(timer=lambda: next(ticks))

    service.respond("학식", "", "kakao-user-9")

    (row,) = all_chat_rows()
    assert row.user_id == "kakao-user-9"
    assert row.query == "학식"
    assert row.answer == "가짜 답변"
    assert row.category == "menu"
    assert (row.step1_time, row.step2_time, row.step3_time, row.total_time) == (0.12, 0.12, 0.12, 0.86)


def test_db_failure_is_rolled_back_and_answer_still_returned(make_chat_service, monkeypatch):
    class BrokenSession:
        rolled_back = False
        closed = False

        def add(self, obj):
            pass

        def commit(self):
            raise RuntimeError("disk full")

        def rollback(self):
            BrokenSession.rolled_back = True

        def close(self):
            BrokenSession.closed = True

    from app.db import session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", lambda: BrokenSession())
    service = make_chat_service()

    answer, category = service.respond("학식", "", "user-1")

    assert (answer, category) == ("가짜 답변", "menu")
    assert BrokenSession.rolled_back and BrokenSession.closed
