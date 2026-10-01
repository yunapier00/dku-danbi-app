from loguru import logger


def setup_logging(log_dir: str = "logs") -> None:
    # rotation="00:00": 매일 자정에 새로운 로그 파일 생성
    # retention="7 days": 7일이 지난 로그 파일은 자동 삭제
    logger.add(f"{log_dir}/danbi_chat_{{time:YYYY-MM-DD}}.log", rotation="00:00", retention="7 days", level="INFO")
