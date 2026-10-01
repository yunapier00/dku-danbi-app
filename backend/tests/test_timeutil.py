import inspect

from app.core.timeutil import get_kst_now, today_kst


def test_today_kst_matches_get_kst_now_date():
    assert today_kst() == get_kst_now().date()


def test_chat_service_and_menu_crawler_default_to_kst_today():
    """시간대 버그 수정: date.today()(서버 로컬) 대신 today_kst 를 기본값으로 쓴다."""
    from app.crawlers.menu import MenuCrawler
    from app.services.chat_service import ChatService

    assert inspect.signature(ChatService.__init__).parameters["today"].default is today_kst
    assert inspect.signature(MenuCrawler.__init__).parameters["today"].default is today_kst
