"""
Vision Plan Agent
LLM이 화면을 보고 요금제를 찾아서 선택
"""
import json
import asyncio
import base64
from typing import Dict, Any
from playwright.async_api import Page

from ..core.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger()


class VisionPlanAgent:
    """Vision 기반 요금제 선택"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    async def select_plan_by_fee(
        self,
        page: Page,
        target_fee: int,
        carrier: str = "SKT"
    ) -> bool:
        """
        Vision이 화면 보고 요금제 선택
        
        Args:
            target_fee: 목표 월요금 (89000)
        """
        print(f"\n🤖 Vision: {target_fee:,}원 요금제 찾기")
        
        # 드롭다운 열기
        await self._open_dropdown(page)
        
        # 화면 캡처 (타임아웃 처리)
        try:
            screenshot = await page.screenshot(full_page=False, quality=70, type='jpeg', timeout=8000)
            screenshot_b64 = base64.b64encode(screenshot).decode()
            img_url = f"data:image/jpeg;base64,{screenshot_b64}"
        except Exception as e:
            print(f"  ❌ 스크린샷 실패: {e}")
            return False
        
        # Vision에게 요금제 찾기 요청
        prompt = f"""
화면에서 월요금 **{target_fee:,}원** 요금제를 찾으세요.

{{
  "found": true,
  "plan_name": "프라임",
  "click_text": "프라임"
}}

{target_fee:,}원이 없으면 found: false

**JSON만 출력.**
"""
        
        try:
            resp = await self.llm.complete_with_vision(prompt=prompt, image_url=img_url)
            
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            result = json.loads(resp)
            
            if not result.get("found"):
                print(f"  ❌ {target_fee:,}원 없음")
                return False
            
            click_text = result.get("click_text", "")
            print(f"  ✅ 발견: {result.get('plan_name')} - '{click_text}'")
            
            # JavaScript로 월요금 찾아서 클릭 (가장 확실!)
            clicked = await page.evaluate(f"""
                () => {{
                    const targetFee = {target_fee};
                    const all = document.querySelectorAll('*');
                    
                    for (const elem of all) {{
                        const text = elem.textContent;
                        if (text.length < 200 && text.includes('월')) {{
                            const match = text.match(/(\\d{{1,3}}),?(\\d{{3}})/);
                            if (match) {{
                                const fee = parseInt(match[0].replace(/,/g, ''));
                                if (fee === targetFee) {{
                                    const onclick = elem.getAttribute('onclick');
                                    if (onclick) {{
                                        eval(onclick);
                                        return true;
                                    }}
                                    elem.click();
                                    return true;
                                }}
                            }}
                        }}
                    }}
                    return false;
                }}
            """)
            
            if clicked:
                await asyncio.sleep(0.5)
                print(f"  ✅ 클릭 성공")
                
                # popup 닫기
                try:
                    await page.evaluate("document.querySelector('.popup_close')?.click()")
                    await asyncio.sleep(0.3)
                except:
                    pass
            
            return clicked
            
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            return False
    
    async def _open_dropdown(self, page: Page):
        """드롭다운 열기"""
        try:
            await page.evaluate("""
                document.querySelector('a[onclick*="popup"]')?.click();
                document.querySelector('button.bill-view')?.click();
                document.querySelector('.bill-view-more')?.click();
                document.querySelector('.plan_mod')?.click();
            """)
            await asyncio.sleep(2)
        except:
            pass
