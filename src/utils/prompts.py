"""
Prompt Templates (Phase 2 & Phase 3)
LLM 분석용 프롬프트 템플릿
"""


# ============================================================================
# 리스팅 페이지 분석
# ============================================================================

LISTING_PAGE_ANALYSIS_SYSTEM = """
당신은 웹 페이지 구조 분석 전문가입니다.
휴대폰 판매 리스팅 페이지의 HTML 구조를 분석하여 상품 카드를 찾고, 
각 정보(기종명, 가격, 요금제 등)의 CSS 셀렉터를 정확하게 추출해야 합니다.

📸 스크린샷 기반 분석 우선:
1. 스크린샷 이미지를 보고 지원금 금액(숫자)이 시각적으로 어디에 위치하는지 먼저 파악
2. 해당 위치의 HTML 요소를 찾아 셀렉터 생성
3. 반드시 숫자가 보이는 요소를 선택

🚨 CRITICAL 규칙: 
- 지원금 셀렉터는 반드시 숫자(0-9)를 포함한 요소를 선택해야 합니다.
- "원", "공시지원 :", "추가 지원금 :" 같은 레이블이나 단위만 있는 요소는 절대 선택 금지!
- 형제 요소로 분리된 경우: 숫자가 있는 요소만 선택 (레이블이나 단위 요소 X)
"""

