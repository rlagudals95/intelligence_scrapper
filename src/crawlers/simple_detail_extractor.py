"""
단순 상세페이지 추출기
LLM Vision 추론 중심, 선택자 최소화
"""
import json
import asyncio
import base64
import hashlib
import datetime
from typing import Dict, Any, List
from playwright.async_api import Page

from ..core.llm_client import LLMClient
from ..utils.logger import get_logger
from ..models.phase3_schemas import (
    ScrapingResult,
    Product,
    Policy,
    MobilePlan,
    PricingDetails,
    SourceInfo,
    JoinType,
    DiscountType,
    parse_storage
)
from .vision_plan_agent import VisionPlanAgent

logger = get_logger()


class SimpleDetailExtractor:
    """
    단순 상세페이지 추출기
    
    원칙:
    1. LLM Vision으로 화면 이해
    2. 텍스트 기반 클릭
    3. 복잡한 선택자 사용 안 함
    """
    
    # 요금제 필터
    PLAN_FILTERS = {
        "GALAXY_S25": {
            "SKT": {"번호이동": [89000, 79000, 69000], "기기변경": [89000, 79000, 69000]},
            "KT": {"번호이동": [100000, 80000, 61000], "기기변경": [100000, 80000, 61000]},
            "LGU": {"번호이동": [85000, 61000], "기기변경": [85000, 61000]},
        },
        "IPHONE17": {
            "SKT": {"번호이동": [89000, 79000, 69000], "기기변경": [89000, 79000, 69000]},
            "KT": {"번호이동": [100000, 80000, 61000], "기기변경": [100000, 80000, 61000]},
            "LGU": {"번호이동": [85000, 61000], "기기변경": [85000, 61000]},
        }
    }
    
    def __init__(self, llm_client: LLMClient, model_name: str = "GALAXY_S25"):
        self.llm = llm_client
        self.model_name = model_name
        self.vision_agent = VisionPlanAgent(llm_client)  # Vision Agent 초기화
    
    async def collect_all_policies(
        self,
        page: Page,
        url: str,
        site_name: str = "Unknown"
    ) -> ScrapingResult:
        """
        모든 정책 수집 (단순 버전)
        
        Returns:
            ScrapingResult
        """
        print("\n" + "="*70)
        print(f"🚀 단순 추출기: {site_name}")
        print("="*70)
        
        # Step 1: 고유 요금 목록 생성
        collected = []
        
        if self.model_name not in self.PLAN_FILTERS:
            print("⚠️  필터 조건 없음")
            return ScrapingResult(source=SourceInfo(site=site_name, url=url), products=[])
        
        filters = self.PLAN_FILTERS[self.model_name]
        
        # 모든 고유 요금 추출
        all_target_fees = set()
        for carrier_filters in filters.values():
            for join_fees in carrier_filters.values():
                all_target_fees.update(join_fees)
        
        all_target_fees = sorted(all_target_fees, reverse=False)  # 낮은 요금부터 (화면 안정성)
        
        print(f"\n모든 요금제: {all_target_fees}")
        
        # Step 1.5: 화면에 있는 요금제 미리 확인 (Vision 1회만!)
        print(f"\n화면 요금제 확인 중...")
        available_fees = await self._get_available_fees(page)
        print(f"  화면에 있는 요금제: {available_fees}")
        
        # 🔥 핵심: 필터에 있는 요금제만 시도 (필터에 없는 요금제는 제외)
        if not available_fees or len(available_fees) < len(all_target_fees) * 0.5:
            print(f"  ⚠️  Vision으로 찾은 요금제가 부족함, 필터의 모든 요금제를 시도")
            target_fees_to_try = all_target_fees
        else:
            # 화면에 있고 필터에도 있는 요금제만 시도
            target_fees_to_try = [fee for fee in all_target_fees if fee in available_fees]
            print(f"  📋 필터에 없는 요금제 제외: {[f for f in available_fees if f not in all_target_fees]}")
        
        print(f"  시도할 요금제: {target_fees_to_try}")
        
        # Step 2: 각 요금제별로 (핵심 순서!)
        for target_fee in target_fees_to_try:
            print(f"\n{'='*70}")
            print(f"💰 요금제: {target_fee:,}원")
            print(f"{'='*70}")
            
            # 요금제 선택 (Vision Agent)
            plan_selected = await self.vision_agent.select_plan_by_fee(page, target_fee)
            
            if not plan_selected:
                print(f"  ❌ {target_fee:,}원 요금제 선택 실패, skip")
                continue
            
            # 🔥 핵심: 요금제가 실제로 선택되었는지 확인
            is_actually_selected = await self._verify_plan_selected(page, target_fee)
            if not is_actually_selected:
                print(f"  ⚠️  {target_fee:,}원 요금제 선택이 반영되지 않음, 재시도")
                plan_selected = await self.vision_agent.select_plan_by_fee(page, target_fee)
                is_actually_selected = await self._verify_plan_selected(page, target_fee)
                if not is_actually_selected:
                    print(f"  ❌ {target_fee:,}원 요금제 선택 재시도 실패, skip")
                    continue
            
            print(f"  ✅ {target_fee:,}원 요금제 선택 완료 및 검증됨")
            await asyncio.sleep(1)
            
            # Step 3: 이 요금제로 모든 통신사 × 가입유형 조합 수집
            # 🔥 핵심: 필터 조건에 맞는 조합만 시도
            for carrier in ["SKT", "KT", "LGU"]:
                for join_type in ["번호이동", "기기변경"]:
                    
                    # 필터 조건 확인: 이 조합이 필터에 있는지 확인
                    if target_fee not in filters.get(carrier, {}).get(join_type, []):
                        print(f"  [{carrier} / {join_type}] 스킵 (필터에 없음)")
                        continue
                    
                    print(f"  [{carrier} / {join_type}] 시도")
                    
                    # 🔥 핵심: 통신사/가입유형 변경 전에 요금제가 여전히 선택되어 있는지 확인
                    is_still_selected = await self._verify_plan_selected(page, target_fee)
                    if not is_still_selected:
                        print(f"    ⚠️  요금제가 초기화됨, 다시 선택")
                        await self.vision_agent.select_plan_by_fee(page, target_fee)
                        await asyncio.sleep(0.5)
                    
                    # 통신사 선택 (여러 표기 시도)
                    carrier_texts = [carrier]
                    if carrier == "LGU":
                        carrier_texts = ["LGU", "LG U+", "U+", "LG"]
                    
                    clicked_carrier = False
                    for carrier_text in carrier_texts:
                        clicked_carrier = await self._click_by_text(page, carrier_text)
                        if clicked_carrier:
                            break
                    
                    await asyncio.sleep(0.5)
                    
                    # 🔥 핵심: 통신사 변경 후에도 요금제가 유지되는지 확인
                    is_still_selected = await self._verify_plan_selected(page, target_fee)
                    if not is_still_selected:
                        print(f"    ⚠️  통신사 변경 후 요금제 초기화됨, 다시 선택")
                        await self.vision_agent.select_plan_by_fee(page, target_fee)
                        await asyncio.sleep(0.5)
                    
                    if not clicked_carrier:
                        print(f"    ⚠️  {carrier} 클릭 실패")
                        continue
                    
                    # 가입유형 선택
                    clicked_join = await self._click_by_text(page, join_type)
                    await asyncio.sleep(0.5)
                    
                    # 🔥 핵심: 가입유형 변경 후에도 요금제가 유지되는지 확인
                    is_still_selected = await self._verify_plan_selected(page, target_fee)
                    if not is_still_selected:
                        print(f"    ⚠️  가입유형 변경 후 요금제 초기화됨, 다시 선택")
                        await self.vision_agent.select_plan_by_fee(page, target_fee)
                        await asyncio.sleep(0.5)
                    
                    if not clicked_join:
                        print(f"    ⚠️  {join_type} 클릭 실패")
                        continue
                    
                    # 가격 추출
                    pricing = await self._extract_pricing(page)
                    
                    if pricing and (pricing.get('retail_price') or pricing.get('installment_principal')):
                        # 🔥 핵심: 추출된 가격의 요금제가 맞는지 확인
                        extracted_fee = pricing.get('plan_monthly_fee', 0)
                        if extracted_fee and abs(extracted_fee - target_fee) > 1000:  # 1000원 이상 차이나면 다른 요금제
                            print(f"    ⚠️  추출된 요금제({extracted_fee:,}원)가 목표({target_fee:,}원)와 다름")
                            continue
                        
                        collected.append({
                            "carrier": carrier,
                            "join_type": join_type,
                            "target_fee": target_fee,
                            "pricing": pricing
                        })
                        print(f"    ✅ 정책 수집 (요금제: {extracted_fee or target_fee:,}원)")
                    else:
                        print(f"    ⚠️  가격 데이터 없음")
        
        # Step 3: 스키마 변환
        print(f"\n📊 총 {len(collected)}개 정책 수집")
        result = self._convert_to_schema(collected, url, site_name)
        
        return result
    
    async def _click_by_text(self, page: Page, text: str) -> bool:
        """텍스트, 이미지, 다양한 표기로 요소 찾아서 클릭"""
        
        # 가입유형 매핑
        text_variants = [text]
        if text == "번호이동":
            text_variants = ["번호이동", "통신사이동", "번이", "통신사 이동"]
        elif text == "기기변경":
            text_variants = ["기기변경", "기변", "기기 변경"]
        elif text == "LGU":
            text_variants = ["LGU", "LG U+", "U+", "LG"]
        
        # 모든 변형 시도
        for variant in text_variants:
            # 전략 1: 텍스트
            try:
                await page.get_by_text(variant, exact=False).first.click(force=True, timeout=500)
                return True
            except:
                pass
            
            # 전략 2: 이미지 (alt, src)
            try:
                await page.locator(f'img[alt*="{variant}"], img[src*="{variant.lower()}"]').first.click(force=True, timeout=500)
                return True
            except:
                pass
            
            # 전략 3: JavaScript로 이미지 또는 텍스트 찾기
            try:
                result = await page.evaluate(f"""
                    () => {{
                        const searchText = "{variant}";
                        
                        // 이미지 검색
                        const imgs = document.querySelectorAll('img');
                        for (const img of imgs) {{
                            const alt = (img.alt || '').toLowerCase();
                            const src = (img.src || '').toLowerCase();
                            const searchLower = searchText.toLowerCase();
                            
                            if (alt.includes(searchLower) || src.includes(searchLower)) {{
                                const parent = img.closest('button, a, div[onclick], label, div[class*="btn"]');
                                if (parent) {{
                                    parent.click();
                                    return true;
                                }}
                                img.click();
                                return true;
                            }}
                        }}
                        
                        // 텍스트 검색
                        const all = document.querySelectorAll('button, a, div, span, label');
                        for (const elem of all) {{
                            if (elem.textContent.includes(searchText)) {{
                                elem.click();
                                return true;
                            }}
                        }}
                        
                        return false;
                    }}
                """)
                
                if result:
                    return True
            except:
                pass
        
        return False
    
    async def _verify_plan_selected(self, page: Page, target_fee: int) -> bool:
        """요금제가 실제로 선택되었는지 확인"""
        try:
            result = await page.evaluate(f"""
                (targetFee) => {{
                    // 현재 화면에 표시된 요금제 가격 찾기
                    const selectors = [
                        '.bill-charge .unit-w',           // 띵폰, 투게더몰
                        '.plan_price',                    // 하이폰
                        '.bill_price strong',             // 공통
                        'span.unit-w',                    // 공통
                        '[data-billprice]'                // data 속성
                    ];
                    
                    for (const sel of selectors) {{
                        const elem = document.querySelector(sel);
                        if (!elem) continue;
                        
                        // 텍스트에서 가격 추출
                        const text = elem.textContent || '';
                        const textNoComma = text.replace(/,/g, '');
                        const match = textNoComma.match(/\\d{{5,6}}/);
                        
                        if (match) {{
                            const fee = parseInt(match[0]);
                            if (fee === targetFee) {{
                                return true;
                            }}
                        }}
                        
                        // data-billprice 속성 확인
                        const dataPrice = elem.getAttribute('data-billprice') || 
                                        elem.closest('[data-billprice]')?.getAttribute('data-billprice');
                        if (dataPrice && parseInt(dataPrice) === targetFee) {{
                            return true;
                        }}
                    }}
                    
                    // 선택된 상태 클래스 확인
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
            
            return result
        except Exception as e:
            print(f"      ⚠️  요금제 검증 실패: {e}")
            return False
    
    async def _get_available_fees(self, page: Page) -> List[int]:
        """화면에 있는 모든 요금제의 월요금 추출 (JavaScript + Vision 복합)"""
        try:
            # 드롭다운 열기 (VisionPlanAgent의 로직 사용)
            await self.vision_agent._open_dropdown(page)
            await asyncio.sleep(2)  # 스크롤 및 로딩 대기
            
            # 🔥 핵심: JavaScript로 직접 data-billprice 속성에서 모든 요금제 찾기
            js_fees = await page.evaluate("""
                () => {
                    const fees = new Set();
                    
                    // data-billprice 속성에서 찾기
                    const elementsWithPrice = document.querySelectorAll('[data-billprice]');
                    elementsWithPrice.forEach(elem => {
                        const price = elem.getAttribute('data-billprice');
                        if (price) {
                            fees.add(parseInt(price));
                        }
                    });
                    
                    // 텍스트에서 가격 패턴 찾기 (월 XXX,XXX원)
                    const allText = document.body.innerText;
                    const priceMatches = allText.match(/월\\s*(\\d{1,3}(?:,\\d{3})*)\\s*원/g);
                    if (priceMatches) {
                        priceMatches.forEach(match => {
                            const numStr = match.replace(/[월\\s원,]/g, '');
                            const num = parseInt(numStr);
                            if (num >= 20000 && num <= 200000) {  // 합리적인 범위
                                fees.add(num);
                            }
                        });
                    }
                    
                    return Array.from(fees).sort((a, b) => a - b);
                }
            """)
            
            print(f"  🔍 JavaScript로 찾은 요금제: {js_fees}")
            
            # Vision으로도 확인 (보조)
            screenshot = await page.screenshot(full_page=False, quality=60, type='jpeg', timeout=8000)
            screenshot_b64 = base64.b64encode(screenshot).decode()
            img_url = f"data:image/jpeg;base64,{screenshot_b64}"
            
            prompt = """
화면에 있는 모든 요금제를 나열하세요. 스크롤해서 모든 요금제를 확인하세요:

[
  {"name": "프리미어 슈퍼", "monthly_fee": 115000},
  {"name": "프리미어 에센셜", "monthly_fee": 85000},
  {"name": "심플 플러스", "monthly_fee": 61000}
]

**모든 요금제를 추출하세요. JSON 배열만 출력.**
"""
            
            try:
                resp = await self.llm.complete_with_vision(prompt=prompt, image_url=img_url)
                resp = resp.strip()
                if "```" in resp:
                    resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
                resp = resp.strip()
                
                import json
                plans = json.loads(resp)
                
                # 요금제 정보 캐싱
                self.vision_agent.cached_plans = plans
                
                vision_fees = [int(p['monthly_fee']) for p in plans if 'monthly_fee' in p]
                print(f"  👁️  Vision으로 찾은 요금제: {vision_fees}")
                
                # JavaScript와 Vision 결과 합치기
                all_fees = set(js_fees) | set(vision_fees)
                fees = sorted(list(all_fees))
                
            except Exception as e:
                print(f"  ⚠️  Vision 추출 실패, JavaScript 결과만 사용: {e}")
                fees = js_fees
            
            return fees
            
        except Exception as e:
            print(f"  ⚠️  화면 요금제 확인 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _select_plan_by_fee(self, page: Page, target_fee: int) -> bool:
        """
        월요금으로 요금제 선택 (핵심!)
        
        Args:
            target_fee: 목표 월요금 (예: 89000)
        """
        try:
            # popup 열기 및 AJAX 로딩 대기
            try:
                # JavaScript로 popup 열기
                await page.evaluate("""
                    const link = document.querySelector('a[onclick*="popup"], a[onclick*="price"]');
                    if (link) {
                        link.click();
                    }
                """)
                
                # AJAX 로딩 대기 (popup 내용이 로드될 때까지)
                await asyncio.sleep(3)  # 충분한 시간
                
                # popup 내용 확인
                popup_html = await page.evaluate("""
                    document.querySelector('.popup, .modal')?.innerHTML || ''
                """)
                
                print(f"      popup 내용: {len(popup_html)} bytes")
                
                # 요금제 개수 확인
                tr_count = await page.evaluate("""
                    document.querySelectorAll('.popup tr, .modal tr').length
                """)
                print(f"      popup 내부 tr: {tr_count}개")
                
            except Exception as e:
                print(f"      popup 열기 실패: {e}")
            
            # JavaScript로 월요금 찾아서 onclick 실행
            result = await page.evaluate(f"""
                (targetFee) => {{
                    const allRows = document.querySelectorAll('tr, li');
                    let debugInfo = {{searched: allRows.length, found: []}};
                    
                    for (const row of allRows) {{
                        const text = row.textContent;
                        
                        // 월요금 패턴 찾기
                        const feeMatches = text.match(/(\\d{{1,3}}),?(\\d{{3}})/g);
                        
                        if (feeMatches) {{
                            for (const match of feeMatches) {{
                                const fee = parseInt(match.replace(/,/g, ''));
                                
                                if (fee === targetFee) {{
                                    debugInfo.found.push({{fee: fee, text: text.substring(0, 50)}});
                                    
                                    // onclick 실행
                                    const onclick = row.getAttribute('onclick');
                                    if (onclick) {{
                                        eval(onclick);
                                        return {{success: true, method: 'onclick', debug: debugInfo}};
                                    }}
                                    
                                    // 클릭
                                    row.click();
                                    return {{success: true, method: 'click', debug: debugInfo}};
                                }}
                            }}
                        }}
                    }}
                    
                    return {{success: false, debug: debugInfo}};
                }}
            """, target_fee)
            
            # 디버깅 정보 출력
            if isinstance(result, dict):
                debug = result.get('debug', {})
                print(f"      검색: {debug.get('searched', 0)}개 요소")
                print(f"      매칭: {len(debug.get('found', []))}개")
                
                for match in debug.get('found', [])[:3]:
                    print(f"        - {match['fee']:,}원: {match['text']}")
                
                success = result.get('success', False)
                if success:
                    method = result.get('method', 'unknown')
                    print(f"      ✅ 선택 성공 ({method})")
                    await asyncio.sleep(0.5)
                    
                    # popup 닫기
                    try:
                        await page.evaluate("document.querySelector('.popup_close, .close')?.click()")
                        await asyncio.sleep(0.3)
                    except:
                        pass
                    
                    return True
                else:
                    print(f"      ❌ {target_fee:,}원 요금제 못 찾음")
                    return False
            else:
                return bool(result)
            
            if result:
                await asyncio.sleep(0.5)
                print(f"      ✅ 요금제 선택 성공: {target_fee:,}원")
                
                # popup 닫기
                try:
                    await page.locator('.popup_close, .close').first.click(timeout=500)
                    await asyncio.sleep(0.3)
                except:
                    pass
            else:
                print(f"      ❌ {target_fee:,}원 요금제 못 찾음")
            
            return result
            
        except Exception as e:
            print(f"      ❌ 요금제 선택 오류: {e}")
            return False
    
    async def _extract_pricing(self, page: Page) -> Dict[str, Any]:
        """Vision으로 가격 추출 (간소화)"""
        try:
            screenshot = await page.screenshot(
                full_page=False,
                quality=50,
                type='jpeg',
                timeout=10000  # 10초로 증가 (타임아웃 방지)
            )
            screenshot_b64 = base64.b64encode(screenshot).decode()
            img_url = f"data:image/jpeg;base64,{screenshot_b64}"
            
            prompt = """
가격:
{"retail_price": 1155000, "installment_principal": 465000, "monthly_payment": 20586, "plan_name": "프리미엄", "plan_monthly_fee": 85000}

JSON만.
"""
            
            resp = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=img_url,
                system_message="가격 추출"
            )
            
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            pricing = json.loads(resp)
            
            # 최소 검증
            if not pricing.get('retail_price') and not pricing.get('installment_principal'):
                return {}
            
            return pricing
            
        except Exception as e:
            print(f"        가격 추출 실패: {str(e)[:50]}")
            return {}
    
    def _convert_to_schema(
        self,
        collected: List[Dict[str, Any]],
        url: str,
        site_name: str
    ) -> ScrapingResult:
        """스키마 변환"""
        policies = []
        
        for data in collected:
            carrier = data["carrier"]
            join_type_str = data["join_type"]
            pricing = data["pricing"]
            
            # JoinType
            if "번호이동" in join_type_str:
                join_type = JoinType.NUMBER_TRANSFER
            else:
                join_type = JoinType.DEVICE_CHANGE
            
            # Carrier 정규화
            carrier_clean = carrier.upper().replace(" ", "").replace("+", "")
            if "LG" in carrier_clean:
                carrier_clean = "LGU"
            
            # 양수 변환
            public_subsidy = abs(pricing.get("public_subsidy")) if pricing.get("public_subsidy") else None
            additional_subsidy = abs(pricing.get("additional_subsidy")) if pricing.get("additional_subsidy") else None
            
            policy = Policy(
                policy_id=hashlib.md5(str(data).encode()).hexdigest()[:16],
                carrier=carrier_clean,
                mno_join_type=join_type,
                mobile_plan=MobilePlan(
                    name=pricing.get("plan_name", "알 수 없음"),
                    monthly_fee=pricing.get("plan_monthly_fee", 0) or 0
                ),
                discount_type=DiscountType.PUBLIC_SUBSIDY,
                pricing=PricingDetails(
                    mno_retail_price=pricing.get("retail_price"),
                    public_subsidy=public_subsidy,
                    discount=additional_subsidy,
                    sku_installment_fee=pricing.get("installment_principal"),
                    monthly_payment=pricing.get("monthly_payment")
                )
            )
            
            policies.append(policy)
        
        # Product 생성
        product = Product(
            product_id=hashlib.md5(f"{site_name}_{self.model_name}".encode()).hexdigest()[:16],
            sku_code=self.model_name,
            sku_storage=parse_storage("256GB"),  # 기본값
            policies=policies
        )
        
        return ScrapingResult(
            captured_at=datetime.datetime.now(),
            source=SourceInfo(site=site_name, url=url),
            products=[product] if policies else []
        )

