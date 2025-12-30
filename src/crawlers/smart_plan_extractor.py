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
        페이지에서 모든 요금제 추출
        
        Returns:
            [{"name": "프라임", "monthly_fee": 89000}, ...]
        """
        logger.info("="*70)
        logger.info("📋 스마트 요금제 추출 시작")
        logger.info("="*70)
        
        # Step 1: Vision으로 드롭다운 버튼 찾기
        logger.info("\n[Step 1] 드롭다운 버튼 찾기 (Vision)")
        
        screenshot = await page.screenshot(full_page=False, quality=60, type='jpeg')
        screenshot_b64 = base64.b64encode(screenshot).decode()
        img_url = f"data:image/jpeg;base64,{screenshot_b64}"
        
        button_prompt = """
이 화면에서 "요금제" 선택 박스/버튼을 찾으세요.

보통:
- "요금제" 라벨
- 현재 선택된 요금제명 + 월요금
- 드롭다운 아이콘 (▼)

예: "프리미엄(OTT 택1) 월 109,000원 ▼"

현재 선택된 요금제의 **정확한 텍스트 일부**를 반환:

JSON:
{"button_text": "프리미엄"}

**클릭할 버튼을 찾을 수 있는 키워드만 반환하세요.**
"""
        
        try:
            resp = await self.llm.complete_with_vision(
                prompt=button_prompt,
                image_url=img_url,
                system_message="요금제 드롭다운 버튼을 찾으세요."
            )
            
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            button_info = json.loads(resp)
            button_text = button_info.get("button_text", "")
            
            logger.info(f"   🎯 버튼 키워드: '{button_text}'")
            
            if button_text:
                # 버튼 클릭
                await page.get_by_text(button_text, exact=False).first.click(force=True, timeout=3000)
                await asyncio.sleep(1)
                logger.info(f"   ✅ 드롭다운 열림")
                
        except Exception as e:
            logger.warning(f"   ⚠️ Vision 버튼 찾기 실패: {e}")
        
        # Fallback: ▼ 모두 클릭
        try:
            btns = await page.locator('*:has-text("▼")').all()
            for btn in btns[:3]:
                try:
                    await btn.click(force=True, timeout=500)
                    await asyncio.sleep(0.2)
                except:
                    pass
        except:
            pass
        
        await asyncio.sleep(1.5)
        
        # Step 2: Vision으로 모든 요금제 추출
        logger.info("\n[Step 2] 요금제 추출 (Vision)")
        
        screenshot = await page.screenshot(full_page=False, quality=70, type='jpeg')
        screenshot_b64 = base64.b64encode(screenshot).decode()
        img_url = f"data:image/jpeg;base64,{screenshot_b64}"
        
        plan_prompt = """
화면에서 **모든 요금제와 월요금**을 추출하세요.

예:
- 프라임 플러스    월 99,000원
- 프라임           월 89,000원
- 레귤러 플러스    월 79,000원
- 레귤러           월 69,000원

JSON 배열:
[
  {"name": "프라임 플러스", "monthly_fee": 99000},
  {"name": "프라임", "monthly_fee": 89000},
  {"name": "레귤러 플러스", "monthly_fee": 79000},
  {"name": "레귤러", "monthly_fee": 69000}
]

**보이는 모든 요금제를 추출하세요. JSON만 출력.**
"""
        
        try:
            resp = await self.llm.complete_with_vision(
                prompt=plan_prompt,
                image_url=img_url,
                system_message="모든 요금제를 정확히 추출하세요."
            )
            
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            plans = json.loads(resp)
            
            logger.info(f"   ✅ 요금제 추출: {len(plans)}개")
            for p in plans[:10]:
                logger.info(f"      • {p['name']} ({p['monthly_fee']:,}원/월)")
            
            return plans
            
        except Exception as e:
            logger.error(f"   ❌ Vision 추출 실패: {e}")
            return []