LISTING_PAGE_ANALYSIS_PROMPT = """
📸 이미지와 HTML을 함께 분석하세요:
1. **스크린샷 이미지를 먼저 확인**: 지원금 금액이 시각적으로 어디에 표시되는지 파악
2. **HTML에서 해당 위치 찾기**: 이미지에서 본 숫자가 어떤 HTML 요소에 있는지 확인
3. **셀렉터 생성**: 그 숫자를 포함한 요소의 CSS 셀렉터 작성

⚠️ 주의: 지원금 셀렉터는 반드시 숫자가 포함된 요소를 선택해야 합니다. "원"만 있는 요소는 절대 선택 금지!

다음 HTML은 휴대폰 판매 리스팅 페이지입니다.
이 페이지를 분석하여 아래 정보를 JSON 형식으로 추출해주세요.

# 추출할 정보

**필수 정보:**
1. **product_card_selector**: 각 상품을 감싸는 컨테이너의 CSS 셀렉터
2. **product_name_selector**: 휴대폰 기종명(예: "갤럭시 S24 Ultra")이 있는 요소의 CSS 셀렉터 (카드 내부 기준)
3. **detail_link_selector**: 상세 페이지로 가는 링크 요소의 CSS 셀렉터 (카드 내부 기준)

**선택 정보 (리스팅에 표시된 경우만):**
4. **carrier_selector**: 통신사(SKT, KT, LGU+ 등)의 CSS 셀렉터
   - SKT, KT, LGU+ 중 하나를 선택
5. **signup_type_selector**: 변경유형(번호이동, 기기변경, 신규가입 등)의 CSS 셀렉터
6. **retail_price_selector**: 출고가의 CSS 셀렉터
7. **discount_price_selector**: 할인가/최종가의 CSS 셀렉터

**지원금 정보 (매우 중요! 반드시 숫자를 포함한 요소를 선택!):**
8. **subsidy_type_selector**: 지원금 타입 레이블의 CSS 셀렉터
   - 예: "공시지원", "선택약정"
   - 공시지원 혹은 선택 약정 중 하나를 선택
   
9. **public_subsidy_selector**: 공시지원금 금액이 들어있는 요소의 CSS 셀렉터
   - 📸 **이미지 분석 필수**: 스크린샷에서 "공시지원", "공통지원금", "통신사지원금" 레이블 근처에 표시된 **숫자**를 찾으세요
   - 🎯 **반드시 그 숫자를 포함한 HTML 요소를 선택!**
   - 📋 **HTML 패턴 분석 (이미지에서 확인한 숫자의 위치를 HTML에서 찾기)**:
     ```html
     <!-- 패턴 A: 레이블, 숫자, 단위가 형제 요소로 분리 -->
     <li>
       <span class="label">공시지원 :</span>
       <span class="value">600,000</span>  ← 이미지에서 본 숫자가 여기 있음! 선택! ✅
       <span class="unit">원</span>  ← 이건 단위만! 선택 금지! ❌
     </li>
     셀렉터 예: li > span.value 또는 li > span:nth-child(2)
     
     <!-- 패턴 B: 레이블+숫자+단위가 하나의 요소 -->
     <p>공통지원금 : 500,000원</p>  ← 이 요소 선택 ✅
     ```
   - ⚠️ **검증**: 선택한 요소의 `textContent`에 숫자가 있는지 확인 (예: "600,000" ✅, "원" ❌)
   - ❌ **절대 선택 금지**: "원", "공시지원 :", "공통지원금 :" 같은 레이블/단위만 있는 요소
    
10. **additional_subsidy_selector**: 추가지원금 금액이 들어있는 요소의 CSS 셀렉터
   - 📸 **이미지 분석 필수**: 스크린샷에서 "추가 지원금", "제휴할인", "판매점 할인" 레이블 근처에 표시된 **숫자**를 찾으세요
   - 🎯 **반드시 그 숫자를 포함한 HTML 요소를 선택!**
   - 📋 **HTML 패턴 분석 (이미지에서 확인한 숫자의 위치를 HTML에서 찾기)**:
     ```html
     <!-- 패턴 A: 레이블, 숫자, 단위가 형제 요소로 분리 -->
     <li>
       <span class="label">추가 지원금 :</span>
       <span class="amount">739,300</span>  ← 이미지에서 본 숫자가 여기 있음! 선택! ✅
       <span class="unit">원</span>  ← 이건 단위만! 선택 금지! ❌
     </li>
     셀렉터 예: li > span.amount 또는 li > span:nth-child(2)
     
     <!-- 패턴 B: 레이블+숫자+단위가 하나의 요소 -->
     <p>판매점 제휴할인 : 820,000원</p>  ← 이 요소 선택 ✅
     ```
   - ⚠️ **검증**: 선택한 요소의 `textContent`에 숫자가 있는지 확인 (예: "739,300" ✅, "원" ❌)
   - ❌ **절대 선택 금지**: "원", "추가 지원금 :", "제휴할인" 같은 레이블/단위만 있는 요소

**요금제 정보 (지원금 타입과 혼동하지 말 것!):**
11. **plan_name_selector**: 실제 통신 요금제명과 요금의 CSS 셀렉터
   - 예: "5G 프리미어 에센셜", "ZEM플랜 스마트 (만 13세 미만)", "프리미엄(OTT 택1)"
   - "공시지원", "선택약정"은 요금제가 아님! 지원금 타입임

**기타 정보:**
12. **benefits_selector**: 혜택/사은품/프로모션의 CSS 셀렉터
13. **image_selector**: 제품 이미지의 CSS 셀렉터 (보통 "img")

**페이지네이션:**
14. **pagination_type**: "pagination" (버튼 있음) | "infinite_scroll" (무한 스크롤) | "none" (단일 페이지)
15. **next_button_selector**: 다음 페이지 버튼 또는 "더보기" 버튼의 CSS 셀렉터 (pagination인 경우만)

# 응답 형식 (JSON)

```json
{{
  "product_card_selector": ".product-item",
  "product_name_selector": ".product-title",
  "detail_link_selector": "a.detail-link",
  "carrier_selector": ".carrier-badge",
  "signup_type_selector": ".signup-type",
  "retail_price_selector": ".retail-price",
  "discount_price_selector": ".final-price",
  "subsidy_type_selector": ".subsidy-type-label",
  "public_subsidy_selector": ".subsidy-amount.public",
  "additional_subsidy_selector": ".subsidy-amount.additional",
  "plan_name_selector": ".plan-info .plan-name",
  "benefits_selector": ".promotion-text",
  "image_selector": "img.product-image",
  "pagination_type": "pagination",
  "next_button_selector": ".pagination .next"
}}
```

# 분석 규칙

- CSS 셀렉터는 가능한 한 구체적이고 안정적으로 (id, class, data-* 속성 사용)
- 상대 셀렉터를 사용할 수 있음 (예: ".card > .title")
- 리스팅에 표시되지 않은 정보는 null 또는 빈 문자열("")로 설정

**🚨 매우 중요한 구분 (반드시 지켜야 함!):**

1. **요금제 (plan_name)**: 통신사 요금제 이름
   - ✓ 올바른 예: "5G 프리미어 에센셜", "ZEM플랜 스마트", "5G 초이스 스페셜"
   - ✗ 잘못된 예: "공시지원", "선택약정" (이건 지원금 타입!)
  
2. **지원금 타입 (subsidy_type)**: 지원금 방식 (레이블만)
   - ✓ 올바른 예: "공시지원", "선택약정"
   - ✗ 잘못된 예: "500,000원", "원" (이건 금액이거나 단위!)
  
3. **공시지원금 (public_subsidy)**: 숫자를 포함한 요소 (레이블이 함께 있어도 OK)
   - ✅ 셀렉터가 선택하는 값 예시:
     - "500,000" ✅ (숫자만)
     - "152,000원" ✅ (숫자+단위)
     - "공통지원금 : 600,000원" ✅ (레이블+숫자+단위)
   - ❌ 선택하면 안 되는 값: "원", "공시지원 :", "공시지원" (숫자 없음!)
   - 💡 전략: 숫자가 분리되어 있으면 숫자만, 함께 있으면 함께 선택
  
4. **추가지원금 (additional_subsidy)**: 숫자를 포함한 요소 (레이블이 함께 있어도 OK)
   - ✅ 셀렉터가 선택하는 값 예시:
     - "739,300" ✅ (숫자만)
     - "820,000원" ✅ (숫자+단위)
     - "판매점 제휴할인 : 820,000원" ✅ (레이블+숫자+단위)
   - ❌ 선택하면 안 되는 값: "원", "추가 지원금 :", "제휴할인" (숫자 없음!)
   - 💡 전략: 숫자가 분리되어 있으면 숫자만, 함께 있으면 함께 선택

**🎯 셀렉터 선택 원칙 (모든 사이트 공통):**

1. **핵심 규칙**: 반드시 숫자(0-9)를 포함한 요소를 선택
   - 숫자가 있다면 레이블이나 단위가 함께 있어도 OK
   - 숫자가 없다면 절대 선택 금지

2. **우선순위 A**: 숫자만 분리되어 있으면 → 숫자 요소만 선택 (최선)
   ```html
   <li>
     <span class="label">추가 지원금 :</span>
     <span class="value">739,300</span>  ← 선택 ✅
     <span class="unit">원</span>  ← 선택 금지 ❌
   </li>
   ✅ 셀렉터: li > span.value 또는 li > span:nth-child(2)
   ```

3. **우선순위 B**: 레이블+숫자가 함께 있으면 → 그 요소 선택 (차선, 후처리에서 숫자 추출)
   ```html
   <p>판매점 제휴할인 : 820,000원</p>  ← 선택 ✅
   ✅ 셀렉터: p → "판매점 제휴할인 : 820,000원" (후처리: "820,000")
   ```

4. **절대 금지**: 숫자가 없는 요소
   ```html
   <span class="label">공시지원 :</span>  ← 숫자 없음 ❌
   <span class="unit">원</span>           ← 숫자 없음 ❌
   ```
   ❗️ **실수 사례**: `li > span.unit`이나 `li > span:last-child`를 선택하면 "원"만 추출됨 → 잘못된 선택!

5. **판단 기준**: 선택한 요소의 텍스트에 0~9 숫자가 최소 1개 이상 있어야 함
   - 브라우저 DevTools에서 셀렉터를 실행했을 때 숫자가 보이는지 확인
   - 예: `document.querySelector('li > span.value').textContent` → "739,300" ✅
   - 예: `document.querySelector('li > span.unit').textContent` → "원" ❌

**페이지네이션 타입 판단:**
- "다음", "Next", ">" 버튼 또는 "더보기", "Load More" 버튼이 있으면 → "pagination"
- 스크롤 시 자동으로 로딩되면 → "infinite_scroll"
- 모든 상품이 한 페이지에 있으면 → "none"

- 셀렉터가 여러 개 가능하면 가장 안정적인 것 선택

**⚡ 지원금 셀렉터 핵심 요약:**
- 반드시 숫자(0-9)를 포함한 요소를 선택
- 숫자가 분리되어 있으면 → 숫자만 (우선)
- 숫자가 레이블과 함께 있으면 → 함께 선택도 OK (후처리에서 정리됨)
- 숫자가 없는 요소는 절대 선택 금지 ("원", "공시지원 :", "제휴할인" 등)

# HTML

{html_content}

**🚨 최종 확인 (지원금 셀렉터만!):**
1. **스크린샷을 다시 보세요**: 지원금 금액(숫자)이 어디에 표시되는지 시각적으로 확인
2. **HTML에서 그 위치를 찾으세요**: 이미지에서 본 숫자가 있는 HTML 요소 확인
3. **셀렉터가 그 요소를 가리키는지 검증**:
   - `public_subsidy_selector` → 숫자 포함 요소? (예: "600,000" ✅, "원" ❌)
   - `additional_subsidy_selector` → 숫자 포함 요소? (예: "739,300" ✅, "원" ❌)
4. **잘못된 선택 사례**: `span.kw`, `span.unit`, `span:last-child` 등은 보통 "원"만 있음 → 피하기!

위 HTML을 분석하여 JSON만 출력하세요. 추가 설명 없이 JSON만 반환하세요.
"""


