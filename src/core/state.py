"""
상태 관리 (State Manager)
중복 방지 및 방문 추적
"""
import json
import hashlib
from pathlib import Path
from typing import Set, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger()


class StateManager:
    """방문 상태 관리 및 중복 방지"""
    
    def __init__(self, state_file: str = "checkpoints/state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 방문한 detail_url 집합
        self.visited_urls: Set[str] = set()
        
        # 옵션 상태 해시 (detail_url + options_hash)
        self.visited_states: Set[str] = set()
        
        # 통계
        self.stats: Dict[str, Any] = {
            "total_urls": 0,
            "total_states": 0,
            "started_at": datetime.now().isoformat(),
            "last_updated": None
        }
        
        # 기존 상태 로드
        self.load()
    
    def load(self) -> None:
        """저장된 상태 로드"""
        if not self.state_file.exists():
            logger.info("새로운 상태 파일 생성")
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.visited_urls = set(data.get("visited_urls", []))
            self.visited_states = set(data.get("visited_states", []))
            self.stats = data.get("stats", self.stats)
            
            logger.info(
                "상태 로드 완료",
                urls=len(self.visited_urls),
                states=len(self.visited_states)
            )
        except Exception as e:
            logger.error("상태 로드 실패", error=str(e))
    
    def save(self) -> None:
        """현재 상태 저장"""
        self.stats["last_updated"] = datetime.now().isoformat()
        self.stats["total_urls"] = len(self.visited_urls)
        self.stats["total_states"] = len(self.visited_states)
        
        try:
            data = {
                "visited_urls": list(self.visited_urls),
                "visited_states": list(self.visited_states),
                "stats": self.stats
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("상태 저장 완료")
        except Exception as e:
            logger.error("상태 저장 실패", error=str(e))
    
    def is_url_visited(self, url: str) -> bool:
        """URL 방문 여부 확인"""
        return url in self.visited_urls
    
    def mark_url_visited(self, url: str) -> None:
        """URL을 방문한 것으로 표시"""
        if url not in self.visited_urls:
            self.visited_urls.add(url)
            logger.debug(f"URL 방문 기록: {url}")
    
    def is_state_visited(self, detail_url: str, options: Dict[str, Any]) -> bool:
        """옵션 상태 방문 여부 확인"""
        state_hash = self.hash_state(detail_url, options)
        return state_hash in self.visited_states
    
    def mark_state_visited(self, detail_url: str, options: Dict[str, Any]) -> None:
        """옵션 상태를 방문한 것으로 표시"""
        state_hash = self.hash_state(detail_url, options)
        if state_hash not in self.visited_states:
            self.visited_states.add(state_hash)
            logger.debug(f"상태 방문 기록: {state_hash[:16]}...")
    
    @staticmethod
    def hash_state(detail_url: str, options: Dict[str, Any]) -> str:
        """옵션 상태 해시 생성"""
        # 옵션을 정렬하여 일관된 해시 생성
        sorted_options = sorted(options.items())
        state_str = f"{detail_url}|{json.dumps(sorted_options, sort_keys=True)}"
        
        # SHA256 해시
        return hashlib.sha256(state_str.encode('utf-8')).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            **self.stats,
            "current_urls": len(self.visited_urls),
            "current_states": len(self.visited_states)
        }
    
    def reset(self) -> None:
        """상태 초기화"""
        self.visited_urls.clear()
        self.visited_states.clear()
        self.stats = {
            "total_urls": 0,
            "total_states": 0,
            "started_at": datetime.now().isoformat(),
            "last_updated": None
        }
        logger.warning("상태 초기화 완료")

