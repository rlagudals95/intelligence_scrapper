"""
스마트 요금제 추출기
LLM Vision으로 드롭다운 찾고 열고 추출
"""
import json
import asyncio
import base64
from typing import Dict, Any, List
from playwright.async_api import Page

from ..core.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger()


class SmartPlanExtractor:
    """
    LLM Vision 기반 요금제 추출
    
    단계:
    1. Vision으로 "요금제" 드롭다운 버튼 찾기
    2. 클릭
    3. Vision으로 열린 드롭다운에서 모든 요금제 추출
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    async def extract_all_plans(self, page: Page) -> List[Dict[str, Any]]:
        """
        페이지에서 모든 요금제 추출 (Vision 기반)
        
        Returns:
            [{"name": "프라임", "monthly_fee": 89000}, ...]
        """
        logger.info("   📋 Smart Plan Extractor 시작")
        print("   📋 Smart Plan Extractor (Vision) 시작")
        
        try:
            # Step 1: popup/모달/드롭다운 확인
            logger.info("   🔍 popup/모달 확인 중...")
            
            # popup 확인 (.popup, .modal, .layer)
            popup_visible = await page.locator('.popup:visible, .modal:visible, .bill-layer-box:visible, .plan_list:visible').count()
            print(f"   popup/모달: {popup_visible}개 발견")
            
            # Step 2: 화면 전체 스크린샷 (popup 포함)
            screenshot = await page.screenshot(
                full_page=False,  # viewport만 (빠름, popup이 viewport에 있음)
                quality=70,
                type='jpeg',
                timeout=8000
            )
            screenshot_b64 = base64.b64encode(screenshot).decode()
            img_url = f"data:image/jpeg;base64,{screenshot_b64}"
            
            print(f"   📸 스크린샷: {len(screenshot_b64)} bytes (full page)")
            
            # Step 3: Vision으로 화면의 모든 요금제 추출
            plan_prompt = """
이 화면에서 **모든 요금제와 월요금**을 추출하세요.

화면에 요금제 리스트/테이블/popup이 있습니다:
- 프라임 플러스    월 99,000원
- 프라임           월 89,000원
- 레귤러 플러스    월 79,000원
- 레귤러           월 69,000원
- 베이직 플러스    월 59,000원
- 베이직           월 49,000원

**popup 창이나 드롭다운 메뉴에 있는 모든 요금제를 찾으세요!**

JSON 배열:
[
  {"name": "프라임 플러스", "monthly_fee": 99000},
  {"name": "프라임", "monthly_fee": 89000},
  {"name": "레귤러 플러스", "monthly_fee": 79000},
  {"name": "레귤러", "monthly_fee": 69000},
  {"name": "베이직 플러스", "monthly_fee": 59000}
]

**주의:**
- 괄호 내용 제거 ("프리미엄(OTT 택1)" → "프리미엄")
- "5GX", "5G" 포함해도 됨
- 월요금은 정수로
- **화면에 보이는 모든 요금제를 추출** (최소 5개 이상 찾으세요!)

**JSON 배열만 출력하세요.**
"""
            
            resp = await self.llm.complete_with_vision(
                prompt=plan_prompt,
                image_url=img_url,
                system_message="화면의 popup/드롭다운을 포함하여 모든 요금제를 정확히 추출하세요."
            )
            
            # JSON 파싱
            resp = resp.strip()
            if "```json" in resp:
                resp = resp.split("```json")[1].split("```")[0]
            elif "```" in resp:
                resp = resp.split("```")[1].split("```")[0]
            resp = resp.strip()
            
            plans = json.loads(resp)
            
            logger.info(f"   ✅ Vision 추출: {len(plans)}개")
            print(f"   ✅ Vision 추출: {len(plans)}개")
            
            for p in plans[:15]:
                print(f"      • {p['name']} ({p['monthly_fee']:,}원/월)")
            
            return plans
            
        except Exception as e:
            logger.error(f"   ❌ Vision 추출 실패: {e}")
            print(f"   ❌ Vision 추출 실패: {e}")
            return []

