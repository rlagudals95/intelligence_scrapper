"""
슬랙 알림 유틸리티
"""
import os
import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.logger import get_logger

logger = get_logger()


class SlackNotifier:
    """슬랙 웹훅을 통한 알림 전송"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Args:
            webhook_url: 슬랙 웹훅 URL (없으면 환경변수에서 가져옴)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL이 설정되지 않았습니다. 슬랙 알림이 비활성화됩니다.")
    
    async def send_message(self, text: str, blocks: Optional[List[Dict]] = None) -> bool:
        """
        슬랙 메시지 전송
        
        Args:
            text: 메시지 텍스트 (fallback)
            blocks: 슬랙 블록 킷 (선택적)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.webhook_url:
            logger.debug("슬랙 웹훅이 설정되지 않아 메시지를 전송하지 않습니다.")
            return False
        
        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("슬랙 메시지 전송 완료")
                    return True
                else:
                    logger.error(f"슬랙 메시지 전송 실패: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"슬랙 메시지 전송 중 오류: {e}")
            return False
    
    async def send_scraping_result(
        self,
        site_name: str,
        success: bool,
        product_count: int = 0,
        policy_count: int = 0,
        duration_seconds: float = 0.0,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        스크래핑 결과 알림 전송
        
        Args:
            site_name: 사이트 이름
            success: 성공 여부
            product_count: 추출된 제품 수
            policy_count: 추출된 정책 수
            duration_seconds: 소요 시간 (초)
            error_message: 오류 메시지 (실패 시)
            details: 추가 상세 정보
            
        Returns:
            bool: 전송 성공 여부
        """
        # 이모지
        status_emoji = "✅" if success else "❌"
        
        # 기본 텍스트
        text = f"{status_emoji} [{site_name}] 스크래핑 {'완료' if success else '실패'}"
        
        # 블록 구성
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} 스크래핑 결과: {site_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*상태:*\n{'성공' if success else '실패'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*소요 시간:*\n{duration_seconds:.1f}초"
                    }
                ]
            }
        ]
        
        # 성공 시 통계
        if success:
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*제품 수:*\n{product_count:,}개"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*정책 수:*\n{policy_count:,}개"
                    }
                ]
            })
        
        # 실패 시 오류 메시지
        if not success and error_message:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*오류:*\n```{error_message[:500]}```"
                }
            })
        
        # 추가 상세 정보
        if details:
            detail_text = "\n".join([f"• {k}: {v}" for k, v in details.items()])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*상세 정보:*\n{detail_text}"
                }
            })
        
        # 시간 정보
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })
        
        return await self.send_message(text, blocks)
    
    async def send_integration_summary(
        self,
        results: List[Dict[str, Any]],
        total_duration: float,
        llm_stats: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        통합 테스트 결과 요약 전송
        
        Args:
            results: 사이트별 결과 리스트
            total_duration: 전체 소요 시간 (초)
            llm_stats: LLM 사용 통계
            
        Returns:
            bool: 전송 성공 여부
        """
        # 통계 계산
        total_sites = len(results)
        success_sites = sum(1 for r in results if r.get('success'))
        total_products = sum(r.get('product_count', 0) for r in results)
        total_policies = sum(r.get('policy_count', 0) for r in results)
        
        # 기본 텍스트
        text = f"🎯 통합 스크래핑 완료: {success_sites}/{total_sites} 사이트 성공"
        
        # 블록 구성
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎯 통합 스크래핑 결과 요약",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*전체 사이트:*\n{total_sites}개"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*성공 사이트:*\n{success_sites}개 ✅"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*제품 수:*\n{total_products:,}개"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*정책 수:*\n{total_policies:,}개"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        # 사이트별 결과
        site_results = []
        for result in results[:10]:  # 최대 10개만
            site_name = result.get('site_name', 'Unknown')
            success = result.get('success', False)
            product_count = result.get('product_count', 0)
            policy_count = result.get('policy_count', 0)
            
            emoji = "✅" if success else "❌"
            site_results.append(
                f"{emoji} *{site_name}*: {product_count}개 제품, {policy_count:,}개 정책"
            )
        
        if site_results:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*사이트별 결과:*\n" + "\n".join(site_results)
                }
            })
        
        if len(results) > 10:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_...외 {len(results) - 10}개 사이트_"
                }
            })
        
        blocks.append({
            "type": "divider"
        })
        
        # LLM 사용량
        if llm_stats:
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*LLM 요청:*\n{llm_stats.get('request_count', 0):,}회"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*토큰 사용:*\n{llm_stats.get('total_tokens', 0):,}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*비용:*\n${llm_stats.get('total_cost_usd', 0):.4f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*소요 시간:*\n{total_duration:.1f}초"
                    }
                ]
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*전체 소요 시간:* {total_duration:.1f}초"
                }
            })
        
        # 시간 정보
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })
        
        return await self.send_message(text, blocks)

