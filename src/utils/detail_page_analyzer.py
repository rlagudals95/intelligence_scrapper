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
        structure = step2_result.get("structure", {})
        step5_result = await self._step5_extract_policies(page, step4_result, step1_result, structure)
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
    
    async def _analyze_button_event_handler(self, page: Page, button_selector: str) -> Dict[str, Any]:
        """버튼의 이벤트 핸들러를 분석하여 어떤 동작을 하는지 추측"""
        
        analysis = await page.evaluate("""
            (selector) => {
                const button = document.querySelector(selector);
                if (!button) return { found: false };
                
                // 1. onclick 속성 확인
                const onclickAttr = button.getAttribute('onclick');
                
                // 2. 함수 소스 코드 추출 (onclick 또는 inline event)
                let handlerSource = onclickAttr || '';
                
                // 3. data 속성 확인
                const dataAttrs = {};
                for (const attr of button.attributes) {
                    if (attr.name.startsWith('data-')) {
                        dataAttrs[attr.name] = attr.value;
                    }
                }
                
                // 4. 핸들러 분석
                const analysis = {
                    found: true,
                    onclick: onclickAttr,
                    handlerSource: handlerSource,
                    dataAttrs: dataAttrs,
                    // AJAX 호출 감지
                    hasAjax: /ajax|fetch|XMLHttpRequest|\\$\\.post|\\$\\.get|\\$\\.ajax/i.test(handlerSource),
                    // DOM 조작 감지
                    hasShow: /show|display|visible|toggle|fadeIn|slideDown|addClass|removeClass/i.test(handlerSource),
                    // 특정 요소 타겟팅 감지
                    targets: []
                };
                
                // 타겟 요소 ID/클래스 추출
                const idMatches = handlerSource.match(/#([a-zA-Z_][a-zA-Z0-9_-]*)/g);
                const classMatches = handlerSource.match(/\\.([a-zA-Z_][a-zA-Z0-9_-]*)/g);
                
                if (idMatches) analysis.targets.push(...idMatches);
                if (classMatches) analysis.targets.push(...classMatches);
                
                return analysis;
            }
        """, button_selector)
        
        return analysis
    
    async def _click_and_detect_changes(self, page: Page, button_selector: str) -> Dict[str, Any]:
        """버튼 클릭 후 DOM 변화를 감지하여 새로 나타난 요소 찾기"""
        
        # MutationObserver 설정
        await page.evaluate("""
            () => {
                window._mutationLog = [];
                const observer = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        if (mutation.type === 'attributes' && 
                            (mutation.attributeName === 'style' || 
                             mutation.attributeName === 'class')) {
                            const el = mutation.target;
                            const style = window.getComputedStyle(el);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                const html = el.outerHTML || '';
                                const priceCount = (html.match(/\\d{2,3},?\\d{3}\\s*원/g) || []).length;
                                if (priceCount >= 3) {
                                    window._mutationLog.push({
                                        type: 'shown',
                                        selector: el.className || el.id || el.tagName,
                                        html: html.substring(0, 2000),
                                        priceCount: priceCount
                                    });
                                }
                            }
                        } else if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                            mutation.addedNodes.forEach((node) => {
                                if (node.nodeType === 1) {
                                    const html = node.outerHTML || '';
                                    const priceCount = (html.match(/\\d{2,3},?\\d{3}\\s*원/g) || []).length;
                                    if (priceCount >= 3) {
                                        window._mutationLog.push({
                                            type: 'added',
                                            selector: node.className || node.id || node.tagName,
                                            html: html.substring(0, 2000),
                                            priceCount: priceCount
                                        });
                                    }
                                }
                            });
                        }
                    });
                });
                observer.observe(document.body, {
                    attributes: true,
                    childList: true,
                    subtree: true,
                    attributeOldValue: true
                });
            }
        """)
        
        # 버튼 클릭
        try:
            await page.click(button_selector)
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"    ⚠️  버튼 클릭 실패: {e}")
            return {'method': 'click_failed'}
        
        # 변화 로그 가져오기
        mutations = await page.evaluate("() => window._mutationLog || []")
        
        # 가장 많은 가격 정보를 가진 변화 찾기
        best_mutation = None
        max_prices = 0
        
        for mutation in mutations:
            price_count = mutation.get('priceCount', 0)
            if price_count > max_prices:
                max_prices = price_count
                best_mutation = mutation
        
        if best_mutation:
            print(f"    ✅ DOM 변화 감지: {best_mutation['selector']} ({max_prices}개 가격)")
            return {
                'method': 'mutation_detected',
                'selector': best_mutation['selector'],
                'type': best_mutation['type'],
                'html': best_mutation['html'],
                'priceCount': max_prices
            }
        
        return {'method': 'no_mutation'}
    
    async def _monitor_ajax_and_click(self, page: Page, button_selector: str) -> List[Dict]:
        """버튼 클릭 후 발생하는 AJAX 요청 모니터링"""
        
        captured_responses = []
        
        async def handle_response(response):
            # JSON 응답만 캡처
            content_type = response.headers.get('content-type', '').lower()
            if 'json' in content_type or 'javascript' in content_type:
                try:
                    text = await response.text()
                    # JSON 파싱 시도
                    try:
                        data = json.loads(text)
                        captured_responses.append({
                            'url': response.url,
                            'status': response.status,
                            'data': data,
                            'text': text[:2000]
                        })
                    except:
                        # JSON이 아니면 텍스트로 저장
                        if '원' in text:
                            captured_responses.append({
                                'url': response.url,
                                'status': response.status,
                                'text': text[:5000]
                            })
                except Exception as e:
                    pass
        
        page.on('response', handle_response)
        
        # 버튼 클릭
        try:
            await page.click(button_selector)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"    ⚠️  버튼 클릭 실패: {e}")
        
        page.remove_listener('response', handle_response)
        
        print(f"    📡 캡처된 응답: {len(captured_responses)}개")
        
        # 응답에서 요금제 찾기
        for resp in captured_responses:
            if 'data' in resp:
                data = resp['data']
                # 응답 데이터에서 요금제 리스트 찾기
                if isinstance(data, dict):
                    for key in ['list', 'plans', 'items', 'data', 'result', 'rows']:
                        if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                            print(f"    ✅ AJAX 응답에서 데이터 발견: {key} ({len(data[key])}개)")
                            return data[key]
            elif 'text' in resp:
                # HTML이나 JavaScript 응답에 가격 정보가 있으면
                text = resp['text']
                price_count = text.count('원')
                if price_count >= 5:
                    print(f"    ✅ AJAX 응답에서 가격 정보 발견: {price_count}개")
                    return [{'html': text}]
        
        return []
    
    async def _extract_plans_smart(self, page: Page, open_button_selector: str) -> List[Dict[str, str]]:
        """
        통합 전략: 이벤트 분석 + DOM 변화 + AJAX 모니터링 + LLM
        """
        print("    [스마트 요금제 추출 시작]")
        
        if not open_button_selector:
            print("    ⚠️  open_button_selector가 없음")
            return []
        
        try:
            # 1단계: 이벤트 핸들러 분석
            print(f"    📋 1단계: 이벤트 핸들러 분석")
            handler_info = await self._analyze_button_event_handler(page, open_button_selector)
            
            if not handler_info or not handler_info.get('found'):
                print(f"    ⚠️  버튼을 찾지 못함: {open_button_selector}, 폴백 사용")
                # 폴백
                try:
                    await page.click(open_button_selector)
                    await asyncio.sleep(1.5)
                except:
                    pass
                return await self._extract_plan_list_with_llm(page)
            
            onclick_text = handler_info.get('onclick', 'None')
            print(f"    ├─ onclick: {onclick_text[:50] if onclick_text else 'None'}...")
            print(f"    ├─ AJAX: {handler_info.get('hasAjax', False)}")
            print(f"    ├─ DOM조작: {handler_info.get('hasShow', False)}")
            print(f"    └─ 타겟: {handler_info.get('targets', [])[:3]}")
        
            # 2단계: AJAX 요청이 있으면 모니터링
            if handler_info.get('hasAjax'):
                print(f"    🌐 2단계: AJAX 모니터링")
                ajax_data = await self._monitor_ajax_and_click(page, open_button_selector)
                if ajax_data:
                    # AJAX 데이터를 LLM으로 파싱
                    if isinstance(ajax_data[0], dict) and 'html' in ajax_data[0]:
                        html_content = ajax_data[0]['html']
                        return await self._extract_with_llm_from_html(html_content)
                    else:
                        # JSON 데이터 직접 파싱
                        return await self._parse_ajax_data(ajax_data)
            
            # 3단계: DOM 조작이 있으면 MutationObserver
            if handler_info.get('hasShow'):
                print(f"    🔄 3단계: DOM 변화 감지")
                mutation_result = await self._click_and_detect_changes(page, open_button_selector)
                
                if mutation_result.get('html'):
                    # 변화된 HTML을 LLM으로 추출
                    return await self._extract_with_llm_from_html(mutation_result['html'])
            
            # 4단계: 타겟 요소가 명시되어 있으면 직접 추출
            if handler_info.get('targets'):
                print(f"    🎯 4단계: 타겟 요소 직접 추출")
                for target in handler_info['targets'][:5]:  # 최대 5개만
                    try:
                        # onclick="show('#myModal')" 같은 경우
                        target_html = await page.evaluate(
                            f"() => document.querySelector('{target}')?.outerHTML"
                        )
                        if target_html and '원' in target_html:
                            price_count = target_html.count('원')
                            if price_count >= 5:
                                print(f"    ✅ 타겟 요소에서 가격 발견: {target} ({price_count}개)")
                                return await self._extract_with_llm_from_html(target_html)
                    except Exception as e:
                        continue
            
            # 5단계: 폴백 - 기존 방식 (단순 클릭 후 전체 body)
            print(f"    🔙 5단계: 폴백 - 전체 페이지 분석")
            try:
                await page.click(open_button_selector)
                await asyncio.sleep(1.5)
            except:
                pass
            
            return await self._extract_plan_list_with_llm(page)
        
        except Exception as e:
            print(f"    ⚠️  스마트 추출 실패: {e}")
            import traceback
            traceback.print_exc()
            # 최종 폴백
            try:
                await page.click(open_button_selector)
                await asyncio.sleep(1.5)
            except:
                pass
            return await self._extract_plan_list_with_llm(page)
    
    async def _parse_ajax_data(self, ajax_data: List[Dict]) -> List[Dict[str, str]]:
        """AJAX JSON 데이터에서 요금제 추출"""
        plans = []
        
        for item in ajax_data:
            # 요금제 이름과 가격 찾기
            name = None
            price = None
            
            # 일반적인 키 패턴
            name_keys = ['name', 'plan_name', 'title', 'bill_name', 'planName']
            price_keys = ['price', 'monthly_price', 'bill_price', 'fee', 'monthlyFee']
            
            for key in name_keys:
                if key in item:
                    name = item[key]
                    break
            
            for key in price_keys:
                if key in item:
                    price = str(item[key]).replace(',', '')
                    break
            
            if name and price:
                try:
                    price_int = int(price)
                    if price_int >= 60000:
                        plans.append({'name': name, 'price': str(price_int)})
                except:
                    pass
        
        print(f"    ✅ AJAX 데이터에서 {len(plans)}개 요금제 파싱")
        return plans
    
    async def _extract_with_llm_from_html(self, html: str) -> List[Dict[str, str]]:
        """HTML 조각에서 LLM으로 요금제 추출"""
        print(f"    🤖 LLM으로 HTML 분석 중... ({len(html)}자)")
        
        # HTML 크기 제한
        html = html[:200000]
        
        prompt = f"""
다음 HTML에서 **모든 휴대폰 요금제**를 추출하세요.

# HTML
{html}

# 규칙
1. 요금제 이름 + 가격이 있는 항목만
2. 60,000원 이상만
3. 부가 혜택(무제한, 넷플릭스 등) 제외

# 응답 (JSON 배열만)
[
  {{"name": "5G 심플 30GB", "price": 61000}}
]
"""
        
        try:
            response = await self.llm.complete(prompt, max_tokens=8000)
            response_text = response.strip()
            
            # JSON 파싱
            if "```" in response_text:
                lines = response_text.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or (not line.strip().startswith("```")):
                        json_lines.append(line)
                response_text = "\n".join(json_lines)
            
            start_idx = response_text.find("[")
            end_idx = response_text.rfind("]") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]
            
            plans = json.loads(response_text)
            
            # 가격 필터링 및 정규화
            valid_plans = []
            for p in plans:
                price = p.get("price")
                name = p.get("name", "")
                
                if isinstance(price, str):
                    price = int(price.replace(",", "")) if price.replace(",", "").isdigit() else 0
                elif isinstance(price, (int, float)):
                    price = int(price)
                else:
                    price = 0
                
                if price >= 60000:
                    valid_plans.append({"name": name, "price": str(price)})
            
            print(f"    ✅ LLM이 {len(valid_plans)}개 요금제 추출")
            return valid_plans
            
        except Exception as e:
            print(f"    ⚠️  LLM 추출 실패: {e}")
            return []
    
    async def _extract_plan_list_with_llm(self, page: Page) -> List[Dict[str, str]]:
        """
        LLM을 이용해 요금제 리스트 추출
        
        클릭 후 새로 나타난 요소의 HTML만 LLM에게 전달
        """
        print("    [LLM 기반 요금제 추출 시작]")
        
        try:
            # 클릭 후 모달/드롭다운 HTML 직접 추출
            extraction_result = await page.evaluate("""
                () => {
                    console.log('[요금제 추출] 시작');
                    
                    // 전체 요소 중에서 가격 정보가 가장 많은 요소 찾기
                    let bestElement = null;
                    let maxPrices = 0;
                    let bestInfo = '';
                    
                    // 모든 요소를 순회
                    const allElements = document.querySelectorAll('*');
                    
                    for (const el of allElements) {
                        const style = window.getComputedStyle(el);
                        
                        // 보이는 요소만 체크
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            continue;
                        }
                        
                        const html = el.innerHTML || '';
                        // "원" 패턴 카운트
                        const priceMatches = html.match(/\\d{2,3},?\\d{3}\\s*원|월\\s*\\d{2,3},?\\d{3}\\s*원/g);
                        const priceCount = priceMatches ? priceMatches.length : 0;
                        
                        // 가격이 5개 이상이고, 자식 요소가 많은 (리스트 형태) 요소 우선
                        if (priceCount >= 5) {
                            const children = el.querySelectorAll('[class*="item"], [class*="list"], li, div');
                            const childrenCount = children.length;
                            
                            // 가격 수 + 자식 수로 점수 계산
                            const score = priceCount + (childrenCount * 0.1);
                            const prevScore = maxPrices + (bestElement ? bestElement.querySelectorAll('[class*="item"], [class*="list"], li, div').length * 0.1 : 0);
                            
                            if (score > prevScore) {
                                maxPrices = priceCount;
                                bestElement = el;
                                const className = el.className || el.id || el.tagName;
                                bestInfo = `${className} (${childrenCount}개 자식)`;
                                console.log(`[후보] ${bestInfo}: ${priceCount}개 가격`);
                            }
                        }
                    }
                    
                    if (bestElement && maxPrices >= 5) {
                        console.log(`[최종 선택] ${bestInfo}: ${maxPrices}개 가격 정보`);
                        return {
                            html: bestElement.outerHTML,
                            method: 'price_density',
                            priceCount: maxPrices,
                            info: bestInfo
                        };
                    }
                    
                    // 찾지 못했으면 전체 body 반환
                    console.log('[폴백] body 전체 사용');
                    return {
                        html: document.body.innerHTML,
                        method: 'body_fallback',
                        priceCount: 0,
                        info: 'body'
                    };
                }
            """)
            
            newly_visible_html = extraction_result.get("html", "")
            extraction_method = extraction_result.get("method", "unknown")
            price_count = extraction_result.get("priceCount", 0)
            element_info = extraction_result.get("info", "")
            
            print(f"    🔍 추출 방법: {extraction_method}")
            print(f"    📊 가격 정보: {price_count}개")
            print(f"    🎯 요소: {element_info}")
            
            if not newly_visible_html:
                print("    ⚠️  HTML을 찾지 못함")
                return []
            
            # HTML 크기 제한 확대 (200KB)
            newly_visible_html = newly_visible_html[:200000]
            print(f"    📄 추출된 HTML 크기: {len(newly_visible_html)}자")
            
            # LLM에게 요금제 추출 요청 (프롬프트 강화)
            prompt = f"""
# 임무
다음 HTML에서 **모든 휴대폰 요금제**를 빠짐없이 추출하세요.

# HTML
{newly_visible_html}

# 중요 지침
1. **완전성**: HTML에 있는 **모든** 요금제를 추출하세요 (보통 10~15개)
2. **요금제 식별**:
   - "5G" 또는 "LTE"로 시작하는 이름
   - "월 XX,XXX원" 또는 "XX,XXX원" 형태의 가격
   - 예: "5G 심플 30GB", "5G 초이스 베이직", "5G 프리미어 플러스"
3. **제외 항목**:
   - 부가 혜택만 있는 항목 ("무제한", "넷플릭스", "10GB+1Mbps")
4. **필터**:
   - 60,000원 이상만
   - 가격은 숫자만 (쉼표 제거)

# 추출 방법
HTML을 꼼꼼히 스캔하여:
- 반복되는 패턴 찾기
- 각 패턴에서 요금제 이름과 가격 추출
- 리스트 끝까지 모두 추출

# 응답 (JSON 배열만, **최소 10개 이상** 추출)
[
  {{"name": "5G 초이스 스페셜", "price": 110000}},
  {{"name": "5G 스페셜", "price": 100000}},
  {{"name": "5G 초이스 베이직", "price": 90000}},
  {{"name": "5G 베이직", "price": 80000}},
  {{"name": "5G 심플 110GB", "price": 69000}},
  {{"name": "5G 심플 90GB", "price": 67000}},
  {{"name": "5G 심플 70GB", "price": 65000}},
  {{"name": "5G 심플 50GB", "price": 63000}},
  {{"name": "5G 심플 30GB", "price": 61000}}
]

**지금 JSON 배열을 출력하세요. 모든 요금제를 포함해야 합니다.**
"""
            
            response = await self.llm.complete(prompt, max_tokens=8000)
            response_text = response.strip()
            
            print(f"    📝 LLM 응답 길이: {len(response_text)}자")
            
            # JSON 파싱
            # 코드 블록 제거
            if "```" in response_text:
                lines = response_text.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or (not line.strip().startswith("```")):
                        json_lines.append(line)
                response_text = "\n".join(json_lines)
            
            # JSON 배열 시작/끝 찾기
            start_idx = response_text.find("[")
            end_idx = response_text.rfind("]") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]
            
            try:
                plans = json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON 파싱 실패: {e}")
                print(f"    응답: {response_text[:500]}")
                return []
            
            # 가격이 있는 항목만 필터링
            valid_plans = []
            for p in plans:
                price = p.get("price")
                name = p.get("name", "")
                
                # 가격 정수로 변환
                if isinstance(price, str):
                    price = int(price.replace(",", "")) if price.replace(",", "").isdigit() else 0
                elif isinstance(price, (int, float)):
                    price = int(price)
                else:
                    price = 0
                
                # 부가정보 필터링 (무제한, 데이터 용량만 있는 항목 제외)
                exclude_keywords = ["무제한", "Mbps", "Kbps", "넷플릭스", "디즈니", "티빙", "지니", "멤버쉽", "VIP"]
                is_benefit_only = any(kw in name for kw in exclude_keywords) and price == 0
                
                if price > 0 and not is_benefit_only:
                    valid_plans.append({
                        "name": name,
                        "price": str(price)
                    })
            
            print(f"    ✅ LLM이 {len(valid_plans)}개 유효 요금제 추출")
            return valid_plans
            
        except Exception as e:
            print(f"    ⚠️  LLM 요금제 추출 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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
                
                # 드롭다운/다이얼로그 열기
                open_btn = plan_info.get("open_button_selector")
                
                # 스마트 요금제 추출: 이벤트 분석 + DOM 변화 + AJAX 모니터링
                plans = await self._extract_plans_smart(page, open_btn)
                
                if plans:
                    options["plan"] = plans
                    print(f"    ✅ 요금제: {len(plans)}개 발견 (LLM 기반)")
                    for plan in plans[:10]:  # 최대 10개까지 출력
                        price_str = f" ({plan.get('price', '')}원)" if plan.get('price') else " (가격 없음)"
                        print(f"      - {plan.get('name', 'N/A')}{price_str}")
                else:
                    print(f"    ⚠️  요금제 추출 실패: LLM이 요금제를 찾지 못함")
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
            
            # 요금제 가격 추출
            plan_price = combo.get("plan_price", "0")
            if isinstance(plan_price, str):
                plan_price = int(plan_price) if plan_price.isdigit() else 0
            
            policy = Policy(
                policy_id=policy_id,
                carrier=carrier,
                mno_join_type=join_type,
                mobile_plan=MobilePlan(
                    name=combo.get("plan") or "Unknown",
                    monthly_fee=plan_price
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