# ============================================================================
# 상세 페이지 옵션 분석
# ============================================================================

DETAIL_PAGE_OPTIONS_SYSTEM = """
당신은 휴대폰 구매 옵션 UI 분석 전문가입니다.
상세 페이지에서 통신사, 가입유형, 요금제, 할부, 용량, 색상 등의 
선택 옵션을 찾고 추출하는 것이 당신의 역할입니다.
"""

DETAIL_PAGE_OPTIONS_PROMPT = """
다음 HTML은 휴대폰 상세 페이지입니다.
이 페이지에서 구매 옵션 UI를 분석하여 정보를 추출해주세요.

# 추출할 정보

1. **통신사 선택 UI**
   - 셀렉터: CSS 셀렉터
   - 타입: "select" | "radio" | "button" | "tab"
   - 옵션 목록 추출 방법

2. **가입유형 선택 UI** (번호이동/기기변경/신규가입)
   - 동일한 구조

3. **요금제 선택 UI**
   - 동일한 구조

4. **할부/약정 선택 UI**
   - 동일한 구조

5. **용량 선택 UI** (64GB, 128GB 등)
   - 동일한 구조

6. **색상 선택 UI**
   - 동일한 구조

# 응답 형식 (JSON)

```json
{{
  "carrier": {{
    "selector": "#carrier-select",
    "type": "select",
    "option_selector": "option",
    "exists": true
  }},
  "signup_type": {{
    "selector": "input[name='signup']",
    "type": "radio",
    "option_selector": "input[name='signup']",
    "exists": true
  }},
  "plan": {{
    "selector": ".plan-list .plan-item",
    "type": "button",
    "option_selector": ".plan-list .plan-item",
    "exists": true
  }},
  "installment": {{
    "selector": "#installment",
    "type": "select",
    "option_selector": "option",
    "exists": true
  }},
  "storage": {{
    "selector": ".storage-btn",
    "type": "button",
    "option_selector": ".storage-btn",
    "exists": true
  }},
  "color": {{
    "selector": ".color-btn",
    "type": "button",
    "option_selector": ".color-btn",
    "exists": true
  }}
}}
```

# 분석 규칙

- "exists"가 false면 해당 옵션이 페이지에 없는 것
- "option_selector"는 개별 옵션 항목을 선택하는 셀렉터
- 타입을 정확히 판단 (select/radio/button/tab)
- 옵션이 없으면 exists: false, 나머지 필드는 null

# HTML

{html_content}

위 HTML을 분석하여 JSON만 출력하세요.
"""


