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
        plan_name: str = None,
        carrier: str = "SKT"
    ) -> bool:
        """
        Vision 추론 기반 요금제 선택 (가격 우선 매칭)
        
        Args:
            target_fee: 목표 월요금 (89000) - 최우선 매칭 기준
            plan_name: 예상 요금제 이름 (보조 정보, 선택적)
        """
        print(f"\n🤖 Vision 추론: {target_fee:,}원 요금제 선택")
        if plan_name:
            print(f"  📋 참고 요금제명: {plan_name} (보조 정보)")
        
        # 1. 드롭다운 열기 및 스크롤
        await self._open_dropdown(page)
        await asyncio.sleep(2)
        
        # 2. 캐시에서 요금제 이름 확인 (비전 프롬프트에 활용)
        plan_name = None
        if self.cached_plans:
            for plan in self.cached_plans:
                if plan.get('monthly_fee') == target_fee:
                    plan_name = plan.get('name', '')
                    break
        
        # 3. 스크린샷 캡처
        screenshot = await page.screenshot(full_page=False, quality=80, type='jpeg', timeout=8000)
        screenshot_b64 = base64.b64encode(screenshot).decode()
        img_url = f"data:image/jpeg;base64,{screenshot_b64}"
        
        # 4. Vision LLM에게 시각적 추론 요청
        plan_name_hint = ""
        if plan_name:
            plan_name_hint = f"\n참고: 예상 요금제 이름은 '{plan_name}'입니다. (하지만 가격이 우선입니다)"
        
        prompt = f"""
이 화면에서 **월 {target_fee:,}원** 요금제를 선택하려고 합니다.

**중요: 가격({target_fee:,}원)을 1순위로 매칭하세요. 요금제 이름은 보조 정보입니다.**{plan_name_hint}

보통 요금제 선택요소는 요금제 또는 요금제 선택이라는 라벨 근처에 있습니다.

화면을 자세히 보고, **월 {target_fee:,}원** 가격이 표시된 요금제 블록의 **시각적 특징**을 설명해주세요:
1. **가격 우선**: 화면에서 **정확히 {target_fee:,}원** (또는 월 {target_fee:,}원)이 표시된 블록을 찾으세요.
2. 화면에서 몇 번째 블록인가요? (위에서부터)
3. 요금제 이름은 무엇인가요? (참고용)
4. 가격이 어떤 색상으로 표시되어 있나요?
5. 주변에 어떤 텍스트나 아이콘이 있나요?

**매칭 우선순위:**
1. 가격이 정확히 {target_fee:,}원인 블록 (최우선)
2. 요금제 이름이 일치하는 블록 (보조)
3. 위치 정보

그리고 이 요금제 블록을 클릭하기 위한 **구체적인 방법**을 제시해주세요:
1. 요소의 위치 (예: "위에서 두 번째 블록", "세 번째 항목")
2. 포함된 텍스트 (예: "월 {target_fee:,}원" - 필수, 요금제 이름 - 선택)
3. 시각적 특징 (예: "빨간색 가격", "회색 배경")

JSON 형식으로 답변해주세요:
{{
  "position": "위에서 두 번째 블록",
  "plan_name": "실제 화면의 요금제명",
  "price_text": "월 {target_fee:,}원",
  "visual_features": "빨간색 가격 텍스트, 회색 배경",
  "click_strategy": "월 {target_fee:,}원이 포함된 블록 전체를 클릭"
}}
"""
        
        try:
            resp = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=img_url,
                system_message="요금제 선택 UI 분석 전문가. 화면을 보고 정확한 클릭 방법을 제시합니다."
            )
            
            # JSON 파싱
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            vision_result = json.loads(resp)
            print(f"  👁️  Vision 분석 결과:")
            print(f"     - 위치: {vision_result.get('position', 'N/A')}")
            print(f"     - 요금제명: {vision_result.get('plan_name', 'N/A')}")
            print(f"     - 가격 텍스트: {vision_result.get('price_text', 'N/A')}")
            
            # 5. 🔥 핵심: HTML 기반 직접 선택 우선 시도 (드롭다운이 열렸다면 HTML에 모든 요소가 있음)
            html_click_success = await self._click_based_on_html(page, target_fee)
            
            if html_click_success:
                print(f"  ✅ HTML 기반 선택 성공")
                await asyncio.sleep(0.5)
                
                # popup 닫기
                try:
                    is_selected = await page.evaluate(f"""
                        (targetFee) => {{
                            const selected = document.querySelector('.opt_bill_list.on, .layer-bill-item.on, .plan_list_item.on');
                            if (selected) {{
                                const dataPrice = selected.getAttribute('data-billprice');
                                if (dataPrice && parseInt(dataPrice) === targetFee) {{
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """, target_fee)
                    
                    if is_selected:
                        await page.evaluate("document.querySelector('.popup_close, .closex, .close')?.click()")
                        await asyncio.sleep(0.3)
                except:
                    pass
                
                return True
            
            # 6. HTML 기반 실패 시 Vision 결과를 바탕으로 시도
            print(f"  🔄 HTML 기반 선택 실패, Vision 기반 시도")
            click_success = await self._click_based_on_vision(page, target_fee, vision_result)
            
            if click_success:
                await asyncio.sleep(0.5)
                
                # 🔥 핵심: popup을 무조건 닫지 말고, 선택이 반영되었는지 확인 후 닫기
                # 일부 사이트는 popup이 자동으로 닫히고, 일부는 수동으로 닫아야 함
                try:
                    # 선택이 반영되었는지 확인
                    is_selected = await page.evaluate(f"""
                        (targetFee) => {{
                            // 현재 선택된 요금제 확인
                            const selected = document.querySelector('.opt_bill_list.on, .layer-bill-item.on, .plan_list_item.on');
                            if (selected) {{
                                const dataPrice = selected.getAttribute('data-billprice');
                                if (dataPrice && parseInt(dataPrice) === targetFee) {{
                                    return true;
                                }}
                            }}
                            
                            // 화면에 표시된 요금제 가격 확인
                            const priceElems = document.querySelectorAll('.bill-charge .unit-w, .plan_price, .bill_price strong, span.unit-w');
                            for (const elem of priceElems) {{
                                const text = elem.textContent || '';
                                const textNoComma = text.replace(/,/g, '');
                                const match = textNoComma.match(/\\d{{5,6}}/);
                                if (match && parseInt(match[0]) === targetFee) {{
                                    return true;
                                }}
                            }}
                            
                            return false;
                        }}
                    """, target_fee)
                    
                    # 선택이 반영되었으면 popup 닫기 (일부 사이트는 자동으로 닫힘)
                    if is_selected:
                        await page.evaluate("document.querySelector('.popup_close, .closex, .close')?.click()")
                        await asyncio.sleep(0.3)
                except:
                    pass
                
                return True
            else:
                print(f"  ❌ Vision 기반 클릭 실패, 폴백 시도")
                # 폴백: 기존 방식으로 재시도
                return await self._fallback_click(page, target_fee)
                
        except Exception as e:
            print(f"  ⚠️  Vision 추론 실패: {e}")
            import traceback
            traceback.print_exc()
            # 폴백: 기존 방식으로 재시도
            return await self._fallback_click(page, target_fee)
    
    async def _click_based_on_html(self, page: Page, target_fee: int) -> bool:
        """HTML 기반 직접 선택 (드롭다운이 열렸다면 HTML에 모든 요소가 있음)"""
        url = page.url
        site_type = self._detect_site_type(url)
        
        # 드롭다운이 열려있는지 확인
        is_dropdown_open = await page.evaluate("""
            () => {
                // 드롭다운 컨테이너가 보이는지 확인
                const containers = [
                    '.myModal-content.open',
                    '.plan_list[style*="display: block"]',
                    '.bill-layer-box:not([style*="display: none"])',
                    'ul.layer-bill-item',
                    'ul.opt_bill_list'
                ];
                
                for (const sel of containers) {
                    const elem = document.querySelector(sel);
                    if (elem) {
                        const style = window.getComputedStyle(elem);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            return true;
                        }
                    }
                }
                
                // li.layer-bill-item 또는 li.opt_bill_list가 있으면 열려있는 것으로 간주
                const items = document.querySelectorAll('li.layer-bill-item, li.opt_bill_list, .plan_list_item');
                return items.length > 0;
            }
        """)
        
        if not is_dropdown_open:
            print(f"     ⚠️  드롭다운이 열려있지 않음, 다시 열기 시도")
            await self._open_dropdown(page)
            await asyncio.sleep(1)
        
        result = await page.evaluate(f"""
            (info) => {{
                const {{ targetFee, siteType }} = info;
                
                // 🔥 핵심: data-billprice 속성으로 직접 찾기 (가장 확실한 방법)
                const directMatch = document.querySelector(`[data-billprice="${{targetFee}}"]`);
                if (directMatch) {{
                    // 요소가 보이도록 스크롤
                    const container = directMatch.closest('.myModal-content, .plan_list, .bill-layer-box, .popup, ul');
                    if (container) {{
                        container.focus();
                        container.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                        directMatch.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
                    }}
                    
                    // 클릭
                    const onclick = directMatch.getAttribute('onclick');
                    if (onclick) {{
                        eval(onclick);
                        return {{success: true, method: 'data-billprice-onclick'}};
                    }}
                    directMatch.click();
                    return {{success: true, method: 'data-billprice-click'}};
                }}
                
                // 사이트별 셀렉트 요소 선택자로 찾기
                let selectors = [];
                if (siteType === "띵폰" || siteType === "ddingphone") {{
                    selectors = ['li.opt_bill_list'];
                }} else if (siteType === "하이폰" || siteType === "hi-phone") {{
                    selectors = ['.plan_list_item'];
                }} else if (siteType === "투게더몰" || siteType === "together" || siteType === "엘지티샵" || siteType === "lgt" || siteType === "폰슐랭샵" || siteType === "phone") {{
                    selectors = ['li.layer-bill-item'];
                }} else {{
                    selectors = ['li.opt_bill_list', 'li.layer-bill-item', '.plan_list_item', 'li[data-billprice]'];
                }}
                
                // 모든 후보 찾기 (offsetHeight 체크 없이!)
                let candidates = [];
                selectors.forEach(sel => {{
                    const found = Array.from(document.querySelectorAll(sel));
                    found.forEach(elem => {{
                        if (elem && elem.parentNode) {{
                            candidates.push(elem);
                        }}
                    }});
                }});
                
                // data-billprice로 필터링
                const matches = candidates.filter(elem => {{
                    const dataPrice = elem.getAttribute('data-billprice');
                    if (dataPrice && parseInt(dataPrice) === targetFee) {{
                        return true;
                    }}
                    
                    // 텍스트에서도 확인
                    const text = elem.textContent || '';
                    const textNoComma = text.replace(/,/g, '');
                    return textNoComma.includes(targetFee.toString());
                }});
                
                if (matches.length === 0) {{
                    return {{success: false, reason: 'no_matches', searched: candidates.length}};
                }}
                
                // 첫 번째 매칭 요소 선택
                const targetElement = matches[0];
                
                // 스크롤 및 포커스
                const container = targetElement.closest('.myModal-content, .plan_list, .bill-layer-box, .popup, ul');
                if (container) {{
                    container.focus();
                    container.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                    targetElement.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
                }}
                
                // 클릭
                const onclick = targetElement.getAttribute('onclick');
                if (onclick) {{
                    eval(onclick);
                    return {{success: true, method: 'onclick', matches: matches.length}};
                }}
                targetElement.click();
                return {{success: true, method: 'click', matches: matches.length}};
            }}
        """, {
            "targetFee": target_fee,
            "siteType": site_type
        })
        
        if result.get('success'):
            print(f"     ✅ HTML 기반 클릭 성공 ({result.get('method', 'unknown')}, 매칭: {result.get('matches', 1)}개)")
            return True
        else:
            print(f"     ❌ HTML 기반 클릭 실패: {result.get('reason', 'unknown')} (검색: {result.get('searched', 0)}개)")
            return False
    
    async def _click_based_on_vision(
        self,
        page: Page,
        target_fee: int,
        vision_result: Dict[str, Any]
    ) -> bool:
        """힌트 기반 + Vision 결과를 바탕으로 정확한 요소 클릭"""
        plan_name = vision_result.get('plan_name', '')
        price_text = vision_result.get('price_text', '')
        position = vision_result.get('position', '')
        
        # 현재 URL로 사이트 타입 판별
        url = page.url
        site_type = self._detect_site_type(url)
        
        # JavaScript로 힌트 기반 + Vision 결과로 요소 찾기
        result = await page.evaluate(f"""
            (info) => {{
                const {{ targetFee, planName, priceText, position, siteType }} = info;
                
                // 사이트별 셀렉트 요소 선택자 (힌트 기반)
                let selectors = [];
                if (siteType === "띵폰" || siteType === "ddingphone") {{
                    // 띵폰: li.opt_bill_list (data-billprice 속성 또는 .bill_price strong)
                    selectors = ['li.opt_bill_list'];
                }} else if (siteType === "하이폰" || siteType === "hi-phone") {{
                    // 하이폰: .plan_list_item
                    selectors = ['.plan_list_item'];
                }} else if (siteType === "투게더몰" || siteType === "together") {{
                    // 투게더몰: li.layer-bill-item
                    selectors = ['li.layer-bill-item'];
                }} else if (siteType === "폰슐랭샵" || siteType === "phone") {{
                    // 폰슐랭샵: li.layer-bill-item
                    selectors = ['li.layer-bill-item'];
                }} else if (siteType === "성지폰" || siteType === "sungji") {{
                    // 성지폰: 팝업 내부 요소
                    selectors = ['li', 'tr', 'div[class*="plan"]'];
                }} else if (siteType === "엘지티샵" || siteType === "lgt") {{
                    // 엘지티샵: li.layer-bill-item
                    selectors = ['li.layer-bill-item'];
                }} else {{
                    // 폴백: 공통 선택자
                    selectors = ['li.opt_bill_list', 'li.layer-bill-item', '.plan_list_item', 'li', 'tr'];
                }}
                
                // 모든 잠재적 요금제 블록 찾기 (숨겨진 요소 포함)
                let candidates = [];
                selectors.forEach(sel => {{
                    // querySelectorAll은 숨겨진 요소도 찾음
                    const found = Array.from(document.querySelectorAll(sel));
                    
                    // 각 요소가 실제로 DOM에 있는지 확인 (display: none이어도 DOM에 있으면 포함)
                    found.forEach(elem => {{
                        // offsetParent가 null이어도 DOM에 있으면 포함 (숨겨진 요소)
                        // 단, 실제로 존재하는 요소만
                        if (elem && elem.parentNode) {{
                            candidates.push(elem);
                        }}
                    }});
                }});
                
                // 중복 제거
                candidates = [...new Set(candidates)];
                
                // 숨겨진 요소도 포함하여 검색 (스크롤 영역 밖에 있어도)
                console.log(`검색된 후보: ${{candidates.length}}개`);
                
                // Vision이 제시한 특징으로 필터링 (가격 우선!)
                // 🔥 offsetHeight 체크 제거: DOM에 있으면 클릭 가능 (스크롤로 보이게 할 수 있음)
                const matches = candidates.filter(elem => {{
                    const text = elem.textContent || '';
                    const textNoComma = text.replace(/,/g, '');
                    
                    // 1순위: data-billprice 속성 확인 (띵폰, 투게더몰 등)
                    const dataPrice = elem.getAttribute('data-billprice');
                    if (dataPrice && parseInt(dataPrice) === targetFee) {{
                        return true;
                    }}
                    
                    // 2순위: 텍스트에서 가격 찾기
                    const hasPrice = textNoComma.includes(targetFee.toString());
                    if (!hasPrice) return false;
                    
                    // 3순위: 요금제 이름이 있으면 일치하는지 확인 (보조 정보)
                    const hasPlanName = !planName || text.includes(planName);
                    
                    return hasPrice && hasPlanName;
                }});
                
                if (matches.length === 0) {{
                    return {{success: false, reason: 'no_matches', searched: candidates.length}};
                }}
                
                // 위치 정보가 있다면 활용 (예: "두 번째" -> index 1)
                let targetElement = matches[0];
                if (position && position.includes('번째')) {{
                    const match = position.match(/(\\d+)/);
                    if (match) {{
                        const index = parseInt(match[1]) - 1;
                        if (index >= 0 && index < matches.length) {{
                            targetElement = matches[index];
                        }}
                    }}
                }}
                
                // 요소가 숨겨져 있거나 스크롤 영역 밖에 있으면 부모 컨테이너 찾아서 스크롤
                const container = targetElement.closest('.myModal-content, .plan_list, .bill-layer-box, .popup, ul[class*="bill"], div[style*="overflow"]');
                if (container) {{
                    // 컨테이너에 포커스/호버
                    container.focus();
                    container.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                    
                    // 요소가 보이도록 컨테이너 내에서 스크롤
                    const containerRect = container.getBoundingClientRect();
                    const elementRect = targetElement.getBoundingClientRect();
                    
                    // 요소가 컨테이너 밖에 있으면 스크롤
                    if (elementRect.top < containerRect.top || elementRect.bottom > containerRect.bottom) {{
                        const scrollTop = container.scrollTop + (elementRect.top - containerRect.top) - (containerRect.height / 2);
                        container.scrollTop = Math.max(0, scrollTop);
                    }}
                }}
                
                // 요소를 화면 중앙으로 스크롤 (전체 페이지 기준)
                targetElement.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
                
                // 클릭 가능한 부모 찾기
                const clickable = targetElement.closest('li, tr, a, button, div[onclick]') || targetElement;
                
                // onclick 실행 또는 클릭
                const onclick = clickable.getAttribute('onclick');
                if (onclick) {{
                    eval(onclick);
                    return {{success: true, method: 'onclick', matches: matches.length}};
                }}
                
                clickable.click();
                return {{success: true, method: 'click', matches: matches.length}};
            }}
        """, {
            "targetFee": target_fee,
            "planName": plan_name,
            "priceText": price_text,
            "position": position,
            "siteType": site_type
        })
        
        if result.get('success'):
            print(f"     ✅ 힌트+Vision 기반 클릭 성공 ({result.get('method', 'unknown')}, 매칭: {result.get('matches', 0)}개)")
            return True
        else:
            print(f"     ❌ 힌트+Vision 기반 클릭 실패: {result.get('reason', 'unknown')} (검색: {result.get('searched', 0)}개)")
            return False
    
    async def _fallback_click(self, page: Page, target_fee: int) -> bool:
        """폴백: 기존 JavaScript 방식"""
        print(f"  🔄 폴백 방식으로 재시도...")
        result = await page.evaluate(f"""
            (targetFee) => {{
                const all = document.querySelectorAll('tr, li, div');
                
                for (const elem of all) {{
                    const text = elem.textContent;
                    if (text.length < 300 && text.includes('월')) {{
                        const match = text.match(/(\\d{{1,3}}),?(\\d{{3}})/);
                        if (match) {{
                            const fee = parseInt(match[0].replace(/,/g, ''));
                            if (fee === targetFee) {{
                                const onclick = elem.getAttribute('onclick');
                                if (onclick) {{
                                    eval(onclick);
                                    return {{success: true}};
                                }}
                                elem.click();
                                return {{success: true}};
                            }}
                        }}
                    }}
                }}
                
                return {{success: false}};
            }}
        """, target_fee)
        
        return result.get('success', False)
    
    async def _open_dropdown(self, page: Page):
        """힌트 기반 드롭다운 열기 + 스크롤 (사이트별 최적화)"""
        try:
            # 현재 URL로 사이트 판별
            url = page.url
            site_type = self._detect_site_type(url)
            print(f"  🏪 사이트 타입: {site_type}")
            
            # 사이트별 최적화된 드롭다운 열기
            result = await page.evaluate(f"""
                () => {{
                    let clicked = 0;
                    const siteType = "{site_type}";
                    
                    // 사이트별 셀렉트 부모 버튼 클릭
                    if (siteType === "띵폰" || siteType === "ddingphone") {{
                        // 띵폰: button.bill-view
                        const btn = document.querySelector('button.bill-view');
                        if (btn) {{ btn.click(); clicked++; }}
                    }} else if (siteType === "하이폰" || siteType === "hi-phone") {{
                        // 하이폰: .plan_mod
                        const btn = document.querySelector('.plan_mod');
                        if (btn) {{ btn.click(); clicked++; }}
                    }} else if (siteType === "투게더몰" || siteType === "together") {{
                        // 투게더몰: button.bill-view-more 또는 button.btn-bill-change
                        const btn1 = document.querySelector('button.bill-view-more');
                        const btn2 = document.querySelector('button.btn-bill-change');
                        if (btn1) {{ btn1.click(); clicked++; }}
                        if (btn2) {{ btn2.click(); clicked++; }}
                    }} else if (siteType === "폰슐랭샵" || siteType === "phone") {{
                        // 폰슐랭샵: button.bill-view-more
                        const btn = document.querySelector('button.bill-view-more');
                        if (btn) {{ btn.click(); clicked++; }}
                    }} else if (siteType === "성지폰" || siteType === "sungji") {{
                        // 성지폰: a[onclick*="open_popup('price')"]
                        const link = document.querySelector('a[onclick*="open_popup"], a[onclick*="price"]');
                        if (link) {{ link.click(); clicked++; }}
                    }} else if (siteType === "엘지티샵" || siteType === "lgt") {{
                        // 엘지티샵: button.bill-view-more
                        const btn = document.querySelector('button.bill-view-more');
                        if (btn) {{ btn.click(); clicked++; }}
                    }} else {{
                        // 폴백: 모든 가능한 버튼 시도
                        const popupLink = document.querySelector('a[onclick*="popup"], a[onclick*="price"]');
                        if (popupLink) {{ popupLink.click(); clicked++; }}
                        
                        const btns = document.querySelectorAll('button.bill-view, button.bill-view-more, .plan_mod, button.btn-bill-change');
                        btns.forEach(btn => {{
                            if (btn.offsetParent !== null) {{ // visible check
                                btn.click();
                                clicked++;
                            }}
                        }});
                    }}
                    
                    return clicked;
                }}
            """)
            print(f"  🔽 {result}개 버튼 클릭")
            await asyncio.sleep(1)  # 드롭다운 열림 대기
            
            # 드롭다운 컨테이너 찾기 및 포커스/호버 후 스크롤
            scroll_result = await page.evaluate(f"""
                () => {{
                    const siteType = "{site_type}";
                    
                    // 사이트별 셀렉트 요소 컨테이너 찾기
                    let containers = [];
                    if (siteType === "띵폰" || siteType === "ddingphone") {{
                        containers = [document.querySelector('.myModal-content'), document.querySelector('.modal-bill-list')];
                    }} else if (siteType === "하이폰" || siteType === "hi-phone") {{
                        containers = [document.querySelector('.plan_list')];
                    }} else if (siteType === "투게더몰" || siteType === "together") {{
                        containers = [document.querySelector('.bill-layer-box'), document.querySelector('ul')];
                    }} else if (siteType === "폰슐랭샵" || siteType === "phone") {{
                        containers = [document.querySelector('.bill-layer-box'), document.querySelector('ul')];
                    }} else if (siteType === "엘지티샵" || siteType === "lgt") {{
                        containers = [document.querySelector('.bill-layer-box'), document.querySelector('ul')];
                    }} else {{
                        // 폴백: 모든 가능한 컨테이너
                        containers = [
                            document.querySelector('.myModal-content'),
                            document.querySelector('.plan_list'),
                            document.querySelector('.bill-layer-box'),
                            document.querySelector('.popup'),
                            document.querySelector('ul[class*="bill"]'),
                            document.querySelector('div[style*="overflow"]')
                        ];
                    }}
                    
                    let scrolled = 0;
                    containers.forEach(container => {{
                        if (!container) return;
                        
                        // 1. 드롭다운 컨테이너에 포커스/호버 (중요!)
                        container.focus();
                        container.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                        container.dispatchEvent(new MouseEvent('mouseover', {{ bubbles: true }}));
                        
                        // 2. 스크롤 가능한지 확인
                        const isScrollable = container.scrollHeight > container.clientHeight;
                        if (isScrollable) {{
                            // 점진적으로 스크롤 (lazy loading 대응)
                            const scrollSteps = 5;
                            const stepSize = container.scrollHeight / scrollSteps;
                            
                            for (let i = 1; i <= scrollSteps; i++) {{
                                setTimeout(() => {{
                                    container.scrollTop = stepSize * i;
                                }}, i * 100);
                            }}
                            
                            // 최종적으로 맨 아래로
                            setTimeout(() => {{
                                container.scrollTop = container.scrollHeight;
                            }}, (scrollSteps + 1) * 100);
                            
                            scrolled++;
                        }}
                    }});
                    
                    return {{ scrolled, containersFound: containers.filter(c => c !== null).length }};
                }}
            """)
            print(f"  📜 드롭다운 스크롤: {scroll_result.get('scrolled', 0)}개 컨테이너 (발견: {scroll_result.get('containersFound', 0)}개)")
            
            # 숨겨진 요소까지 검사하기 위해 추가 대기 및 스크롤
            await asyncio.sleep(2)  # 스크롤 애니메이션 및 lazy loading 대기
            
            # 한 번 더 스크롤하여 숨겨진 요소 로드
            await page.evaluate("""
                () => {
                    const scrollables = document.querySelectorAll('.myModal-content, .plan_list, .bill-layer-box, .popup, ul[class*="bill"], div[style*="overflow"]');
                    scrollables.forEach(container => {
                        if (container && container.scrollHeight > container.clientHeight) {
                            // 포커스 유지
                            container.focus();
                            container.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));
                            
                            // 맨 아래로 스크롤
                            container.scrollTop = container.scrollHeight;
                        }
                    });
                }
            """)
            await asyncio.sleep(0.5)  # 최종 로딩 대기
            print(f"  ✅ 드롭다운 스크롤 완료 (숨겨진 요소 검사 준비)")
            
        except Exception as e:
            print(f"  ⚠️  드롭다운 열기 실패: {e}")
    
    def _detect_site_type(self, url: str) -> str:
        """URL로 사이트 타입 판별"""
        url_lower = url.lower()
        if 'ddingphone' in url_lower:
            return "띵폰"
        elif 'hi-phone' in url_lower:
            return "하이폰"
        elif 'together' in url_lower or '투게더' in url_lower:
            return "투게더몰"
        elif 'phone' in url_lower and 'shop' in url_lower:
            return "폰슐랭샵"
        elif 'sungji' in url_lower or '성지' in url_lower:
            return "성지폰"
        elif 'lgt' in url_lower or 'lg' in url_lower:
            return "엘지티샵"
        else:
            return "unknown"
