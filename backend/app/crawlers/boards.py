"""공지 게시판 설정과 질문 → 게시판 라우팅. 게시판 이름 문자열의 단일 출처."""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class NoticeBoard:
    name: str
    list_url: str
    row_selector: str
    title_selector: str
    view_base_url: str  # 상세 페이지 URL 접두어. 게시글 ID를 뒤에 붙여 요청한다.


BOARDS: Dict[str, NoticeBoard] = {
    board.name: board
    for board in (
        NoticeBoard(
            name="학사공지",
            list_url="https://labor.dankook.ac.kr/web/kor/-390",
            row_selector="div.dku-list-body-item",
            title_selector="div.item-title a",
            view_base_url="https://labor.dankook.ac.kr/web/kor/-390?p_p_id=dku_bbs_web_BbsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_dku_bbs_web_BbsPortlet_cur=1&_dku_bbs_web_BbsPortlet_action=view_message&_dku_bbs_web_BbsPortlet_orderBy=createDate&_dku_bbs_web_BbsPortlet_bbsMessageId=",
        ),
        NoticeBoard(
            name="모바일시스템공학과",
            list_url="https://cms.dankook.ac.kr/web/mobilesystems/-8",
            row_selector="div.dku-list-body-item",
            title_selector="div.item-title a",
            view_base_url="https://cms.dankook.ac.kr/web/mobilesystems/-8?p_p_id=dku_bbs_web_BbsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_dku_bbs_web_BbsPortlet_action=view_message&_dku_bbs_web_BbsPortlet_bbsMessageId=",
        ),
        NoticeBoard(
            name="SW대회/행사",
            list_url="https://swcu.dankook.ac.kr/ko/-2024-",
            row_selector="div.dku-list-body-item",
            title_selector="div.r_cont h4 a",
            view_base_url="https://swcu.dankook.ac.kr/ko/-2024-?p_p_id=dku_bbs_web_BbsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_dku_bbs_web_BbsPortlet_action=view_message&_dku_bbs_web_BbsPortlet_bbsMessageId=",
        ),
    )
}

DEFAULT_BOARD = "학사공지"
BRIEFING_BOARD = "모바일시스템공학과"

# (질문에 포함되면 해당 게시판으로 라우팅하는 키워드, 게시판 이름). 위에서부터 먼저 일치하는 것을 사용한다.
_ROUTES = (
    (("모바일시스템공학과", "모시공"), "모바일시스템공학과"),
    (("SW행사", "소융대행사"), "SW대회/행사"),
)


def resolve_board(query: str) -> str:
    """공지 질문에서 조회할 게시판 이름을 정한다. 일치하는 키워드가 없으면 학사공지."""
    for keywords, board_name in _ROUTES:
        if any(keyword in query for keyword in keywords):
            return board_name
    return DEFAULT_BOARD