# ============================================================================
# 가격/정책 영역 분석
# ============================================================================

PRICING_AREA_SYSTEM = """
당신은 가격 정보 추출 전문가입니다.
휴대폰 구매 페이지에서 가격, 할부, 지원금 등의 정보를 찾아 추출합니다.
"""

PRICING_AREA_PROMPT = """
다음 HTML에서 가격/정책 정보를 추출해주세요.

# 추출할 정보

1. **최종가**: 고객이 실제로 지불하는 최종 가격
2. **할부원금**: 할부 원금
3. **월 납부금**: 매월 납부하는 금액
4. **공시지원금**: 공시지원금
5. **추가지원금**: 추가지원금
6. **요금제 조건**: 요금제 결합 조건 텍스트
7. **정책 텍스트**: 면책/주의사항 등

# 응답 형식 (JSON)

```json
{{
  "final_price": {{
    "selector": ".final-price",
    "exists": true
  }},
  "installment_principal": {{
    "selector": ".installment-amount",
    "exists": true
  }},
  "monthly_payment": {{
    "selector": ".monthly-payment",
    "exists": true
  }},
  "subsidy_official": {{
    "selector": ".official-subsidy",
    "exists": true
  }},
  "subsidy_additional": {{
    "selector": ".additional-subsidy",
    "exists": true
  }},
  "plan_condition": {{
    "selector": ".plan-condition",
    "exists": true
  }},
  "policy_text": {{
    "selector": ".policy-notice",
    "exists": true
  }}
}}
```

# 분석 규칙

- 가격 요소는 숫자가 포함된 텍스트를 찾으세요
- 셀렉터는 가격 값이 표시되는 요소를 가리켜야 합니다
- 없는 정보는 exists: false

# HTML

{html_content}

위 HTML을 분석하여 JSON만 출력하세요.
"""


