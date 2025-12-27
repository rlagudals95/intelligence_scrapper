"""
Prompt Templates (Phase 2)
LLM 분석용 프롬프트 템플릿
"""


# ============================================================================
# 리스팅 페이지 분석
# ============================================================================

LISTING_PAGE_ANALYSIS_SYSTEM = """
당신은 웹 페이지 구조 분석 전문가입니다.
휴대폰 판매 리스팅 페이지의 HTML 구조를 분석하여 상품 카드를 찾고, 
각 정보(기종명, 가격, 요금제 등)의 CSS 셀렉터를 정확하게 추출해야 합니다.
"""

LISTING_PAGE_ANALYSIS_PROMPT = """
다음 HTML은 휴대폰 판매 리스팅 페이지입니다.
이 페이지를 분석하여 아래 정보를 JSON 형식으로 추출해주세요.

# 추출할 정보

**필수 정보:**
1. **product_card_selector**: 각 상품을 감싸는 컨테이너의 CSS 셀렉터
2. **product_name_selector**: 휴대폰 기종명(예: "갤럭시 S24 Ultra")이 있는 요소의 CSS 셀렉터 (카드 내부 기준)
3. **detail_link_selector**: 상세 페이지로 가는 링크 요소의 CSS 셀렉터 (카드 내부 기준)

**선택 정보 (리스팅에 표시된 경우만):**
4. **signup_type_selector**: 변경유형(번호이동, 기기변경, 신규가입 등)의 CSS 셀렉터
5. **retail_price_selector**: 출고가의 CSS 셀렉터
6. **discount_price_selector**: 할인가/최종가의 CSS 셀렉터
7. **plan_name_selector**: 요금제명의 CSS 셀렉터
8. **image_selector**: 제품 이미지의 CSS 셀렉터 (보통 "img")

**페이지네이션:**
9. **pagination_type**: "pagination" (버튼 있음) | "infinite_scroll" (무한 스크롤) | "none" (단일 페이지)
10. **next_button_selector**: 다음 페이지 버튼의 CSS 셀렉터 (pagination인 경우만)

# 응답 형식 (JSON)

```json
{{
  "product_card_selector": ".product-item",
  "product_name_selector": ".product-title",
  "detail_link_selector": "a.detail-link",
  "signup_type_selector": ".signup-type",
  "retail_price_selector": ".retail-price",
  "discount_price_selector": ".final-price",
  "plan_name_selector": ".plan-name",
  "image_selector": "img.product-image",
  "pagination_type": "pagination",
  "next_button_selector": ".pagination .next"
}}
```

# 분석 규칙

- CSS 셀렉터는 가능한 한 구체적이고 안정적으로 (id, class, data-* 속성 사용)
- 상대 셀렉터를 사용할 수 있음 (예: ".card > .title")
- 리스팅에 표시되지 않은 정보는 null 또는 빈 문자열("")로 설정
- 페이지네이션 버튼이 없으면 "pagination_type": "none" 또는 "infinite_scroll"
- 셀렉터가 여러 개 가능하면 가장 안정적인 것 선택

# HTML

{html_content}

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

