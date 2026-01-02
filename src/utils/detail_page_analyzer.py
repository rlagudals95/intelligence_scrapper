# mcp 및 vision llm 기반 상세페이지 분석기
# 대부분의 휴대폰의 상세페이지는 비슷할거라는 가설
# 용량, 색상, 사용중인 통신사, 사용하실 통신사, 가입유형, 요금제, 할인방법 등 옵션을 알아서 선택하고 그에 맞는 정책을 모두 가져오는게 최종목표

import json
import asyncio
import base64
import hashlib
import datetime
from typing import Dict, Any, List, Optional
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

logger = get_logger()


class DetailPageAnalyzer:
    """
    Vision LLM 및 Playwright 기반 범용 상세페이지 분석기
    
    단계별 분석:
    1. 페이지 로드 및 기본 정보 추출
    2. 옵션 UI 분석 (Vision + HTML)
    3. 옵션 값 추출
    4. 옵션 조합 생성
    5. 각 조합에 대해 정책 추출
    6. 결과 검증 및 반환
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        logger.info("DetailPageAnalyzer 초기화")
    
    async def analyze_detail_page(
        self, 
        page: Page, 
        url: str,
        site_name: str = "Unknown"
    ) -> ScrapingResult:
        """
        상세페이지 전체 분석 및 정책 추출
        
        Args:
            page: Playwright Page 객체
            url: 상세페이지 URL
            site_name: 사이트 이름
            
        Returns:
            ScrapingResult: 추출된 정책 데이터
        """
        print("\n" + "="*70)
        print("🔍 상세페이지 분석 시작")
        print("="*70)
        print(f"URL: {url}")
        print(f"사이트: {site_name}")
        print("="*70 + "\n")
        
        # Step 1: 페이지 로드 및 기본 정보 추출
        step1_result = await self._step1_extract_basic_info(page, url)
        print(f"\n[Step 1 완료] 기본 정보 추출")
        print(f"  제품명: {step1_result.get('product_name', 'N/A')}")
        print(f"  현재 URL: {step1_result.get('current_url', 'N/A')}")
        
        # Step 2: 옵션 UI 분석 (선택자 추출 + 옵션 값 추출)
        step2_result = await self._step2_analyze_option_ui(page)
        print(f"\n[Step 2 완료] 옵션 UI 분석")
        print(f"  선택자 구조: {list(step2_result.get('structure', {}).get('options', {}).keys())}")
        print(f"  추출된 옵션: {list(step2_result.get('options', {}).keys())}")
        
        # Step 3: 옵션 값 검증 (Step 2에서 이미 추출했으므로 그대로 사용)
        step3_result = step2_result.get("options", {})
        structure = step2_result.get("structure", {})
        print(f"\n[Step 3 완료] 옵션 값 검증")
        for opt_type, opt_values in step3_result.items():
            if isinstance(opt_values, list):
                print(f"    {opt_type}: {len(opt_values)}개 - {opt_values[:3]}")
            else:
                print(f"    {opt_type}: {opt_values}")
        
        # Step 4: 옵션 조합 생성
        step4_result = await self._step4_generate_combinations(step3_result, step2_result.get("structure", {}))
        print(f"\n[Step 4 완료] 옵션 조합 생성")
        print(f"  총 조합 수: {len(step4_result)}개")
        if step4_result:
            print(f"  샘플 조합: {step4_result[0]}")
        
        # Step 5: 각 조합에 대해 정책 추출
        step5_result = await self._step5_extract_policies(page, step4_result, step1_result)
        print(f"\n[Step 5 완료] 정책 추출")
        print(f"  성공한 조합: {len([r for r in step5_result if r.get('success')])}개")
        print(f"  실패한 조합: {len([r for r in step5_result if not r.get('success')])}개")
        
        # Step 6: 결과 검증 및 변환
        result = await self._step6_convert_to_schema(
            step5_result, 
            url, 
            site_name, 
            step1_result
        )
        print(f"\n[Step 6 완료] 결과 변환")
        print(f"  제품 수: {len(result.products)}")
        total_policies = sum(len(p.policies) for p in result.products)
        print(f"  총 정책 수: {total_policies}개")
        
        print("\n" + "="*70)
        print("✅ 상세페이지 분석 완료")
        print("="*70 + "\n")
        
        return result
    
    async def _step1_extract_basic_info(self, page: Page, url: str) -> Dict[str, Any]:
        """Step 1: 페이지 로드 및 기본 정보 추출"""
        print("\n[Step 1] 페이지 로드 및 기본 정보 추출 중...")
        
        try:
            # 페이지 제목 추출
            title = await page.title()
            
            # URL에서 제품 정보 추출 시도
            current_url = page.url
            
            # 제품명 추출 (제목 또는 URL에서)
            product_name = title.strip()
            
            return {
                "product_name": product_name,
                "current_url": current_url,
                "page_title": title
            }
        except Exception as e:
            logger.error(f"Step 1 실패: {e}")
            return {
                "product_name": "Unknown",
                "current_url": url,
                "page_title": ""
            }
    
    async def _step2_analyze_option_ui(self, page: Page) -> Dict[str, Any]:
        """Step 2: HTML 기반 옵션 UI 분석 및 선택자 추출"""
        print("\n[Step 2] HTML 구조 분석 및 선택자 추출 중...")
        
        try:
            # HTML 전체 추출
            html = await page.content()
            
            # HTML 정리 (불필요한 스크립트 제거)
            html_cleaned = await self._clean_html(html)
            
            # Step 2A: LLM에게 HTML 분석 요청 (선택자 추출)
            structure = await self._step2a_extract_selectors(html_cleaned)
            
            print("\n[Step 2A 완료] 선택자 추출")
            print(f"  용량 선택자: {structure.get('options', {}).get('storage', {}).get('selector', 'N/A')}")
            print(f"  통신사 선택자: {structure.get('options', {}).get('carrier', {}).get('selector', 'N/A')}")
            print(f"  가입유형 선택자: {structure.get('options', {}).get('join_type', {}).get('selector', 'N/A')}")
            print(f"  요금제 선택자: {structure.get('options', {}).get('plan', {}).get('item_selector', 'N/A')}")
            
            # Step 2B: 추출된 선택자로 실제 옵션 값 추출
            options = await self._step2b_extract_option_values(page, structure)
            
            print("\n[Step 2B 완료] 옵션 값 추출")
            for opt_type, opt_values in options.items():
                if isinstance(opt_values, list):
                    print(f"  {opt_type}: {len(opt_values)}개 - {opt_values[:3]}")
                else:
                    print(f"  {opt_type}: {opt_values}")
            
            return {
                "structure": structure,  # 선택자 정보
                "options": options       # 실제 옵션 값
            }
            
        except Exception as e:
            logger.error(f"Step 2 실패: {e}")
            import traceback
            traceback.print_exc()
            return {
                "structure": {},
                "options": {}
            }
    
    async def _clean_html(self, html: str) -> str:
        """HTML 정리 (스크립트, 스타일 제거)"""
        import re
        
        # 스크립트 제거
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 스타일 제거
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 주석 제거
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # 공백 정리
        html = re.sub(r'\s+', ' ', html)

        
        # 헤더, 푸터, 네비게이션 제거
        # 헤더: <header>, <nav>, <aside>, <footer>
        # 푸터: <footer>, <nav>, <aside>, <header>
        # 네비게이션: <nav>, <aside>, <header>, <footer>
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        

        # 옵션과 무관한 태그들 제거    
        html = re.sub(r'<image[^>]*>.*?</image>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<picture[^>]*>.*?</picture>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<video[^>]*>.*?</video>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<audio[^>]*>.*?</audio>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<embed[^>]*>.*?</embed>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<object[^>]*>.*?</object>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<param[^>]*>.*?</param>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # body 태그 찾기 (정규표현식 사용)
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        
        if body_match:
            print(f"Body 찾음: {len(body_match.group(1))}자")
            html = body_match.group(1)  # body 태그 내용만 추출
        else:
            print(f"Body 못찾음, 전체 HTML 사용")

        print(f"HTML 정리 완료: {len(html)}자")


        html_payload = html
        print(f"HTML 정리 완료: {html_payload}")

        return html_payload
    
    async def _step2a_extract_selectors(self, html: str) -> Dict[str, Any]:
        """Step 2A: HTML 분석하여 CSS 선택자 추출"""
        print("\n[Step 2A] HTML 분석 중 (선택자 추출)...")
        
        prompt = f"""
