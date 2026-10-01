from datetime import date, datetime, timedelta, timezone


def get_kst_now() -> datetime:
    """한국 표준시(KST)를 timezone 정보 없이(naive) 반환한다. DB에는 이 값이 그대로 저장된다."""
    return datetime.now(timezone.utc) + timedelta(hours=9)


def today_kst() -> date:
    """KST 기준 오늘 날짜.

    서버가 UTC로 도는 환경(예: Railway)에서는 KST 00:00~09:00 사이에 `date.today()`(서버 로컬 날짜)와
    `created_at`(KST로 저장됨)의 날짜가 어긋난다. 날짜 비교가 필요한 곳(카카오 일일 한도, 학식 날짜 표시 등)은
    이 함수를 쓴다.
    """
    return get_kst_now().date()
