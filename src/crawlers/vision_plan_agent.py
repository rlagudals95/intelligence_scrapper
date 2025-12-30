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
        self.cached_plans = []  # 처음 추출한 요금제 캐시
    
    async def select_plan_by_fee(
        self,
        page: Page,
        target_fee: int,
        carrier: str = "SKT"
    ) -> bool:
        """
        Vision + JavaScript로 요금제 선택
        
        Args:
            target_fee: 목표 월요금 (89000)
        """
        print(f"\n🤖 Vision: {target_fee:,}원 요금제")
        
        # 드롭다운 열기
        await self._open_dropdown(page)
        await asyncio.sleep(2)
        
        # 캐시 확인
        plan_name = None
        if self.cached_plans:
            print(f"  📦 캐시 확인 ({len(self.cached_plans)}개)")
            for plan in self.cached_plans:
                if plan.get('monthly_fee') == target_fee:
                    plan_name = plan.get('name', '')
                    print(f"  ✅ 캐시 발견: {plan_name}")
                    break
        
        if not plan_name:
            print(f"  ❌ 캐시에 없음")
            return False
        
        # JavaScript로 월요금 찾아서 클릭
        result = await page.evaluate(f"""
            () => {{
                const targetFee = {target_fee};
                const all = document.querySelectorAll('tr, li, div');
                let found = 0;
                
                for (const elem of all) {{
                    const text = elem.textContent;
                    if (text.length < 300 && text.includes('월')) {{
                        const match = text.match(/(\\d{{1,3}}),?(\\d{{3}})/);
                        if (match) {{
                            const fee = parseInt(match[0].replace(/,/g, ''));
                            if (fee === targetFee) {{
                                found++;
                                
                                // onclick 실행
                                const onclick = elem.getAttribute('onclick');
                                if (onclick) {{
                                    eval(onclick);
                                    return {{success: true, found: found}};
                                }}
                                
                                // 클릭
                                elem.click();
                                return {{success: true, found: found}};
                            }}
                        }}
                    }}
                }}
                
                return {{success: false, found: found}};
            }}
        """)
        
        if result.get('success'):
            print(f"  ✅ 클릭 성공 (매칭: {result.get('found', 0)}개)")
            await asyncio.sleep(0.5)
            
            # popup 닫기
            try:
                await page.evaluate("document.querySelector('.popup_close, .close')?.click()")
                await asyncio.sleep(0.3)
            except:
                pass
            
            return True
        else:
            print(f"  ❌ 클릭 실패 (매칭: {result.get('found', 0)}개)")
            return False
    
    async def _open_dropdown(self, page: Page):
        """드롭다운 열기 + 스크롤 (맨 아래까지)"""
        try:
            # 모든 가능한 버튼 클릭
            result = await page.evaluate("""
                () => {
                    let clicked = 0;
                    
                    // popup 링크
                    const popupLink = document.querySelector('a[onclick*="popup"], a[onclick*="price"]');
                    if (popupLink) {
                        popupLink.click();
                        clicked++;
                    }
                    
                    // 드롭다운 버튼들
                    const btns = document.querySelectorAll('button.bill-view, .bill-view-more, .plan_mod');
                    btns.forEach(btn => {
                        btn.click();
                        clicked++;
                    });
                    
                    return clicked;
                }
            """)
            print(f"  🔽 {result}개 버튼 클릭")
            
            # 드롭다운 컨테이너 스크롤 (맨 아래까지!)
            await page.evaluate("""
                () => {
                    // 스크롤 가능한 요금제 컨테이너 찾기
                    const scrollables = document.querySelectorAll('.popup, .bill-layer-box, .plan_list, .plan, ul, div[style*="overflow"]');
                    
                    scrollables.forEach(container => {
                        if (container.scrollHeight > container.clientHeight) {
                            // 스크롤 여러 번 (lazy loading 대응)
                            container.scrollTop = container.scrollHeight / 2;
                            setTimeout(() => {
                                container.scrollTop = container.scrollHeight;
                            }, 100);
                        }
                    });
                    
                    // 전체 페이지도 스크롤
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            await asyncio.sleep(1)  # 스크롤 후 로딩 대기
            print(f"  📜 드롭다운 스크롤 완료")
            
        except Exception as e:
            print(f"  ⚠️  드롭다운 열기 실패: {e}")