# ============================================================================
# 옵션 값 정규화
# ============================================================================

OPTION_NORMALIZATION_SYSTEM = """
당신은 텍스트 정규화 전문가입니다.
다양한 형태로 표현된 통신사, 가입유형 등을 표준 형식으로 변환합니다.
"""

OPTION_NORMALIZATION_PROMPT = """
다음 텍스트를 표준 형식으로 정규화해주세요.

# 정규화 규칙

**통신사**
- SKT, SK텔레콤, 에스케이텔레콤, SK → "SKT"
- KT, 케이티 → "KT"  
- LG U+, LGU+, 엘지유플러스, LG유플러스 → "LGU+"

**가입유형**
- 번호이동, 번이 → "번호이동"
- 기기변경, 기변 → "기기변경"
- 신규가입, 신규 → "신규가입"

**용량**
- 숫자 + GB 형식으로 (예: "256GB")

**색상**
- 첫 글자 대문자 (예: "블랙" → "블랙", "Black" → "블랙")

# 입력 텍스트

{text}

# 출력 형식

정규화된 텍스트만 출력하세요. 추가 설명 없이.
"""


# ============================================================================
# 유틸리티 함수
# ============================================================================

def format_listing_analysis_prompt(html_content: str) -> str:
    """리스팅 분석 프롬프트 생성"""
    return LISTING_PAGE_ANALYSIS_PROMPT.format(html_content=html_content)


def format_detail_options_prompt(html_content: str) -> str:
    """상세 페이지 옵션 분석 프롬프트 생성"""
    return DETAIL_PAGE_OPTIONS_PROMPT.format(html_content=html_content)


def format_pricing_area_prompt(html_content: str) -> str:
    """가격 영역 분석 프롬프트 생성"""
    return PRICING_AREA_PROMPT.format(html_content=html_content)


def format_normalization_prompt(text: str) -> str:
    """정규화 프롬프트 생성"""
    return OPTION_NORMALIZATION_PROMPT.format(text=text)


# ============================================================================
# Phase 3B: 화면 기반 정책 추출
# ============================================================================

