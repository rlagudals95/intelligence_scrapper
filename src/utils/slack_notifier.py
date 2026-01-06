"""
슬랙 알림 유틸리티
"""
import os
import json
import csv
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.logger import get_logger
from ..models.phase3_schemas import ScrapingResult, Product, Policy

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
    
    @staticmethod
    def save_policies_to_csv(
        policies: List[Policy],
        output_dir: Path,
        product_name: str,
        site_name: str
    ) -> Path:
        """
        정책 데이터를 CSV 파일로 저장
        
        Args:
            policies: 정책 리스트
            output_dir: 출력 디렉토리
            product_name: 제품명
            site_name: 사이트 이름
            
        Returns:
            생성된 CSV 파일 경로
        """
        # CSV 디렉토리 생성
        csv_dir = output_dir / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성 (특수문자 제거)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_product_name = product_name.replace('/', '_').replace(' ', '_').replace('\\', '_')
        safe_site_name = site_name.replace('/', '_').replace(' ', '_').replace('\\', '_')
        filename = f"{safe_site_name}_{safe_product_name}_{timestamp}.csv"
        csv_path = csv_dir / filename
        
        # CSV 파일 작성
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            
            # 헤더
            writer.writerow([
                '통신사', '가입유형', '요금제명', '월요금(원)',
                '출고가(원)', '공시지원금(원)', '추가할인(원)', '월할부금(원)'
            ])
            
            # 데이터
            for policy in policies:
                writer.writerow([
                    policy.carrier,
                    policy.mno_join_type.value,
                    policy.mobile_plan.name,
                    policy.mobile_plan.monthly_fee or '',
                    policy.pricing.mno_retail_price or '',
                    policy.pricing.public_subsidy or '',
                    policy.pricing.discount or '',
                    policy.pricing.monthly_payment or ''
                ])
        
        logger.info(f"CSV 파일 생성 완료: {csv_path}")
        return csv_path
    
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
    
    async def send_policy_summary(
        self,
        site_name: str,
        product_name: str,
        policies: List[Policy],
        product_url: Optional[str] = None,
        csv_file_path: Optional[str] = None
    ) -> bool:
        """
        정책 데이터를 비즈니스 친화적으로 표시
        
        Args:
            site_name: 사이트 이름
            product_name: 제품명
            policies: 정책 리스트
            product_url: 제품 상세 URL (선택)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not policies:
            return await self.send_message(
                f"⚠️ [{site_name}] {product_name} - 정책 데이터 없음",
                blocks=[{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{product_name}*\n정책을 찾을 수 없습니다."
                    }
                }]
            )
        
        # 정책을 통신사별로 그룹화
        policies_by_carrier = {}
        for policy in policies:
            carrier = policy.carrier
            if carrier not in policies_by_carrier:
                policies_by_carrier[carrier] = []
            policies_by_carrier[carrier].append(policy)
        
        # 헤더
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📱 {product_name} - {site_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*총 정책 수:*\n{len(policies)}개"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*통신사:*\n{len(policies_by_carrier)}개"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        # 각 통신사별 정책 표시 (요약만)
        for carrier, carrier_policies in policies_by_carrier.items():
            # 통신사 헤더
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{carrier}* - {len(carrier_policies)}개 정책"
                }
            })
            
            # 최저가 정책 찾기 (월 할부금 기준)
            sorted_policies = sorted(
                carrier_policies,
                key=lambda p: p.pricing.monthly_payment or float('inf')
            )
            
            # 최저가 1-2개만 표시
            for policy in sorted_policies[:2]:
                pricing = policy.pricing
                plan = policy.mobile_plan
                
                # 가격 정보 포맷팅
                price_info = []
                
                if pricing.mno_retail_price:
                    price_info.append(f"출고가: {pricing.mno_retail_price:,}원")
                
                if pricing.public_subsidy:
                    price_info.append(f"공시지원금: {pricing.public_subsidy:,}원")
                
                if pricing.discount:
                    price_info.append(f"추가할인: {pricing.discount:,}원")
                
                if pricing.monthly_payment:
                    price_info.append(f"월 할부금: {pricing.monthly_payment:,}원")
                
                # 요금제 정보
                plan_text = f"{plan.name}"
                if plan.monthly_fee:
                    plan_text += f" ({plan.monthly_fee:,}원/월)"
                
                policy_text = f"• *{plan_text}* ({policy.mno_join_type.value})\n"
                if price_info:
                    policy_text += "  " + " | ".join(price_info)
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": policy_text
                    }
                })
            
            # 더 많은 정책이 있으면 안내
            if len(carrier_policies) > 2:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"_...외 {len(carrier_policies) - 2}개 정책 (전체 정책은 CSV 파일 참조)_"
                    }]
                })
            
            blocks.append({
                "type": "divider"
            })
        
        # CSV 파일 다운로드 안내
        if csv_file_path:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📊 *전체 정책 CSV 파일:*\n`{csv_file_path}`\n\n💡 파일 경로를 복사해서 다운로드하거나, 서버에서 직접 열어보세요."
                }
            })
        
        # URL 추가
        if product_url:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{product_url}|🔗 상세 페이지 보기>"
                }
            })
        
        # 시간 정보
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }]
        })
        
        text = f"📱 {product_name} - {len(policies)}개 정책 추출 완료"
        return await self.send_message(text, blocks)
    
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
        scraping_results: List[ScrapingResult],
        site_names: Optional[List[str]] = None
    ) -> bool:
        """
        통합 스크래핑 결과 요약 전송 (비즈니스 친화적)
        
        Args:
            scraping_results: ScrapingResult 리스트
            site_names: 사이트 이름 리스트 (선택)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not scraping_results:
            return await self.send_message("⚠️ 스크래핑 결과가 없습니다.")
        
        # 통계 계산
        total_products = sum(len(r.products) for r in scraping_results)
        total_policies = sum(
            len(policy) 
            for r in scraping_results 
            for product in r.products 
            for policy in [product.policies]
        )
        
        # 기본 텍스트
        text = f"📊 스크래핑 완료: {total_products}개 제품, {total_policies}개 정책"
        
        # 블록 구성
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 스크래핑 결과 요약",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*제품 수:*\n{total_products}개"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*정책 수:*\n{total_policies}개"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        # 제품별 요약 (최대 10개)
        product_summaries = []
        for idx, result in enumerate(scraping_results):
            site_name = site_names[idx] if site_names and idx < len(site_names) else result.source.site
            
            for product in result.products[:3]:  # 사이트당 최대 3개 제품
                if len(product_summaries) >= 10:
                    break
                
                # 최저가 정책 찾기
                best_policy = None
                best_price = float('inf')
                
                for policy in product.policies:
                    final_price = policy.pricing.monthly_payment or 0
                    if final_price > 0 and final_price < best_price:
                        best_price = final_price
                        best_policy = policy
                
                if best_policy:
                    pricing = best_policy.pricing
                    plan = best_policy.mobile_plan
                    
                    summary = f"• *{product.sku_code}* ({site_name})\n"
                    summary += f"  {best_policy.carrier} / {best_policy.mno_join_type.value} / {plan.name}\n"
                    
                    price_parts = []
                    if pricing.mno_retail_price:
                        price_parts.append(f"출고가: {pricing.mno_retail_price:,}원")
                    if pricing.public_subsidy:
                        price_parts.append(f"공시지원금: {pricing.public_subsidy:,}원")
                    if pricing.monthly_payment:
                        price_parts.append(f"월 할부금: {pricing.monthly_payment:,}원")
                    
                    if price_parts:
                        summary += f"  {' | '.join(price_parts)}\n"
                    
                    summary += f"  총 {len(product.policies)}개 정책"
                    
                    product_summaries.append(summary)
        
        if product_summaries:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*주요 제품 정책:*\n" + "\n".join(product_summaries)
                }
            })
        
        # 시간 정보
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }]
        })
        
        return await self.send_message(text, blocks)

