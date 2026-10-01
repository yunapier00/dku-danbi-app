"""카카오 챗봇 연동에 필요한 순수 로직: 응답 포맷, 웹훅 요청 검증."""
import hmac
from typing import Optional

# 카카오 i 오픈빌더 '스킬' 설정의 스킬 서버 HTTP 헤더에 같은 이름으로, 같은 값을 등록해야 한다.
KAKAO_SECRET_HEADER = "X-Danbi-Kakao-Secret"


def kakao_text_response(text: str) -> dict:
    return {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text}}]}}


def is_authorized_webhook(provided_secret: Optional[str], configured_secret: Optional[str]) -> bool:
    """설정된 비밀이 없으면 검증을 건너뛴다(기존 배포와의 호환). 설정돼 있으면 상수 시간 비교로 검증한다."""
    if not configured_secret:
        return True
    if not provided_secret:
        return False
    return hmac.compare_digest(provided_secret, configured_secret)