SCREEN_PAGE_STRUCTURE_SYSTEM = """
당신은 휴대폰 구매 페이지 분석 전문가입니다.
상세 페이지의 HTML을 분석하여 다음을 식별해야 합니다:
1. 옵션 선택 UI (용량, 색상, 통신사, 가입유형, 요금제)
2. 가격 표시 영역 (출고가, 지원금, 할부금, 최종가)

정확한 CSS 셀렉터를 제공하여 Playwright로 요소를 찾을 수 있도록 해야 합니다.

🚨 중요: 실제 HTML 구조를 분석하여 존재하는 요소의 실제 셀렉터를 반환하세요.
"""

SCREEN_PAGE_STRUCTURE_PROMPT = """
주어진 HTML에서 실제로 존재하는 요소의 셀렉터를 찾으세요.

# HTML (실제 페이지)
{html}

# 분석 방법

1. **HTML을 직접 읽으세요**: class, id, name 속성을 확인
2. **실제 존재하는 요소만 반환**: 추측하지 마세요
3. **테스트 가능한 셀렉터**: document.querySelector()로 찾을 수 있어야 함

# 찾아야 할 요소

## 옵션 선택 UI

HTML에서 다음 옵션 UI를 찾으세요:

**용량 (storage)**:
- "256GB", "512GB", "1TB" 같은 텍스트가 있는 버튼/탭/select
- 실제 HTML에서 class나 id 확인
- type: "button" | "tab" | "select" | "radio"
- selector: 실제 CSS 셀렉터

**색상 (color)**:
- 색상 선택 UI (있으면)
- 색상 버튼이나 스와치를 찾으세요

**통신사 (carrier)**:
- SKT, KT, LG U+ 등의 로고나 텍스트
- 실제 HTML에서 찾으세요

**가입유형 (join_type)**:
- "번호이동", "기기변경", "신규가입" 버튼/탭
- 실제 HTML에서 찾으세요

**요금제 (plan)**:
- 요금제 선택 드롭다운이나 버튼
- 있는 경우만 반환

## 가격 표시 영역

HTML에서 다음 가격 정보가 표시된 요소를 찾으세요:

- **출고가**: "출고가", "기기가격" 근처의 금액
- **공시지원금**: "공시지원금", "공통지원금" 근처의 금액
- **추가지원금**: "추가 지원금", "제휴할인" 근처의 금액
- **할부원금**: "할부원금", "제휴카드" 근처의 금액
- **월 할부금**: "월 할부금", "월 납부" 근처의 금액
- **월 통신요금**: "월 통신요금", "월 요금" 근처의 금액

**주의**: 
- 실제 HTML에서 해당 텍스트를 찾으세요
- 없으면 null로 반환
- 추측하지 마세요

# 응답 형식 (JSON)

{{
  "options": {{
    "storage": {{
      "type": "button",
      "selector": ".actual-storage-button-class"
    }},
    "color": {{
      "type": "button", 
      "selector": ".actual-color-button-class"
    }},
    "carrier": {{
      "type": "button",
      "selector": ".actual-carrier-button-class"
    }},
    "join_type": {{
      "type": "button",
      "selector": ".actual-jointype-button-class"
    }}
  }},
  "pricing": {{
    "retail_price_selector": ".actual-retail-price-class",
    "public_subsidy_selector": ".actual-subsidy-class",
    "additional_subsidy_selector": ".actual-additional-class",
    "installment_principal_selector": ".actual-installment-class",
    "monthly_payment_selector": ".actual-monthly-class",
    "plan_monthly_fee_selector": ".actual-plan-fee-class"
  }}
}}

위 예시는 형식일 뿐입니다. 실제 HTML에서 찾은 셀렉터로 교체하세요!

**JSON만 출력하세요. 예시 값을 그대로 반환하지 마세요!**
"""

