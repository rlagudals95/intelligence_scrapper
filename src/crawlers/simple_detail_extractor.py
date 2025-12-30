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
        
        all_target_fees = sorted(all_target_fees, reverse=True)  # 높은 요금부터
        
        print(f"\n모든 요금제: {all_target_fees}")
        
        # Step 2: 각 요금제별로 (핵심 순서!)
        for target_fee in all_target_fees:
            print(f"\n{'='*70}")
            print(f"💰 요금제: {target_fee:,}원")
            print(f"{'='*70}")
            
            # 요금제 선택 (Vision Agent)
            plan_selected = await self.vision_agent.select_plan_by_fee(page, target_fee)
            
            if not plan_selected:
                print(f"  ❌ {target_fee:,}원 요금제 선택 실패, skip")
                continue
            
            print(f"  ✅ {target_fee:,}원 요금제 선택 완료")
            await asyncio.sleep(1)
            
            # Step 3: 이 요금제로 모든 통신사 × 가입유형 조합 수집
            for carrier in ["SKT", "KT", "LGU"]:
                if carrier not in filters:
                    print(f"  ⏭️  {carrier}: 필터 없음")
                    continue
                
                for join_type in ["번호이동", "기기변경"]:
                    if join_type not in filters[carrier]:
                        print(f"  ⏭️  {carrier} / {join_type}: 필터 없음")
                        continue
                    
                    # 이 조합에 이 요금제가 필요한지 확인
                    if target_fee not in filters[carrier][join_type]:
                        print(f"  ⏭️  {carrier} / {join_type}: {target_fee:,}원 불필요")
                        continue
                    
                    print(f"  [{carrier} / {join_type}] 시도")
                    
                    # 통신사 선택
                    await self._click_by_text(page, carrier)
                    await asyncio.sleep(0.5)
                    
                    # 가입유형 선택
                    await self._click_by_text(page, join_type)
                    await asyncio.sleep(0.5)
                    
                    # 가격 추출
                    pricing = await self._extract_pricing(page)
                    
                    if pricing and (pricing.get('retail_price') or pricing.get('installment_principal')):
                        collected.append({
                            "carrier": carrier,
                            "join_type": join_type,
                            "target_fee": target_fee,
                            "pricing": pricing
                        })
                        print(f"    ✅ 정책 수집")
                    else:
                        print(f"    ⚠️  가격 데이터 없음")
        
        # Step 3: 스키마 변환
        print(f"\n📊 총 {len(collected)}개 정책 수집")
        result = self._convert_to_schema(collected, url, site_name)
        
        return result
    
    async def _click_by_text(self, page: Page, text: str) -> bool:
        """텍스트로 요소 찾아서 클릭"""
        try:
            await page.get_by_text(text, exact=False).first.click(force=True, timeout=1000)
            return True
        except:
            return False
    
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
        """Vision으로 가격 추출"""
        try:
            screenshot = await page.screenshot(full_page=False, quality=50, type='jpeg', timeout=8000)
            screenshot_b64 = base64.b64encode(screenshot).decode()
            img_url = f"data:image/jpeg;base64,{screenshot_b64}"
            
            prompt = """
화면의 가격 정보를 추출하세요:

{
  "retail_price": 1155000,
  "public_subsidy": 500000,
  "additional_subsidy": 190000,
  "installment_principal": 465000,
  "monthly_payment": 20586,
  "final_price": 129586,
  "plan_name": "프리미엄",
  "plan_monthly_fee": 109000
}

**JSON만 출력하세요.**
"""
            
            resp = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=img_url,
                system_message="가격 정보를 정확히 추출하세요."
            )
            
            resp = resp.strip()
            if "```" in resp:
                resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
            resp = resp.strip()
            
            return json.loads(resp)
            
        except Exception as e:
            logger.error(f"가격 추출 실패: {e}")
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

