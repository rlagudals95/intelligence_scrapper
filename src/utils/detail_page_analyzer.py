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
            # HTML 전체 추출 (LLM이 모달 구조를 분석할 수 있도록)
            # 모달이 닫혀있어도 HTML에는 모달 구조가 포함되어 있음
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
            print(f"\n❌ [Step 2 실패] {type(e).__name__}: {e}")
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

        # 100KB 제한 (LLM 토큰 제한 고려)
        html_payload = html[:100000]
        print(f"HTML 페이로드 크기: {len(html_payload)}자 (제한: 100KB)")

        return html_payload
    
    async def _step2a_extract_selectors(self, html: str) -> Dict[str, Any]:
        """Step 2A: HTML 분석하여 CSS 선택자 추출"""
        print("\n[Step 2A] HTML 분석 중 (선택자 추출)...")
        print(f"  HTML 크기: {len(html):,}자")
        print(f"  HTML 샘플 (처음 500자): {html[:500]}")
        
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

## 2. 통신사 선택 UI (carrier) - **반드시 "carrier" 키 사용**
- SKT, KT, LG U+ 등의 선택 UI
- HTML에서 `name="item_telecom"`, `name="my_telecom"` 같은 속성 찾기
- **selector**: CSS 선택자 (예: `input[name='item_telecom']`)
- **type**: "button" | "radio" | "select"
- **click_method**: "click" | "select"
- **value_attribute**: 값이 속성에 있는 경우 (예: "value")
- **중요**: 키 이름은 반드시 "carrier"로 사용하세요. "my_telecom", "item_telecom" 같은 이름을 사용하지 마세요.

## 3. 가입유형 선택 UI (join_type) - **반드시 "join_type" 키 사용**
- "번호이동", "기기변경" 버튼/탭
- HTML에서 `name="item_ordtype"`, `name="ordtype"` 같은 속성 찾기
- **selector**: CSS 선택자 (예: `input[name='item_ordtype']`)
- **type**: "button" | "tab" | "radio"
- **click_method**: "click" | "select"
- **중요**: 키 이름은 반드시 "join_type"으로 사용하세요. "item_ordtype", "ordtype" 같은 이름을 사용하지 마세요.

## 4. 요금제 선택 UI (plan) - **매우 중요**
- 요금제는 보통 모달/팝업/드롭다운으로 표시됨
- **open_button_selector**: 요금제 모달/드롭다운을 여는 버튼 찾기
  - HTML에서 "요금제", "요금제 선택", "▼", "더보기" 같은 텍스트가 있는 버튼 찾기
  - 모달이 닫혀있어도 HTML 구조를 보고 버튼을 찾을 수 있어야 함
- **list_container_selector**: 요금제 리스트가 있는 컨테이너 (매우 중요!)
  - **반드시 "open_button_selector"를 클릭했을 때 나타나는 모달/드롭다운 내부의 리스트 컨테이너여야 함**
  - HTML에서 모달/팝업 구조를 찾을 때, 버튼 클릭 후 나타날 요소를 추론해야 함
  - 예: 버튼 클릭 후 나타나는 `<div class="myModal-content">` 내부의 `<ul>` 또는 `<div class="modal-bill-list">`
  - **주의**: 버튼 클릭 전에 보이는 요소(예: `.bill-box`)가 아니라, 클릭 후 나타나는 요소여야 함
- **item_selector**: 각 요금제 항목의 선택자 (가장 중요!)
  - "list_container_selector" 내부의 각 요금제 항목 선택자
  - **반드시 모든 요금제 항목을 선택할 수 있는 선택자여야 함**
  - 예: `li.opt_bill_list`, `.opt_bill_list`, `li[data-billcode]`
