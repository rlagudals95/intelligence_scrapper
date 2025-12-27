"""
로깅 설정 (structlog)
"""
import sys
import structlog
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_dir: str = "logs"
) -> None:
    """structlog 설정"""
    
    # 로그 디렉토리 생성
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # 로그 파일명 (타임스탬프 포함)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_path / f"scraper_{timestamp}.log"
    
    # Processors 설정
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # 콘솔 출력용 (컬러)
    if log_to_console:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
    
    # 파일 출력용 (JSON)
    if log_to_file:
        processors.append(
            structlog.processors.JSONRenderer()
        )
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib.logging, log_level.upper(), structlog.stdlib.logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(
            file=open(log_file, "a", encoding="utf-8") if log_to_file else sys.stdout
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """로거 인스턴스 반환"""
    return structlog.get_logger(name)


# 기본 로거 설정 (모듈 로드 시)
_initialized = False

def ensure_logger_initialized():
    """로거 초기화 확인"""
    global _initialized
    if not _initialized:
        setup_logger()
        _initialized = True


# 모듈 임포트 시 기본 설정
ensure_logger_initialized()