다음 HTML은 휴대폰 상세페이지입니다. 
이 HTML을 분석하여 각 옵션의 CSS 선택자와 클릭 방법을 제시하세요.

# HTML
{html[:50000]}  # 50KB 제한

# 찾아야 할 요소

## 1. 용량 선택 UI (storage)
- "256GB", "512GB", "1TB" 같은 텍스트가 있는 버튼/탭/라디오
- **selector**: CSS 선택자 (예: `.storage-btn`, `button[data-storage]`)
- **type**: "button" | "tab" | "radio" | "select"
- **click_method**: "click" | "select" | "open_dropdown_then_select"
- **value_attribute**: 값이 속성에 있는 경우 (예: "data-storage", "value")

## 2. 통신사 선택 UI (carrier)
- SKT, KT, LG U+ 등의 선택 UI
- **selector**: CSS 선택자
- **type**: "button" | "radio" | "select"
- **click_method**: "click" | "select"
- **value_attribute**: 값이 속성에 있는 경우 (예: "value")

## 3. 가입유형 선택 UI (join_type)
- "번호이동", "기기변경" 버튼/탭
- **selector**: CSS 선택자
- **type**: "button" | "tab" | "radio"
- **click_method**: "click" | "select"

## 4. 요금제 선택 UI (plan)
- 요금제 드롭다운/버튼
- **open_button_selector**: 드롭다운을 여는 버튼 (예: `button.bill-view`)
- **list_container_selector**: 요금제 리스트 컨테이너 (예: `.plan-list`, `.myModal-content`)
- **item_selector**: 요금제 항목 선택자 (예: `li.opt_bill_list`, `.plan_list_item`)
- **price_attribute**: 요금제 가격 속성 (예: `data-billprice`, `data-price`)
- **name_selector**: 요금제 이름이 있는 하위 요소 (선택적)