- **price_attribute**: 요금제 가격이 저장된 속성
- **name_selector**: 요금제 이름이 있는 하위 요소

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
            response_format={"type": "json_object"},
            max_tokens=4000  # 충분한 토큰 할당
        )
        
        print(f"\n[LLM 원본 응답]")
        print(f"  응답 길이: {len(response)}자")
        print(f"  응답 샘플 (처음 1000자): {response[:1000]}")
        print(f"  응답 샘플 (마지막 500자): {response[-500:]}")
        
        # JSON 추출 및 정리
        response_original = response
        response = response.strip()
        
        # ```json 블록 제거
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        response = response.strip()
        
        # 불완전한 JSON 복구 시도
        response = self._repair_incomplete_json(response)
        
        # JSON 파싱
        try:
            structure = json.loads(response)
            print(f"\n[JSON 파싱 성공]")
            print(f"  options 키 개수: {len(structure.get('options', {}))}")
            print(f"  pricing 키 개수: {len(structure.get('pricing', {}))}")
            logger.info("   ✅ 선택자 추출 완료")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답 내용 (처음 1000자): {response[:1000]}")
            logger.error(f"응답 내용 (마지막 500자): {response[-500:]}")
            print(f"\n[JSON 파싱 실패]")
            print(f"  에러: {e}")
            print(f"  응답 (처음 1000자): {response[:1000]}")
            print(f"  응답 (마지막 500자): {response[-500:]}")
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
    
    def _repair_incomplete_json(self, json_str: str) -> str:
        """불완전한 JSON 복구 시도"""
        import re
        
        # 불완전한 문자열 값 복구
        # "key": "value 형태로 끝나는 경우
        json_str = re.sub(r':\s*"([^"]*?)$', r': "\1"', json_str, flags=re.MULTILINE)
        
        # 불완전한 객체 복구
        # 마지막에 열린 중괄호/대괄호 닫기
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # 불완전한 문자열 값 찾아서 닫기
        # "key": "value 형태를 "key": "value"로
        json_str = re.sub(r'("click_method":\s*")([^"]*?)(\s*)$', r'\1\2"', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'("selector":\s*")([^"]*?)(\s*)$', r'\1\2"', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'("type":\s*")([^"]*?)(\s*)$', r'\1\2"', json_str, flags=re.MULTILINE)
        
        # 중괄호 닫기
        for _ in range(open_braces - close_braces):
            json_str += "}"
        
        # 대괄호 닫기
        for _ in range(open_brackets - close_brackets):
            json_str += "]"
        
        # 마지막 쉼표 제거
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        return json_str
    
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
                    # 선택자를 인자로 전달하여 작은따옴표 충돌 방지
                    value_attr = storage_info.get("value_attribute", "")
                    print(f"    [용량 추출 시도] 선택자: {selector}, value_attr: {value_attr}")
                    
                    result = await page.evaluate("""
                        ([selector, valueAttr]) => {
                            try {
                                const elements = document.querySelectorAll(selector);
                                console.log(`[용량] 선택자로 찾은 요소 개수: ${elements.length}`);
                                const values = Array.from(elements).map(el => {
                                    // value 속성이 있으면 사용
                                    if (valueAttr && el.getAttribute(valueAttr)) {
                                        return el.getAttribute(valueAttr);
                                    }
                                    // 텍스트에서 추출
                                    return el.textContent.trim();
                                }).filter(v => v);
                                console.log(`[용량] 추출된 값:`, values);
                                return { count: elements.length, values: values };
                            } catch (e) {
                                console.error(`[용량] 에러:`, e);
                                return { count: 0, values: [], error: e.message };
                            }
                        }
                    """, [selector, value_attr])
                    
                    print(f"    [용량 추출 결과] 요소 개수: {result.get('count', 0)}, 값: {result.get('values', [])}")
                    if result.get('error'):
                        print(f"    [용량 에러] {result.get('error')}")
                    
                    values = result.get('values', [])
                    if values:
                        options["storage"] = values
                        print(f"    ✅ 용량: {values}")
                    else:
                        print(f"    ⚠️  용량 추출 실패: 요소를 찾지 못했거나 값이 없음")
                except Exception as e:
                    print(f"    ⚠️  용량 추출 실패: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 통신사 추출 (carrier 또는 my_telecom, item_telecom 등)
        carrier_info = structure.get("options", {}).get("carrier") or \
                      structure.get("options", {}).get("my_telecom") or \
                      structure.get("options", {}).get("item_telecom")
        
        if carrier_info:
            selector = carrier_info.get("selector")
            if selector:
                try:
                    value_attr = carrier_info.get("value_attribute", "value")
                    print(f"    [통신사 추출 시도] 선택자: {selector}, value_attr: {value_attr}")
                    
                    result = await page.evaluate("""
                        ([selector, valueAttr]) => {
                            try {
                                const elements = document.querySelectorAll(selector);
                                console.log(`[통신사] 선택자로 찾은 요소 개수: ${elements.length}`);
                                const values = Array.from(elements).map(el => {
                                    if (valueAttr && el.getAttribute(valueAttr)) {
                                        return el.getAttribute(valueAttr);
                                    }
                                    return el.textContent.trim();
                                }).filter(v => v);
                                console.log(`[통신사] 추출된 값:`, values);
                                return { count: elements.length, values: values };
                            } catch (e) {
                                console.error(`[통신사] 에러:`, e);
                                return { count: 0, values: [], error: e.message };
                            }
                        }
                    """, [selector, value_attr])
                    
                    print(f"    [통신사 추출 결과] 요소 개수: {result.get('count', 0)}, 값: {result.get('values', [])}")
                    if result.get('error'):
                        print(f"    [통신사 에러] {result.get('error')}")
                    
                    values = result.get('values', [])
                    if values:
                        options["carrier"] = values
                        print(f"    ✅ 통신사: {values}")
                    else:
                        print(f"    ⚠️  통신사 추출 실패: 요소를 찾지 못했거나 값이 없음")
                except Exception as e:
                    print(f"    ⚠️  통신사 추출 실패: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 가입유형 추출 (join_type 또는 item_ordtype 등)
        join_type_info = structure.get("options", {}).get("join_type") or \
                        structure.get("options", {}).get("item_ordtype") or \
                        structure.get("options", {}).get("ordtype")
        
        if join_type_info:
            selector = join_type_info.get("selector")
            if selector:
                try:
                    print(f"    [가입유형 추출 시도] 선택자: {selector}")
                    
                    result = await page.evaluate("""
                        (selector) => {
                            try {
                                const elements = document.querySelectorAll(selector);
                                console.log(`[가입유형] 선택자로 찾은 요소 개수: ${elements.length}`);
                                const values = Array.from(elements).map(el => {
                                    // 라디오 버튼의 경우 value 속성 우선, 없으면 텍스트
                                    if (el.getAttribute('value')) {
                                        return el.getAttribute('value');
                                    }
                                    return el.textContent.trim();
                                }).filter(v => v);
                                console.log(`[가입유형] 추출된 값:`, values);
                                return { count: elements.length, values: values };
                            } catch (e) {
                                console.error(`[가입유형] 에러:`, e);
                                return { count: 0, values: [], error: e.message };
                            }
                        }
                    """, selector)
                    
                    print(f"    [가입유형 추출 결과] 요소 개수: {result.get('count', 0)}, 값: {result.get('values', [])}")
                    if result.get('error'):
                        print(f"    [가입유형 에러] {result.get('error')}")
                    
                    values = result.get('values', [])
                    if values:
                        options["join_type"] = values
                        print(f"    ✅ 가입유형: {values}")
                    else:
                        print(f"    ⚠️  가입유형 추출 실패: 요소를 찾지 못했거나 값이 없음")
                except Exception as e:
                    print(f"    ⚠️  가입유형 추출 실패: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 요금제는 드롭다운을 열어야 하므로 별도 처리
        if plan_info := structure.get("options", {}).get("plan"):
            try:
                print(f"    [요금제 추출 시작]")
                
                # 선택자 먼저 가져오기
                item_selector = plan_info.get("item_selector")
                name_selector = plan_info.get("name_selector", "")
                price_attr = plan_info.get("price_attribute")
                
                # 드롭다운/다이얼로그 열기
                open_btn = plan_info.get("open_button_selector")
                list_container = plan_info.get("list_container_selector", "")
                
                # open_button_selector를 클릭하고 나타나는 요소를 확인하여 list_container_selector 검증/보정
                if open_btn:
                    try:
                        btn_element = await page.query_selector(open_btn)
                        if btn_element:
                            # 클릭 전 상태 저장
                            before_html = await page.content()
                            
                            # 버튼 클릭
                            await btn_element.click()
                            await asyncio.sleep(1.0)  # 모달/드롭다운 열림 대기
                            
                            # 클릭 후 나타나는 모달/드롭다운 찾기
                            detected_container = await page.evaluate("""
                                () => {
                                    // 새로 나타난 모달/팝업 찾기
                                    const modals = document.querySelectorAll('.modal, .popup, [class*="Modal"], [class*="modal"], [class*="layer"], [class*="Layer"]');
                                    for (const modal of modals) {
                                        // display: none이 아니고, visible한 요소
                                        const style = window.getComputedStyle(modal);
                                        if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                                            // 내부에 리스트가 있는지 확인
                                            const list = modal.querySelector('ul, ol, [class*="list"], [class*="List"]');
                                            if (list) {
                                                return modal.className || modal.id || modal.tagName;
                                            }
                                        }
                                    }
                                    
                                    // 모달 내부의 리스트 컨테이너 직접 찾기
                                    const listContainers = document.querySelectorAll('[class*="list"], [class*="List"], ul, ol');
                                    for (const container of listContainers) {
                                        const style = window.getComputedStyle(container);
                                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                                            // 부모가 모달/팝업인지 확인
                                            let parent = container.parentElement;
                                            while (parent) {
                                                const parentClass = parent.className || '';
                                                if (parentClass.includes('modal') || parentClass.includes('Modal') || 
                                                    parentClass.includes('popup') || parentClass.includes('Popup') ||
                                                    parentClass.includes('layer') || parentClass.includes('Layer')) {
                                                    return container.className || container.id || container.tagName;
                                                }
                                                parent = parent.parentElement;
                                            }
                                        }
                                    }
                                    
                                    return null;
                                }
                            """)
                            
                            if detected_container:
                                # 실제로 나타난 컨테이너의 선택자 추출
                                actual_container_selector = await page.evaluate("""
                                    (containerClassOrId) => {
                                        // 클래스명으로 찾기
                                        if (containerClassOrId.includes(' ')) {
                                            const parts = containerClassOrId.split(' ').filter(p => p);
                                            if (parts.length > 0) {
                                                return '.' + parts[0];
                                            }
                                        }
                                        // ID로 찾기
                                        const elem = document.getElementById(containerClassOrId);
                                        if (elem) {
                                            return '#' + containerClassOrId;
                                        }
                                        // 클래스명으로 찾기
                                        const elemByClass = document.querySelector('.' + containerClassOrId);
                                        if (elemByClass) {
                                            return '.' + containerClassOrId;
                                        }
                                        return null;
                                    }
                                """, detected_container)
                                
                                if actual_container_selector:
                                    print(f"    ✅ 실제 나타난 컨테이너 감지: {actual_container_selector}")
                                    # LLM이 추출한 선택자와 다르면 업데이트
                                    if list_container != actual_container_selector:
                                        print(f"    🔄 list_container_selector 업데이트: {list_container} → {actual_container_selector}")
                                        list_container = actual_container_selector
                                        plan_info["list_container_selector"] = actual_container_selector
                                        
                    except Exception as e:
                        print(f"    ⚠️  컨테이너 자동 감지 실패: {e}, LLM 추론 선택자 사용")
                
                if open_btn:
                    # Playwright로 버튼 클릭 (더 확실함)
                    try:
                        btn_element = await page.query_selector(open_btn)
                        if btn_element:
                            # 드롭다운 열기 전 항목 개수 확인
                            selector_for_check = item_selector if item_selector else ".bill-basic"
                            before_count = await page.evaluate("""
                                (selector) => {
                                    const items = document.querySelectorAll(selector);
                                    return items.length;
                                }
                            """, selector_for_check)
                            
                            await btn_element.click()
                            
                            # 드롭다운이 열릴 때까지 대기 (최대 3초)
                            max_wait = 3.0
                            wait_interval = 0.2
                            waited = 0.0
                            after_count = before_count
                            
                            while waited < max_wait:
                                await asyncio.sleep(wait_interval)
                                waited += wait_interval
                                
                                after_count = await page.evaluate("""
                                    (selector) => {
                                        const items = document.querySelectorAll(selector);
                                        return items.length;
                                    }
                                """, selector_for_check)
                                
                                # 항목이 증가하면 성공
                                if after_count > before_count:
                                    break
                            
                            await asyncio.sleep(0.5)  # 추가 안정화 대기
                            
                            print(f"    ✅ 요금제 드롭다운 열기 버튼 클릭 (항목: {before_count} → {after_count}개, 대기: {waited:.1f}초)")
                        else:
                            print(f"    ⚠️  요금제 드롭다운 버튼을 찾지 못함")
                    except Exception as e:
                        print(f"    ⚠️  드롭다운 열기 실패: {e}, 계속 진행...")
                
                # 컨테이너가 있으면 스크롤하여 모든 항목 로드
                scroll_container = list_container
                
                if scroll_container:
                    try:
                        # 선택자로 컨테이너 찾기
                        if isinstance(scroll_container, str):
                            container = await page.query_selector(scroll_container)
                        else:
                            container = scroll_container
                        
                        if container:
                            # 스크롤하여 모든 항목 로드
                            scroll_result = await container.evaluate("""
                                (container) => {
                                    let lastHeight = 0;
                                    let currentHeight = container.scrollHeight;
                                    let scrollAttempts = 0;
                                    
                                    // 최대 15번 스크롤 시도
                                    while (scrollAttempts < 15 && currentHeight > lastHeight) {
                                        container.scrollTop = container.scrollHeight;
                                        
                                        // 대기
                                        const start = Date.now();
                                        while (Date.now() - start < 300) {}
                                        
                                        lastHeight = currentHeight;
                                        currentHeight = container.scrollHeight;
                                        scrollAttempts++;
                                    }
                                    
                                    // 맨 위로 스크롤
                                    container.scrollTop = 0;
                                    
                                    return {
                                        scrollAttempts: scrollAttempts
                                    };
                                }
                            """)
                            
                            await asyncio.sleep(0.5)
                            print(f"    ✅ 요금제 리스트 스크롤 완료 (시도: {scroll_result.get('scrollAttempts', 0)}회)")
                        else:
                            print(f"    ⚠️  스크롤 컨테이너를 찾지 못함")
                    except Exception as e:
                        print(f"    ⚠️  스크롤 실패: {e}, 계속 진행...")
                else:
                    print(f"    ⚠️  스크롤할 컨테이너가 없음")
                
                # 요금제 목록 추출 (개선된 가격 추출)
                # 추가 대기 (동적 로딩 완료 대기)
                await asyncio.sleep(0.5)
                
                if item_selector:
                    plans = await page.evaluate("""
                        ([itemSelector, nameSelector, priceAttr, listContainer]) => {
                            try {
                                // LLM이 추출한 컨테이너 선택자 사용
                                let searchRoot = document;
                                
                                if (listContainer) {
                                    const container = document.querySelector(listContainer);
                                    if (container) {
                                        searchRoot = container;
                                        console.log(`[요금제] 컨테이너 사용: ${listContainer}`);
                                    } else {
                                        console.log(`[요금제] 컨테이너를 찾지 못함: ${listContainer}`);
                                    }
                                }
                                
                                // LLM이 추출한 선택자로 항목 찾기
                                const items = searchRoot.querySelectorAll(itemSelector);
                                console.log(`[요금제] 선택자 "${itemSelector}"로 찾은 항목: ${items.length}개`);
                                
                                // 각 항목의 정보 출력 (디버깅)
                                Array.from(items).forEach((item, idx) => {
                                    const name = nameSelector ? (item.querySelector(nameSelector)?.textContent || '') : item.textContent;
                                    const price = priceAttr ? item.getAttribute(priceAttr) : '';
                                    console.log(`  [${idx + 1}] ${name?.trim()} (${price}원)`);
                                });
                                
                                const plans = Array.from(items).map(item => {
                                    // 이름 추출
                                    let name = '';
                                    if (nameSelector) {
                                        const nameElem = item.querySelector(nameSelector);
                                        if (nameElem) {
                                            name = nameElem.textContent.trim();
                                        }
                                    }
                                    if (!name) {
                                        name = item.textContent.trim();
                                    }
                                    
                                    // 가격 추출 (여러 방법 시도)
                                    let price = '';
                                    
                                    // LLM이 추출한 가격 속성으로 가격 추출
                                    if (priceAttr) {
                                        price = item.getAttribute(priceAttr) || '';
                                    }
                                    
                                    // 가격 속성이 없으면 텍스트에서 가격 패턴 찾기
                                    if (!price) {
                                        const text = item.textContent || '';
                                        const patterns = [
                                            /(\d{1,3}(?:,\d{3})*)\s*원/,
                                            /(\d{4,})\s*원/,
                                            /월\s*(\d{1,3}(?:,\d{3})*)\s*원/
                                        ];
                                        
                                        for (const pattern of patterns) {
                                            const match = text.match(pattern);
                                            if (match) {
                                                price = match[1].replace(/,/g, '');
                                                break;
                                            }
                                        }
                                    }
                                    
                                    return {
                                        name: name,
                                        price: price,
                                        element: item.outerHTML.substring(0, 300)
                                    };
                                }).filter(p => p.name);
                                
                                console.log(`[요금제] 추출된 요금제 개수: ${plans.length}`);
                                return plans;
                            } catch (e) {
                                console.error(`[요금제] 에러:`, e);
                                return [];
                            }
                        }
                    """, [item_selector, name_selector, price_attr, list_container])
                    
                    if plans:
                        options["plan"] = plans
                        print(f"    ✅ 요금제: {len(plans)}개 발견")
                        for plan in plans[:10]:  # 최대 10개까지 출력
                            price_str = f" ({plan.get('price', '')}원)" if plan.get('price') else " (가격 없음)"
                            print(f"      - {plan.get('name', 'N/A')}{price_str}")
                    else:
                        print(f"    ⚠️  요금제 추출 실패: 항목을 찾지 못함")
                else:
                    print(f"    ⚠️  요금제 선택자가 없음")
            except Exception as e:
                print(f"    ⚠️  요금제 추출 실패: {e}")
                import traceback
                traceback.print_exc()
        
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
    
    async def _select_options(self, page: Page, combo: Dict[str, str], structure: Dict[str, Any]):
        """옵션 선택 (선택자 기반 우선, 폴백으로 텍스트 기반)"""
        options_info = structure.get("options", {})
        execution_plan = structure.get("execution_plan", {})
        order = execution_plan.get("order", ["storage", "carrier", "join_type", "plan"])
        wait_times = execution_plan.get("wait_times", {})
        
        # 순서대로 옵션 선택
        for option_type in order:
            if option_type == "storage" and combo.get("storage"):
                storage_info = options_info.get("storage", {})
                if storage_info.get("selector"):
                    # 선택자 기반 선택
                    await self._select_by_selector(page, storage_info, combo["storage"])
                else:
                    # 텍스트 기반 폴백
                    await self._click_by_text(page, combo["storage"])
                await asyncio.sleep(wait_times.get("after_storage", 0.3))
            
            elif option_type == "carrier" and combo.get("carrier"):
                carrier_info = options_info.get("carrier", {})
                if carrier_info.get("selector"):
                    # 선택자 기반 선택
                    await self._select_by_selector(page, carrier_info, combo["carrier"])
                else:
                    # 텍스트 기반 폴백
                    await self._click_by_text(page, combo["carrier"])
                await asyncio.sleep(wait_times.get("after_carrier", 0.5))
            
            elif option_type == "join_type" and combo.get("join_type"):
                join_type_info = options_info.get("join_type", {})
                if join_type_info.get("selector"):
                    # 선택자 기반 선택
                    await self._select_by_selector(page, join_type_info, combo["join_type"])
                else:
                    # 텍스트 기반 폴백
                    await self._click_by_text(page, combo["join_type"])
                await asyncio.sleep(wait_times.get("after_join_type", 0.3))
            
            elif option_type == "plan" and combo.get("plan"):
                plan_info = options_info.get("plan", {})
                if plan_info.get("open_button_selector"):
                    # 요금제 드롭다운 열기
                    await self._select_plan(page, plan_info, combo["plan"], combo.get("plan_price"))
                else:
                    # 텍스트 기반 폴백
                    await self._click_by_text(page, combo["plan"])
                await asyncio.sleep(wait_times.get("after_plan", 1.0))
    
    async def _select_by_selector(self, page: Page, option_info: Dict[str, Any], value: str) -> bool:
        """선택자 기반으로 옵션 선택"""
        try:
            selector = option_info.get("selector")
            value_attr = option_info.get("value_attribute", "value")
            click_method = option_info.get("click_method", "click")
            
            if not selector:
                return False
            
            # value 속성으로 찾기
            if value_attr:
                result = await page.evaluate("""
                    ([selector, valueAttr, targetValue]) => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            for (const elem of elements) {
                                const attrValue = elem.getAttribute(valueAttr);
                                if (attrValue === targetValue || attrValue === String(targetValue)) {
                                    elem.click();
                                    return true;
                                }
                            }
                            return false;
                        } catch (e) {
                            return false;
                        }
                    }
                """, [selector, value_attr, value])
                
                if result:
                    return True
            
            # 텍스트로 찾기
            result = await page.evaluate("""
                ([selector, targetText]) => {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const elem of elements) {
                            if (elem.textContent && elem.textContent.trim().includes(targetText)) {
                                elem.click();
                                return true;
                            }
                        }
                        return false;
                    } catch (e) {
                        return false;
                    }
                }
            """, [selector, value])
            
            return result
            
        except Exception as e:
            print(f"      ⚠️  선택자 기반 선택 실패: {e}")
            return False
    
    async def _select_plan(self, page: Page, plan_info: Dict[str, Any], plan_name: str, plan_price: str = None) -> bool:
        """요금제 선택 (드롭다운 열고 선택)"""
        try:
            # 드롭다운 열기
            open_btn = plan_info.get("open_button_selector")
            if open_btn:
                btn_element = await page.query_selector(open_btn)
                if btn_element:
                    await btn_element.click()
                    await asyncio.sleep(0.5)
            
            # 요금제 항목 찾아서 클릭
            item_selector = plan_info.get("item_selector")
            name_selector = plan_info.get("name_selector", "")
            
            if item_selector:
                # 가격 우선 매칭 (있으면)
                if plan_price:
                    result = await page.evaluate("""
                        ([itemSelector, nameSelector, targetPrice]) => {
                            try {
                                const items = document.querySelectorAll(itemSelector);
                                for (const item of items) {
                                    const text = item.textContent || '';
                                    // 가격 찾기
                                    const priceMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)/);
                                    if (priceMatch) {
                                        const price = priceMatch[1].replace(/,/g, '');
                                        if (price === targetPrice) {
                                            item.click();
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            } catch (e) {
                                return false;
                            }
                        }
                    """, [item_selector, name_selector, plan_price])
                    
                    if result:
                        return True
                
                # 이름으로 매칭
                result = await page.evaluate("""
                    ([itemSelector, nameSelector, targetName]) => {
                        try {
                            const items = document.querySelectorAll(itemSelector);
                            for (const item of items) {
                                let name = '';
                                if (nameSelector) {
                                    const nameElem = item.querySelector(nameSelector);
                                    if (nameElem) {
                                        name = nameElem.textContent.trim();
                                    }
                                }
                                if (!name) {
                                    name = item.textContent.trim();
                                }
                                
                                if (name.includes(targetName)) {
                                    item.click();
                                    return true;
                                }
                            }
                            return false;
                        } catch (e) {
                            return false;
                        }
                    }
                """, [item_selector, name_selector, plan_name])
                
                return result
            
            return False
            
        except Exception as e:
            print(f"      ⚠️  요금제 선택 실패: {e}")
            return False
    
    async def _click_by_text(self, page: Page, text: str) -> bool:
        """텍스트로 요소 찾아서 클릭 (Playwright 기본 기능만 사용)"""
        try:
            await page.get_by_text(text, exact=False).first.click(force=True, timeout=1000)
            return True
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
