"""질문 의도 분류. 키워드 규칙 기반이며 LLM 을 호출하지 않는다."""

MENU = "menu"
NOTICE = "notice"
GENERAL = "general"

MENU_KEYWORDS = ("학식", "학생식당")
NOTICE_KEYWORDS = ("[공지]",)


def classify_intent(query: str) -> str:
    # 공백을 제거한 뒤 비교하므로 "학생 식당" 도 "학생식당" 으로 매치된다.
    compact = query.replace(" ", "")
    if any(keyword in compact for keyword in MENU_KEYWORDS):
        return MENU
    if any(keyword in compact for keyword in NOTICE_KEYWORDS):
        return NOTICE
    return GENERAL
