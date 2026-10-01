"""KakaoService 순수 헬퍼 단위 테스트."""
import pytest

from app.services.kakao_service import is_authorized_webhook, kakao_text_response


def test_kakao_text_response_shape():
    assert kakao_text_response("안녕") == {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": "안녕"}}]},
    }


@pytest.mark.parametrize(
    "provided, configured, expected",
    [
        (None, None, True),       # 검증 미설정 시 항상 통과 (기존 배포 호환)
        ("anything", None, True),
        (None, "secret", False),  # 설정돼 있는데 헤더가 없으면 거부
        ("wrong", "secret", False),
        ("secret", "secret", True),
        ("Secret", "secret", False),  # 대소문자까지 정확히 일치해야 한다
    ],
)
def test_is_authorized_webhook(provided, configured, expected):
    assert is_authorized_webhook(provided, configured) is expected