## 5. 가격 정보 영역 (pricing)
- **retail_price_selector**: 출고가가 표시된 요소
- **public_subsidy_selector**: 공시지원금이 표시된 요소
- **discount_selector**: 추가할인이 표시된 요소
- **installment_fee_selector**: 할부원금이 표시된 요소
- **monthly_payment_selector**: 월 할부금이 표시된 요소
- **plan_monthly_fee_selector**: 요금제 월요금이 표시된 요소

# 응답 형식 (JSON)

{{
  "options": {{
    "storage": {{
      "selector": ".storage-btn",
      "type": "button",
      "click_method": "click",
      "value_attribute": "data-storage"
    }},
    "carrier": {{
      "selector": "input[name='item_telecom']",
      "type": "radio",
      "click_method": "click",
      "value_attribute": "value"
    }},
    "join_type": {{
      "selector": "button.join-type-btn",
      "type": "button",
      "click_method": "click"
    }},
    "plan": {{
      "open_button_selector": "button.bill-view",
      "list_container_selector": ".myModal-content",
      "item_selector": "li.opt_bill_list",
      "price_attribute": "data-billprice",
      "name_selector": ".bill_name"
    }}
  }},
  "pricing": {{
    "retail_price_selector": ".retail-price .unit-w",
    "public_subsidy_selector": ".subsidy .unit-w",
    "discount_selector": ".discount .unit-w",
    "installment_fee_selector": ".installment .unit-w",
    "monthly_payment_selector": ".monthly-payment .unit-w",
    "plan_monthly_fee_selector": ".plan-fee .unit-w"
  }},
  "execution_plan": {{
    "order": ["storage", "carrier", "join_type", "plan"],
    "wait_times": {{
      "after_storage": 0.3,
      "after_carrier": 0.5,
      "after_join_type": 0.3,
      "after_plan": 1.0
    }},
    "price_extraction_trigger": "after_all_selected"
  }}
}}

**중요:**
- 실제 HTML에 존재하는 선택자만 반환
- 예시 값을 그대로 반환하지 마세요
- 선택자는 `document.querySelector()`로 찾을 수 있어야 함
- 없으면 null 반환
- execution_plan은 옵션 선택 순서와 대기 시간을 제시

