class CrawlerError(Exception):
    """크롤링 실패. 오류 문자열을 결과처럼 반환하지 않고 예외로 알린다 (LLM 컨텍스트 오염 방지)."""
