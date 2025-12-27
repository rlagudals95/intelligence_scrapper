"""
설정 관리 (Configuration)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SiteConfig:
    """사이트별 스크래핑 설정"""
    
    # 대상 URL
    target_url: str
    listing_url: Optional[str] = None  # 리스팅 페이지 URL (없으면 target_url 사용)
    
    # 딜레이 설정 (초)
    delay_min: float = 1.0
    delay_max: float = 3.0
    
    # 브라우저 설정
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout: int = 30000  # 밀리초 (30초)
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    
    # 재시도 설정
    max_retries: int = 3
    retry_delay: float = 2.0
    
    # 가지치기 설정
    pruning_threshold: int = 3  # 연속 N회 가격 변화 없으면 가지치기
    
    # 체크포인트 설정
    checkpoint_interval: int = 10  # N개마다 중간 저장
    
    # 로깅 설정
    log_level: str = "INFO"
    log_to_file: bool = True
    log_to_console: bool = True
    
    def __post_init__(self):
        """초기화 후 검증"""
        if not self.listing_url:
            self.listing_url = self.target_url
        
        if self.delay_min > self.delay_max:
            raise ValueError("delay_min은 delay_max보다 작아야 합니다")
        
        if self.pruning_threshold < 1:
            raise ValueError("pruning_threshold는 1 이상이어야 합니다")


# 기본 설정
DEFAULT_CONFIG = SiteConfig(
    target_url="https://example.com",
    delay_min=1.0,
    delay_max=3.0,
)