**JSON만 출력하세요.**
"""
        
        response = await self.llm.complete(
            prompt=prompt,
            system_message="당신은 HTML 구조 분석 전문가입니다. 실제 HTML을 분석하여 정확한 CSS 선택자를 추출합니다.",
            response_format={"type": "json_object"}
        )
        
        # JSON 추출 및 정리
        response = response.strip()
        
        # ```json 블록 제거
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        response = response.strip()
        
        # JSON 파싱
        try:
            structure = json.loads(response)
            logger.info("   ✅ 선택자 추출 완료")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답 내용 (처음 500자): {response[:500]}")
            # 기본 구조 반환
            structure = {
                "options": {},
                "pricing": {},
                "execution_plan": {
                    "order": ["storage", "carrier", "join_type", "plan"],
                    "wait_times": {
                        "after_storage": 0.3,
                        "after_carrier": 0.5,
                        "after_join_type": 0.3,
                        "after_plan": 1.0
                    },
                    "price_extraction_trigger": "after_all_selected"
                }
            }
        
        return structure
    
    async def _step2b_extract_option_values(
        self, 
        page: Page, 
        structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Step 2B: 추출된 선택자로 실제 옵션 값 추출"""
        print("\n[Step 2B] 옵션 값 추출 중...")
        
        options = {}
        
        # 용량 추출
        if storage_info := structure.get("options", {}).get("storage"):
            selector = storage_info.get("selector")
            if selector:
                try:
                    values = await page.evaluate(f"""
                        () => {{
                            try {{
                                const elements = document.querySelectorAll('{selector}');
                                return Array.from(elements).map(el => {{
                                    // value 속성이 있으면 사용
                                    const valueAttr = '{storage_info.get("value_attribute", "")}';
                                    if (valueAttr && el.getAttribute(valueAttr)) {{
                                        return el.getAttribute(valueAttr);
                                    }}
                                    // 텍스트에서 추출
                                    return el.textContent.trim();
                                }}).filter(v => v);
                            }} catch (e) {{
                                return [];
                            }}
                        }}
                    """)
                    if values:
                        options["storage"] = values
                        print(f"    ✅ 용량: {values}")
                except Exception as e:
                    print(f"    ⚠️  용량 추출 실패: {e}")
        
        # 통신사 추출
        if carrier_info := structure.get("options", {}).get("carrier"):
            selector = carrier_info.get("selector")
            if selector:
                try:
                    values = await page.evaluate(f"""
                        () => {{
                            try {{
                                const elements = document.querySelectorAll('{selector}');
                                return Array.from(elements).map(el => {{
                                    const valueAttr = '{carrier_info.get("value_attribute", "value")}';
                                    if (valueAttr && el.getAttribute(valueAttr)) {{
                                        return el.getAttribute(valueAttr);
                                    }}
                                    return el.textContent.trim();
                                }}).filter(v => v);
                            }} catch (e) {{
                                return [];
                            }}
                        }}
                    """)
                    if values:
                        options["carrier"] = values
                        print(f"    ✅ 통신사: {values}")
                except Exception as e:
                    print(f"    ⚠️  통신사 추출 실패: {e}")
        
        # 가입유형 추출
        if join_type_info := structure.get("options", {}).get("join_type"):
            selector = join_type_info.get("selector")
            if selector:
                try:
                    values = await page.evaluate(f"""
                        () => {{
                            try {{
                                const elements = document.querySelectorAll('{selector}');
                                return Array.from(elements).map(el => el.textContent.trim()).filter(v => v);
                            }} catch (e) {{
                                return [];
                            }}
                        }}
                    """)
                    if values:
                        options["join_type"] = values
                        print(f"    ✅ 가입유형: {values}")
                except Exception as e:
                    print(f"    ⚠️  가입유형 추출 실패: {e}")
        
        # 요금제는 드롭다운을 열어야 하므로 별도 처리
        if plan_info := structure.get("options", {}).get("plan"):
            try:
                # 드롭다운 열기
                open_btn = plan_info.get("open_button_selector")
                if open_btn:
                    await page.evaluate(f"""
                        () => {{
                            const btn = document.querySelector('{open_btn}');
                            if (btn) {{
                                btn.click();
                            }}
                        }}
                    """)
                    await asyncio.sleep(1)
                    print(f"    ✅ 요금제 드롭다운 열기 시도")
                
                # 요금제 목록 추출
                item_selector = plan_info.get("item_selector")
                price_attr = plan_info.get("price_attribute", "data-billprice")
                name_selector = plan_info.get("name_selector", "")
                
                if item_selector:
                    plans = await page.evaluate(f"""
                        () => {{
                            try {{
                                const items = document.querySelectorAll('{item_selector}');
                                return Array.from(items).map(item => {{
                                    const nameElem = '{name_selector}' ? item.querySelector('{name_selector}') : item;
                                    const name = nameElem ? nameElem.textContent.trim() : item.textContent.trim();
                                    const price = item.getAttribute('{price_attr}') || '';
                                    
                                    // 텍스트에서 가격 추출 시도
                                    let priceFromText = '';
                                    if (!price) {{
                                        const text = item.textContent || '';
                                        const match = text.match(/(\\d{{1,3}}),?(\\d{{3}}),?(\\d{{3}})?/);
                                        if (match) {{
                                            priceFromText = match[0].replace(/,/g, '');
                                        }}
                                    }}
                                    
                                    return {{
                                        name: name,
                                        price: price || priceFromText,
                                        element: item.outerHTML.substring(0, 200)
                                    }};
                                }}).filter(p => p.name);
                            }} catch (e) {{
                                return [];
                            }}
                        }}
                    """)
                    if plans:
                        options["plan"] = plans
                        print(f"    ✅ 요금제: {len(plans)}개 발견")
                        for plan in plans[:3]:
                            print(f"      - {plan.get('name')} ({plan.get('price')}원)")
            except Exception as e:
                print(f"    ⚠️  요금제 추출 실패: {e}")
        
        return options
    
    async def _step3_extract_option_values(
        self, 
        page: Page, 
        step2_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Step 3: 옵션 값 검증 (Step 2에서 이미 추출됨)"""
        print("\n[Step 3] 옵션 값 검증 중...")
        
        # Step 2에서 이미 추출했으므로 그대로 사용
        return step2_result.get("options", {})
    
    async def _step4_generate_combinations(
        self, 
        options: Dict[str, Any],
        structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Step 4: 옵션 조합 생성"""
        print("\n[Step 4] 옵션 조합 생성 중...")
        
        combinations = []
        
        # 기본값 설정
        storages = options.get("storage", ["256GB"])
        carriers = options.get("carrier", ["SKT", "KT", "LGU"])
        join_types = options.get("join_type", ["번호이동", "기기변경"])
        plans = options.get("plan", [])  # 요금제는 리스트 (dict 형태)
        
        # storages가 문자열인 경우 리스트로 변환
        if isinstance(storages, str):
            storages = [storages]
        if isinstance(carriers, str):
            carriers = [carriers]
        if isinstance(join_types, str):
            join_types = [join_types]
        
        # 용량 × 통신사 × 가입유형 × 요금제 조합
        for storage in storages:
            for carrier in carriers:
                for join_type in join_types:
                    # 요금제가 있으면 각 요금제별로 조합 생성
                    if plans and len(plans) > 0:
                        for plan in plans:
                            combinations.append({
                                "storage": storage,
                                "carrier": carrier,
                                "join_type": join_type,
                                "plan": plan.get("name") if isinstance(plan, dict) else plan,
                                "plan_price": plan.get("price") if isinstance(plan, dict) else None
                            })
                    else:
                        # 요금제가 없으면 일단 None으로
                        combinations.append({
                            "storage": storage,
                            "carrier": carrier,
                            "join_type": join_type,
                            "plan": None,
                            "plan_price": None
                        })
        
        return combinations
    
    async def _step5_extract_policies(
        self,
        page: Page,
        combinations: List[Dict[str, Any]],
        basic_info: Dict[str, Any],
        structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Step 5: 각 조합에 대해 정책 추출"""
        print("\n[Step 5] 정책 추출 중...")
        print(f"  총 {len(combinations)}개 조합 처리 예정")
        
        results = []
        
        for idx, combo in enumerate(combinations, 1):
            print(f"\n  [{idx}/{len(combinations)}] 조합 처리: {combo}")
            
            try:
                # 옵션 선택 (선택자 기반)
                await self._select_options(page, combo, structure)
                
                # 가격 정보 추출 (선택자 기반)
                pricing = await self._extract_pricing_with_selectors(page, structure)
                
                results.append({
                    "success": True,
                    "combo": combo,
                    "pricing": pricing
                })
                print(f"    ✅ 정책 추출 성공")
                
            except Exception as e:
                logger.error(f"    ❌ 조합 처리 실패: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    "success": False,
                    "combo": combo,
                    "error": str(e)
                })
        
        return results
    
    async def _select_options(self, page: Page, combo: Dict[str, str]):
        """옵션 선택 (텍스트 기반)"""
        # 용량 선택
        if combo.get("storage"):
            await self._click_by_text(page, combo["storage"])
            await asyncio.sleep(0.3)
        
        # 통신사 선택
        if combo.get("carrier"):
            carrier_texts = [combo["carrier"]]
            if combo["carrier"] == "LGU":
                carrier_texts = ["LGU", "LG U+", "U+", "LG"]
            
            for carrier_text in carrier_texts:
                if await self._click_by_text(page, carrier_text):
                    break
            await asyncio.sleep(0.3)
        
        # 가입유형 선택
        if combo.get("join_type"):
            await self._click_by_text(page, combo["join_type"])
            await asyncio.sleep(0.3)
    
    async def _click_by_text(self, page: Page, text: str) -> bool:
        """텍스트로 요소 찾아서 클릭"""
        try:
            await page.get_by_text(text, exact=False).first.click(force=True, timeout=1000)
            return True
        except:
            # JavaScript로 시도
            try:
                result = await page.evaluate(f"""
                    () => {{
                        const all = document.querySelectorAll('button, a, div, span, label, input[type="radio"]');
                        for (const elem of all) {{
                            if (elem.textContent && elem.textContent.includes("{text}")) {{
                                elem.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """)
                return result
            except:
                return False
    
    async def _extract_pricing_with_selectors(
        self, 
        page: Page, 
        structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """가격 정보 추출 (선택자 기반)"""
        try:
            pricing_selectors = structure.get("pricing", {})
            pricing = {}
            
            # 각 가격 정보 추출
            for price_type, selector in pricing_selectors.items():
                if not selector:
                    continue
                
                try:
                    value = await page.evaluate(f"""
                        () => {{
                            try {{
                                const elem = document.querySelector('{selector}');
                                if (!elem) return null;
                                
                                const text = elem.textContent || '';
                                // 숫자만 추출 (콤마 제거)
                                const match = text.match(/[\\d,]+/);
                                if (match) {{
                                    return parseInt(match[0].replace(/,/g, ''));
                                }}
                                return null;
                            }} catch (e) {{
                                return null;
                            }}
                        }}
                    """)
                    
                    # 필드명 매핑
                    if price_type == "retail_price_selector":
                        pricing["mno_retail_price"] = value
                    elif price_type == "public_subsidy_selector":
                        pricing["public_subsidy"] = value
                    elif price_type == "discount_selector":
                        pricing["discount"] = value
                    elif price_type == "installment_fee_selector":
                        pricing["sku_installment_fee"] = value
                    elif price_type == "monthly_payment_selector":
                        pricing["monthly_payment"] = value
                    elif price_type == "plan_monthly_fee_selector":
                        pricing["plan_monthly_fee"] = value
                        
                except Exception as e:
                    logger.debug(f"가격 추출 실패 ({price_type}): {e}")
            
            # 선택자로 추출 실패 시 Vision 폴백
            if not any(pricing.values()):
                print("      ⚠️  선택자 기반 추출 실패, Vision 폴백 시도")
                return await self._extract_pricing_with_vision(page)
            
            return pricing
            
        except Exception as e:
            logger.error(f"가격 추출 실패: {e}")
            return await self._extract_pricing_with_vision(page)
    
    async def _extract_pricing_with_vision(self, page: Page) -> Dict[str, Any]:
        """가격 정보 추출 (Vision 폴백)"""
        try:
            screenshot = await page.screenshot(full_page=False, quality=80, type='jpeg', timeout=8000)
            screenshot_b64 = base64.b64encode(screenshot).decode()
            image_url = f"data:image/jpeg;base64,{screenshot_b64}"
            
            prompt = """
화면에서 가격 정보를 추출하세요.

다음 정보를 찾으세요:
- 출고가 (정가, 원가)
- 공시지원금
- 추가할인
- 최종가격 (할인 후 가격)
- 월 할부금
- 요금제 월요금

JSON 형식:
{
  "mno_retail_price": 1500000,
  "public_subsidy": 500000,
  "discount": 100000,
  "final_price": 900000,
  "sku_installment_fee": 37500,
  "plan_monthly_fee": 89000
}

숫자는 콤마 없이 정수로 반환하세요.
없는 정보는 null로 반환하세요.
JSON만 출력하세요.
"""
            
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=image_url,
                system_message="당신은 가격 정보 추출 전문가입니다."
            )
            
            # JSON 추출
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            response = response.strip()
            
            pricing = json.loads(response)
            return pricing
            
        except Exception as e:
            logger.error(f"Vision 가격 추출 실패: {e}")
            return {}
    
    async def _step6_convert_to_schema(
        self,
        results: List[Dict[str, Any]],
        url: str,
        site_name: str,
        basic_info: Dict[str, Any]
    ) -> ScrapingResult:
        """Step 6: 결과를 ScrapingResult 스키마로 변환"""
        print("\n[Step 6] 결과 변환 중...")
        
        # 성공한 결과만 필터링
        successful_results = [r for r in results if r.get("success")]
        
        if not successful_results:
            return ScrapingResult(
                source=SourceInfo(site=site_name, url=url),
                products=[]
            )
        
        # 제품별로 그룹화
        products_map = {}
        
        for result in successful_results:
            combo = result["combo"]
            pricing = result["pricing"]
            
            # 제품 키 생성 (용량)
            storage = combo.get("storage", "256GB")
            product_key = storage
            
            if product_key not in products_map:
                products_map[product_key] = {
                    "sku_code": basic_info.get("product_name", "Unknown"),
                    "sku_storage": parse_storage(storage),
                    "policies": []
                }
            
            # Policy 생성
            join_type_str = combo.get("join_type", "기기변경")
            if "번호이동" in join_type_str:
                join_type = JoinType.NUMBER_TRANSFER
            else:
                join_type = JoinType.DEVICE_CHANGE
            
            carrier_str = combo.get("carrier", "SKT")
            carrier_upper = carrier_str.upper().replace(" ", "").replace("+", "")
            if "LG" in carrier_upper:
                carrier = "LGU"
            elif "SKT" in carrier_upper:
                carrier = "SKT"
            elif "KT" in carrier_upper:
                carrier = "KT"
            else:
                carrier = carrier_upper
            
            # Policy ID 생성
            policy_id = hashlib.md5(
                f"{carrier}_{join_type.value}_{combo.get('storage')}_{combo.get('plan')}".encode()
            ).hexdigest()[:16]
            
            policy = Policy(
                policy_id=policy_id,
                carrier=carrier,
                mno_join_type=join_type,
                mobile_plan=MobilePlan(
                    name=combo.get("plan") or "Unknown",
                    monthly_fee=pricing.get("plan_monthly_fee") or 0
                ),
                discount_type=DiscountType.PUBLIC_SUBSIDY,  # 기본값: 공시지원금
                pricing=PricingDetails(
                    mno_retail_price=pricing.get("mno_retail_price"),
                    public_subsidy=pricing.get("public_subsidy"),
                    discount=pricing.get("discount"),
                    sku_installment_fee=pricing.get("sku_installment_fee"),
                    monthly_payment=pricing.get("final_price")
                )
            )
            
            products_map[product_key]["policies"].append(policy)
        
        # Product 리스트 생성
        products = []
        for product_data in products_map.values():
            # Product ID 생성
            product_id = hashlib.md5(
                f"{product_data['sku_code']}_{product_data['sku_storage'].value if product_data['sku_storage'] else ''}".encode()
            ).hexdigest()[:16]
            
            products.append(Product(
                product_id=product_id,
                sku_code=product_data["sku_code"],
                sku_storage=product_data["sku_storage"],
                policies=product_data["policies"]
            ))
        
        return ScrapingResult(
            source=SourceInfo(
                site=site_name,
                url=url,
                captured_at=datetime.datetime.now().isoformat()
            ),
            products=products
        )
