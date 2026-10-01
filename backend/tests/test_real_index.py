"""실제 chroma_db_dd3 로 조립된 검색기를 확인한다. (임베딩 API 는 호출하지 않는다.)

BM25 구축 실패는 이제 예외 없이 벡터 검색만 쓰도록 폴백되므로, 배포 전에 이 테스트로 조용한 폴백을 잡는다.
"""


def test_real_chroma_index_builds_bm25(api):
    assert api.retriever.bm25 is not None, "BM25 인덱스 구축에 실패해 벡터 검색만 쓰고 있습니다. 로그를 확인하세요."


def test_real_bm25_index_returns_relevant_documents_offline(api):
    docs = api.retriever.bm25.invoke("도서관")

    assert 0 < len(docs) <= 3
    assert all(doc.page_content for doc in docs)
    assert any("도서관" in doc.page_content for doc in docs)
    assert all("출처" in doc.metadata for doc in docs)


def test_real_index_settings_are_applied(api):
    assert api.retriever.bm25.k == 3