SCREEN_EXTRACT_PRICING_SYSTEM = """
당신은 웹 페이지에서 가격 정보를 추출하는 전문가입니다.
HTML에서 휴대폰 구매 관련 가격 정보를 정확히 파싱해야 합니다.

🚨 핵심 규칙:
1. 반드시 HTML에서 실제 텍스트를 찾아야 합니다
2. 예시 값을 반환하지 마세요
3. 가격은 주로 <span class="unit-w">숫자</span> 패턴으로 표시됩니다
4. <dt> 태그에 레이블, <dd> 태그에 값이 있는 패턴을 찾으세요
"""

SCREEN_EXTRACT_PRICING_PROMPT = """
주어진 HTML에서 **실제 가격 정보**를 추출하세요.

# HTML (실제 페이지)
{html}

# 분석 방법

1. **HTML 패턴 파악**:
   - 휴대폰 가격은 보통 `<dt>레이블</dt><dd>가격</dd>` 구조
   - 가격 숫자는 보통 `<span class="unit-w">1,980,000</span>` 형태
   - 예: `<dt>출고가</dt><dd class="sp"><span class="unit-w">1,980,000</span><span>원</span></dd>`

2. **키워드로 검색**:
   - HTML에서 다음 키워드를 찾으세요
   - 키워드 근처의 숫자를 추출하세요

# 추출 작업

HTML을 읽으면서 다음 키워드를 찾고, 그 근처의 **실제 숫자**를 추출하세요:

1. **출고가** → "출고가" 키워드 찾기 → 그 근처의 숫자 (예: 1,980,000)
2. **공시지원금** → "공시지원금" 또는 "공시지원" 키워드 → 근처 숫자
3. **추가 지원금** → "추가 지원금" 또는 "추가지원금" 키워드 → 근처 숫자 (마이너스 가능)
4. **할부원금** → "할부원금" 키워드 → 근처 숫자 (제휴카드 관련)
5. **월 할부금** → "월 할부금" 키워드 → 근처 숫자
6. **월 통신요금** → "월 통신요금" 또는 "월통신요금" 키워드 → 근처 숫자
7. **월 납부금액** → "월 납부금액" 또는 "월납부총액" 키워드 → 근처 숫자 (A+B 합계)
8. **요금제** → 요금제명 (예: "5GX 프리미엄", "5G 초이스") → 그 근처의 월요금

# 검색 전략

```
예시 HTML:
<dt>출고가</dt>
<dd class="sp"><span class="unit-w">1,980,000</span><span>원</span></dd>

추출 과정:
1. "출고가" 텍스트 발견
2. 그 다음 <dd> 태그 확인
3. <span class="unit-w"> 안의 숫자 추출: "1,980,000"
4. 콤마 제거 → 1980000 (정수)
```

# 추출 결과 (JSON)

HTML에서 실제로 찾은 값만 반환하세요:

{{
  "retail_price": 1980000,
  "public_subsidy": null,
  "additional_subsidy": -550000,
  "installment_principal": 1430000,
  "monthly_payment": 63314,
  "final_price": 145064,
  "plan_name": "5GX 프리미엄",
  "plan_monthly_fee": 109000
}}

위는 실제 값의 예시입니다. HTML에서 다른 값을 찾으면 그 값을 반환하세요!

# 중요

- **콤마 제거**: "1,980,000" → 1980000
- **마이너스**: "-550,000" → -550000  
- **정보 없으면**: null
- **반드시 HTML에서 실제 값을 찾으세요**

**JSON만 출력하세요. 다른 설명 없이.**
"""


def format_screen_page_structure_prompt(html: str) -> str:
    """Phase 3B: 페이지 구조 분석 프롬프트"""
    # 더 많은 HTML 제공 (20000자)
    if len(html) > 20000:
        html = html[:20000] + "\n\n...(나머지 HTML 생략)..."
    return SCREEN_PAGE_STRUCTURE_PROMPT.format(html=html)


def format_screen_extract_pricing_prompt(html: str) -> str:
    """Phase 3B: 가격 추출 프롬프트"""
    # 더 많은 HTML 제공 (15000자)
    if len(html) > 15000:
        html = html[:15000] + "\n\n...(나머지 HTML 생략)..."
    return SCREEN_EXTRACT_PRICING_PROMPT.format(html=html)

