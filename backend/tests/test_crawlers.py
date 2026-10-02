"""크롤러: 파싱, 출력 형식, 실패(예외), 캐시, 게시판 이름 계약을 고정한다. 네트워크/Chrome 은 사용하지 않는다."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.crawlers import menu as menu_module
from app.crawlers.boards import BOARDS, DEFAULT_BOARD, BRIEFING_BOARD, resolve_board
from app.crawlers.cache import TTLCache
from app.crawlers.errors import CrawlerError
from app.crawlers.menu import MenuCrawler
from app.crawlers.notice import (
    BODY_NOT_FOUND,
    BODY_TIMEOUT,
    BODY_UNAVAILABLE,
    Notice,
    NoticeCrawler,
    format_notices,
    parse_notice_body,
    parse_notice_list,
)
from conftest import FakeResponse

BOARD = BOARDS["모바일시스템공학과"]


def list_html(rows):
    items = "".join(
        f'<div class="dku-list-body-item"><div class="item-title"><a {attrs}>{title}</a></div></div>'
        for title, attrs in rows
    )
    return f"<html><body>{items}</body></html>"


def detail_html(body):
    return (
        '<html><body><table class="table mb-3"><tbody><tr><td>'
        f'<div class="fr-view">{body}</div></td></tr></tbody></table></body></html>'
    )


def row(title, post_id):
    return (title, f'onclick="viewMessage({post_id}, 1)"')


class FakeSite:
    """requests.get 대체. 목록/상세 URL 별로 응답을 돌려주고 요청 기록을 남긴다."""

    def __init__(self, board=BOARD):
        self.board = board
        self.list_response = FakeResponse(text=list_html([]))
        self.details = {}  # post_id -> FakeResponse | Exception
        self.list_error = None
        self.calls = []  # (url, kwargs)

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == self.board.list_url:
            if self.list_error:
                raise self.list_error
            return self.list_response
        assert url.startswith(self.board.view_base_url), url
        post_id = url[len(self.board.view_base_url):]
        result = self.details.get(post_id, FakeResponse(text=detail_html("기본본문")))
        if isinstance(result, Exception):
            raise result
        return result

    @property
    def detail_calls(self):
        return [c for c in self.calls if c[0] != self.board.list_url]


@pytest.fixture
def site():
    return FakeSite()


def crawler(site, **kwargs):
    kwargs.setdefault("cache_ttl_seconds", 0)
    return NoticeCrawler(http_get=site, **kwargs)


# ---------------------------------------------------------------- 게시판 이름 계약
def test_every_routed_board_is_registered():
    """버그 수정: 예전에는 라우팅이 'SW중심대학사업단' 을 넘기는데 설정 키는 'SW대회/행사' 라서 항상 실패했다."""
    for query in ["", "모시공", "모바일시스템공학과", "SW행사", "소융대행사", "그냥 공지"]:
        assert resolve_board(query) in BOARDS
    assert DEFAULT_BOARD in BOARDS and BRIEFING_BOARD in BOARDS


@pytest.mark.parametrize(
    "query, board",
    [
        ("최신 공지", "학사공지"),
        ("모시공 공지", "모바일시스템공학과"),
        ("모바일시스템공학과 공지", "모바일시스템공학과"),
        ("SW행사 알려줘", "SW대회/행사"),
        ("소융대행사 알려줘", "SW대회/행사"),
        ("모시공 SW행사", "모바일시스템공학과"),  # 먼저 일치하는 규칙이 우선
    ],
)
def test_resolve_board(query, board):
    assert resolve_board(query) == board


def test_every_board_is_fully_configured():
    for name, board in BOARDS.items():
        assert board.name == name
        assert board.list_url.startswith("https://")
        assert board.view_base_url.startswith(board.list_url)
        assert board.view_base_url.endswith("bbsMessageId=")


# ---------------------------------------------------------------- 순수 파싱
def test_parse_notice_list_returns_titles_and_ids_skipping_empty_titles():
    html = list_html([("   ", 'onclick="viewMessage(1)"'), row("공지1", 101), ("링크만", 'href="#"')])

    assert parse_notice_list(html, BOARD) == [("공지1", "101"), ("링크만", None)]


def test_parse_notice_list_raises_when_layout_changed():
    with pytest.raises(CrawlerError, match="'모바일시스템공학과' 게시판의 HTML 구조가 변경된 것 같습니다."):
        parse_notice_list("<html><body></body></html>", BOARD)


def test_parse_notice_list_handles_sw_board_webzine_layout():
    """실제 SW 게시판(swcu.dankook.ac.kr)의 웹진 레이아웃: 제목 링크가 div.r_cont h4 a, 함수명은 접두어가 붙는다."""
    html = """
    <div class="dku-list-body-item"><div class="dku-list-body-item-col webzine_list">
      <div class="r_img"><a href="#none" onclick="_dku_bbs_web_BbsPortlet_viewMessage(184705, true, false)"><img src="x.png"/></a></div>
      <div class="r_cont"><h4>
        <a class="" href="#none" onclick="_dku_bbs_web_BbsPortlet_viewMessage(184705, true, false)">[홍보] SK하이닉스 AI해커톤 2026</a>
        <span class="badge">N</span></h4><p class="content">[안내 페이지 바로가기]</p></div>
    </div></div>
    """

    assert parse_notice_list(html, BOARDS["SW대회/행사"]) == [("[홍보] SK하이닉스 AI해커톤 2026", "184705")]


def test_parse_notice_body_prefers_fr_view_then_falls_back():
    assert parse_notice_body(detail_html("  첫째   본문\n줄  ")) == "첫째 본문 줄"
    assert parse_notice_body('<table class="table mb-3"><tbody><tr><td>제목</td></tr><tr><td>마지막 행</td></tr></tbody></table>') == "마지막 행"
    assert parse_notice_body('<table class="table mb-3"><tr><td>표 본문</td></tr></table>') == "표 본문"
    assert parse_notice_body("<html><body><p>없음</p></body></html>") == BODY_NOT_FOUND


def test_parse_notice_body_skips_trailing_comment_header_row():
    """SW 게시판 상세: 제목/작성자/날짜/조회수 행 다음이 본문이고, 마지막 행은 '댓글' 머리글이다."""
    html = (
        '<table class="table mb-3"><tbody>'
        "<tr><td>[홍보] 행사 제목</td></tr><tr><td>작성자 홍길동</td></tr>"
        "<tr><td>날짜 2026.09.21</td></tr><tr><td>조회수 6</td></tr>"
        "<tr><td>[안내 페이지 바로가기]</td></tr>"
        "<tr><td>댓글</td></tr>"
        "</tbody></table>"
    )

    assert parse_notice_body(html) == "[안내 페이지 바로가기]"


def test_parse_notice_body_last_row_with_nested_table_returns_whole_outer_row():
    """회귀 방지: 본문 행 안에 표가 중첩돼 있어도 안쪽 조각이 아니라 바깥 행 전체를 반환한다.
    (라이브 학사공지/모바일시스템공학과 게시글에서 확인된 구조)"""
    html = (
        '<table class="table mb-3"><tbody>'
        "<tr><td>제목</td></tr>"
        "<tr><td><table><tbody><tr><td>안쪽 A</td></tr><tr><td>안쪽 B</td></tr></tbody></table>바깥 텍스트</td></tr>"
        "</tbody></table>"
    )

    # 안쪽 조각("안쪽 B")이 아니라 바깥 행 전체 텍스트여야 한다. (태그 사이 공백이 없어 텍스트가 이어 붙는다)
    assert parse_notice_body(html) == "안쪽 A안쪽 B바깥 텍스트"


def test_parse_notice_body_comment_only_table_falls_back_to_whole_table():
    html = '<table class="table mb-3"><tbody><tr><td>댓글</td></tr></tbody></table>'

    assert parse_notice_body(html) == "댓글"


def test_format_notices_matches_llm_context_format():
    text = format_notices("모바일시스템공학과", [Notice("공지1", "본문1"), Notice("공지2", "본문2")])

    assert text == (
        "📢 [모바일시스템공학과 최신 공지사항 Top 3]\n\n"
        "1. 제목: 공지1\n   내용 : 본문1\n\n"
        "2. 제목: 공지2\n   내용 : 본문2\n\n"
    )


# ---------------------------------------------------------------- NoticeCrawler
def test_returns_top3_with_title_and_body(site):
    site.list_response = FakeResponse(text=list_html([row(f"공지{i}", 100 + i) for i in range(1, 6)]))
    site.details = {
        "101": FakeResponse(text=detail_html("  첫째   본문\n줄  ")),
        "102": FakeResponse(text=detail_html("둘째 본문")),
        "103": FakeResponse(text=detail_html("셋째 본문")),
    }

    text = crawler(site).get_text("모바일시스템공학과")

    assert text == (
        "📢 [모바일시스템공학과 최신 공지사항 Top 3]\n\n"
        "1. 제목: 공지1\n   내용 : 첫째 본문 줄\n\n"
        "2. 제목: 공지2\n   내용 : 둘째 본문\n\n"
        "3. 제목: 공지3\n   내용 : 셋째 본문\n\n"
    )
    assert len(site.detail_calls) == 3  # 4, 5번째 글은 요청하지 않는다


def test_row_without_view_message_onclick_has_unavailable_body(site):
    site.list_response = FakeResponse(text=list_html([("공지", 'href="#"')]))

    assert crawler(site).fetch("모바일시스템공학과") == [Notice("공지", BODY_UNAVAILABLE)]
    assert site.detail_calls == []


def test_detail_request_failure_is_reported_inline_not_raised(site):
    site.list_response = FakeResponse(text=list_html([row("공지", 55)]))
    site.details = {"55": TimeoutError("slow")}

    assert crawler(site).fetch("모바일시스템공학과") == [Notice("공지", BODY_TIMEOUT)]


def test_unknown_board_raises_crawler_error(site):
    with pytest.raises(CrawlerError, match="아직 '없는학과'의 공지사항은 연동되지 않았습니다."):
        crawler(site).get_text("없는학과")
    assert site.calls == []


def test_layout_change_raises_crawler_error(site):
    site.list_response = FakeResponse(text="<html><body></body></html>")

    with pytest.raises(CrawlerError, match="HTML 구조가 변경된 것 같습니다"):
        crawler(site).get_text("모바일시스템공학과")


def test_list_request_failure_raises_crawler_error(site):
    site.list_error = ConnectionError("no route")

    with pytest.raises(CrawlerError, match="모바일시스템공학과 서버 연결 중 오류가 발생했습니다: no route"):
        crawler(site).get_text("모바일시스템공학과")


def test_http_error_status_raises_crawler_error(site):
    site.list_response = FakeResponse(text="", status_code=500)

    with pytest.raises(CrawlerError, match="서버 연결 중 오류가 발생했습니다"):
        crawler(site).get_text("모바일시스템공학과")


def test_sw_board_is_crawlable_end_to_end():
    sw = BOARDS["SW대회/행사"]
    site = FakeSite(sw)
    site.list_response = FakeResponse(
        text=f'<div class="dku-list-body-item"><div class="r_cont"><h4>'
             f'<a onclick="_dku_bbs_web_BbsPortlet_viewMessage(184705, true, false)">SW 공모전</a></h4></div></div>'
    )
    site.details = {"184705": FakeResponse(text=detail_html("공모전 안내"))}

    text = crawler(site).get_text("SW대회/행사")

    assert "📢 [SW대회/행사 최신 공지사항 Top 3]" in text
    assert "1. 제목: SW 공모전\n   내용 : 공모전 안내" in text
    assert site.detail_calls[0][0] == sw.view_base_url + "184705"


# ---------------------------------------------------------------- SSL 검증
def test_ssl_verification_is_enabled_by_default(site):
    site.list_response = FakeResponse(text=list_html([row("공지", 1)]))

    crawler(site).fetch("모바일시스템공학과")

    assert all(kwargs["verify"] is True for _, kwargs in site.calls)


def test_ssl_verification_can_be_disabled_explicitly(site):
    site.list_response = FakeResponse(text=list_html([row("공지", 1)]))

    crawler(site, verify_ssl=False).fetch("모바일시스템공학과")

    assert all(kwargs["verify"] is False for _, kwargs in site.calls)


# ---------------------------------------------------------------- 캐시
def test_notice_results_are_cached_within_ttl_and_refetched_after(site):
    now = [1000.0]
    site.list_response = FakeResponse(text=list_html([row("공지", 1)]))
    c = crawler(site, cache_ttl_seconds=300, clock=lambda: now[0])

    first = c.fetch("모바일시스템공학과")
    calls_after_first = len(site.calls)
    now[0] += 299
    assert c.fetch("모바일시스템공학과") is first
    assert len(site.calls) == calls_after_first

    now[0] += 2
    c.fetch("모바일시스템공학과")
    assert len(site.calls) == calls_after_first * 2


def test_notice_failures_are_not_cached(site):
    c = crawler(site, cache_ttl_seconds=300)
    site.list_error = ConnectionError("down")
    with pytest.raises(CrawlerError):
        c.fetch("모바일시스템공학과")

    site.list_error = None
    site.list_response = FakeResponse(text=list_html([row("복구됨", 1)]))
    assert c.fetch("모바일시스템공학과")[0].title == "복구됨"


def test_ttl_cache_basics():
    now = [0.0]
    cache = TTLCache(10, clock=lambda: now[0])
    loads = []

    def loader():
        loads.append(1)
        return len(loads)

    assert cache.get_or_load("k", loader) == 1
    assert cache.get_or_load("k", loader) == 1
    assert cache.get_or_load("other", loader) == 2
    now[0] = 11
    assert cache.get_or_load("k", loader) == 3


def test_ttl_cache_disabled_when_ttl_is_zero():
    cache = TTLCache(0)
    counter = iter(range(10))

    assert cache.get_or_load("k", lambda: next(counter)) == 0
    assert cache.get_or_load("k", lambda: next(counter)) == 1


# ---------------------------------------------------------------- 학식 크롤러
class FakeDriver:
    def __init__(self, text="점심: 김치찌개", error=None):
        self.text = text
        self.error = error
        self.visited = []
        self.quit_called = False

    def get(self, url):
        self.visited.append(url)

    def find_element(self, by, value):
        if self.error:
            raise self.error
        assert (by, value) == ("tag name", "body")
        return SimpleNamespace(text=self.text)

    def quit(self):
        self.quit_called = True


def menu_crawler(drivers, *, today=lambda: date(2026, 9, 21), ttl=1800, sleeps=None):
    made = []

    def factory():
        driver = drivers[len(made)]
        made.append(driver)
        return driver

    crawler_ = MenuCrawler(
        driver_factory=factory,
        cache_ttl_seconds=ttl,
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
        today=today,
    )
    return crawler_, made


def test_menu_text_format_and_driver_lifecycle():
    driver = FakeDriver()
    sleeps = []
    c, _ = menu_crawler([driver], sleeps=sleeps)

    assert c.get_menu() == "🍽️ [1947 학식 메뉴 요약]\n\n점심: 김치찌개"
    assert driver.visited == ["https://cms.dankook.ac.kr/web/kor/1947_commons"]
    assert sleeps == [3]
    assert driver.quit_called


def test_menu_failure_raises_crawler_error_and_still_quits_driver():
    driver = FakeDriver(error=RuntimeError("no such element"))
    c, _ = menu_crawler([driver])

    with pytest.raises(CrawlerError, match="크롤링 중 오류 발생: no such element"):
        c.get_menu()
    assert driver.quit_called


def test_menu_driver_creation_failure_raises_crawler_error():
    def factory():
        raise RuntimeError("no driver")

    with pytest.raises(CrawlerError, match="크롤링 중 오류 발생: no driver"):
        MenuCrawler(driver_factory=factory, sleep=lambda s: None).get_menu()


def test_menu_is_cached_per_day_so_chrome_starts_once():
    d1, d2 = FakeDriver("월요일 메뉴"), FakeDriver("화요일 메뉴")
    today = [date(2026, 9, 21)]
    c, made = menu_crawler([d1, d2], today=lambda: today[0])

    assert "월요일 메뉴" in c.get_menu()
    assert "월요일 메뉴" in c.get_menu()
    assert len(made) == 1

    today[0] = date(2026, 9, 22)  # 자정이 지나면 전날 메뉴를 재사용하지 않는다
    assert "화요일 메뉴" in c.get_menu()
    assert len(made) == 2


def test_menu_failure_is_not_cached():
    bad, good = FakeDriver(error=RuntimeError("x")), FakeDriver("복구된 메뉴")
    c, made = menu_crawler([bad, good])

    with pytest.raises(CrawlerError):
        c.get_menu()
    assert "복구된 메뉴" in c.get_menu()


def test_chromedriver_install_runs_once_per_process(monkeypatch):
    installs = []

    class FakeManager:
        def __init__(self, *args, **kwargs):
            pass

        def install(self):
            installs.append(1)
            return "/fake/chromedriver"

    built = []
    monkeypatch.setattr(menu_module, "ChromeDriverManager", FakeManager)
    monkeypatch.setattr(menu_module, "_driver_path", None)
    monkeypatch.setattr(menu_module.webdriver, "Chrome", lambda service, options: built.append(service.path) or "driver")

    assert menu_module.create_chrome_driver() == "driver"
    assert menu_module.create_chrome_driver() == "driver"

    assert installs == [1]
    assert built == ["/fake/chromedriver", "/fake/chromedriver"]


def test_configured_chromedriver_path_skips_webdriver_manager_download(monkeypatch):
    """Docker 이미지처럼 CHROMEDRIVER_PATH/CHROME_BINARY_PATH 가 설정돼 있으면
    webdriver-manager 의 런타임 다운로드를 아예 타지 않아야 한다(네트워크 의존 제거)."""
    monkeypatch.setenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    monkeypatch.setenv("CHROME_BINARY_PATH", "/usr/bin/chromium")

    def boom(*args, **kwargs):
        raise AssertionError("webdriver-manager 가 호출되면 안 된다")

    monkeypatch.setattr(menu_module, "ChromeDriverManager", boom)
    monkeypatch.setattr(menu_module, "_driver_path", None)

    captured = {}

    def fake_chrome(service, options):
        captured["driver_path"] = service.path
        captured["binary_location"] = options.binary_location
        return "driver"

    monkeypatch.setattr(menu_module.webdriver, "Chrome", fake_chrome)

    assert menu_module.create_chrome_driver() == "driver"
    assert captured == {"driver_path": "/usr/bin/chromedriver", "binary_location": "/usr/bin/chromium"}


def test_chrome_binary_path_falls_back_to_hardcoded_linux_default(monkeypatch):
    """CHROME_BINARY_PATH 미설정 시 기존 동작(비-Windows는 /usr/bin/chromium 가정)을 유지한다."""
    monkeypatch.delenv("CHROME_BINARY_PATH", raising=False)
    monkeypatch.setenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    monkeypatch.setattr(menu_module.os, "name", "posix")

    captured = {}
    monkeypatch.setattr(
        menu_module.webdriver,
        "Chrome",
        lambda service, options: captured.setdefault("binary_location", options.binary_location),
    )

    menu_module.create_chrome_driver()

    assert captured["binary_location"] == "/usr/bin/chromium"
