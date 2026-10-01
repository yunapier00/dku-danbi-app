"""학교 게시판 공지 크롤러.

- parse_* : HTML 문자열만 다루는 순수 함수 (네트워크 없이 테스트 가능)
- NoticeCrawler : HTTP 요청 + 캐시. 실패는 CrawlerError 로 알린다.
- format_notices : LLM 컨텍스트로 넘기는 텍스트 형식 (이전 크롤러의 출력과 동일)
"""
import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.crawlers.boards import BOARDS, NoticeBoard
from app.crawlers.cache import TTLCache
from app.crawlers.errors import CrawlerError

NOTICE_LIMIT = 3  # 속도와 LLM 토큰 절약을 위해 상위 3개만 가져온다.
LIST_TIMEOUT = 5
DETAIL_TIMEOUT = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"

BODY_UNAVAILABLE = "본문을 가져올 수 없습니다."
BODY_NOT_FOUND = "본문 영역을 찾지 못했습니다."
BODY_TIMEOUT = "본문 접속 지연."

_VIEW_MESSAGE = re.compile(r"viewMessage\(\s*(\d+)")
# 상세 페이지 본문 셀렉터. fr-view 가 없는 게시판(SW)은 표의 행으로 폴백한다.
_BODY_VIEW = "table.table.mb-3 div.fr-view"
_BODY_LAST_ROW = "table.table.mb-3 tbody tr:last-child"
_BODY_TOP_ROWS = "table.table.mb-3 > tbody > tr"
_BODY_TABLE = "table.table.mb-3"
_COMMENT_ROW = "댓글"  # 표의 마지막 행이 댓글 머리글인 게시판이 있다.


@dataclass(frozen=True)
class Notice:
    title: str
    body: str


# ---------------------------------------------------------------- 파싱 (순수 함수)
def parse_notice_list(html: str, board: NoticeBoard) -> List[Tuple[str, Optional[str]]]:
    """목록 HTML에서 (제목, 게시글 ID) 목록을 순서대로 반환한다. 제목이 빈 행은 건너뛴다."""
    rows = BeautifulSoup(html, "html.parser").select(board.row_selector)
    if not rows:
        raise CrawlerError(f"'{board.name}' 게시판의 HTML 구조가 변경된 것 같습니다.")

    entries: List[Tuple[str, Optional[str]]] = []
    for row in rows:
        title_elem = row.select_one(board.title_selector)
        if not title_elem:
            continue
        title = title_elem.text.strip()
        if not title:
            continue
        match = _VIEW_MESSAGE.search(title_elem.get("onclick", ""))
        entries.append((title, match.group(1) if match else None))
    return entries


def _text(element) -> str:
    return " ".join(element.text.split())


def parse_notice_body(html: str) -> str:
    """상세 페이지 HTML에서 본문 텍스트를 뽑는다. 못 찾으면 BODY_NOT_FOUND.

    1) fr-view 영역
    2) 표의 마지막 행 (문서 순서상 첫 번째 tr:last-child, 즉 바깥쪽 행. 중첩 표가 있어도 본문 전체가 나온다)
    3) 2)가 '댓글' 머리글 행이면, 그 앞의 최상위 행 (SW 게시판)
    4) 표 전체
    """
    soup = BeautifulSoup(html, "html.parser")

    view = soup.select_one(_BODY_VIEW)
    if view is not None:
        return _text(view)

    for row in soup.select(_BODY_LAST_ROW):
        if _text(row) != _COMMENT_ROW:
            return _text(row)

    rows = [row for row in soup.select(_BODY_TOP_ROWS) if _text(row) != _COMMENT_ROW]
    if rows:
        return _text(rows[-1])

    table = soup.select_one(_BODY_TABLE)
    if table is not None:
        return _text(table)
    return BODY_NOT_FOUND


def format_notices(board_name: str, notices: List[Notice]) -> str:
    text = f"📢 [{board_name} 최신 공지사항 Top {NOTICE_LIMIT}]\n\n"
    for number, notice in enumerate(notices, start=1):
        text += f"{number}. 제목: {notice.title}\n   내용 : {notice.body}\n\n"
    return text


# ---------------------------------------------------------------- 크롤러
class NoticeCrawler:
    def __init__(
        self,
        *,
        http_get: Callable = requests.get,
        verify_ssl: bool = True,
        cache_ttl_seconds: float = 300,
        boards: Optional[Dict[str, NoticeBoard]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._http_get = http_get
        self._verify_ssl = verify_ssl
        self._boards = BOARDS if boards is None else boards
        self._cache = TTLCache(cache_ttl_seconds, clock)
        if not verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get_text(self, board_name: str) -> str:
        """게시판의 최신 공지를 LLM 컨텍스트용 텍스트로 반환한다. 실패 시 CrawlerError."""
        return format_notices(board_name, self.fetch(board_name))

    def fetch(self, board_name: str) -> List[Notice]:
        board = self._boards.get(board_name)
        if board is None:
            raise CrawlerError(f"아직 '{board_name}'의 공지사항은 연동되지 않았습니다.")
        return self._cache.get_or_load(board_name, lambda: self._fetch_uncached(board))

    def _fetch_uncached(self, board: NoticeBoard) -> List[Notice]:
        headers = {"User-Agent": USER_AGENT}
        try:
            response = self._http_get(board.list_url, headers=headers, verify=self._verify_ssl, timeout=LIST_TIMEOUT)
            response.raise_for_status()
        except Exception as e:
            raise CrawlerError(f"{board.name} 서버 연결 중 오류가 발생했습니다: {e}") from e

        entries = parse_notice_list(response.text, board)[:NOTICE_LIMIT]
        return [Notice(title=title, body=self._fetch_body(board, post_id, headers)) for title, post_id in entries]

    def _fetch_body(self, board: NoticeBoard, post_id: Optional[str], headers: dict) -> str:
        if post_id is None:
            return BODY_UNAVAILABLE
        try:
            response = self._http_get(
                board.view_base_url + post_id, headers=headers, verify=self._verify_ssl, timeout=DETAIL_TIMEOUT
            )
            return parse_notice_body(response.text)
        except Exception:
            return BODY_TIMEOUT


if __name__ == "__main__":
    print("🚀 크롤러 단독 테스트를 시작합니다...\n")
    print(NoticeCrawler().get_text("학사공지"))
