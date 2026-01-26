/**
 * Prompt Templates (Phase 2 & Phase 3)
 * LLM 분석용 프롬프트 템플릿
 */

// ============================================================================
// 리스팅 페이지 분석
// ============================================================================

export const LISTING_PAGE_ANALYSIS_SYSTEM = `
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
`;

export const LISTING_PAGE_ANALYSIS_PROMPT = `
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
5. **signup_type_selector**: 변경유형(번호이동, 기기변경, 신규가입 등)의 CSS 셀렉터
6. **retail_price_selector**: 출고가의 CSS 셀렉터
7. **discount_price_selector**: 할인가/최종가의 CSS 셀렉터

**지원금 정보 (매우 중요! 반드시 숫자를 포함한 요소를 선택!):**
8. **subsidy_type_selector**: 지원금 타입 레이블의 CSS 셀렉터
9. **public_subsidy_selector**: 공시지원금 금액이 들어있는 요소의 CSS 셀렉터
10. **additional_subsidy_selector**: 추가지원금 금액이 들어있는 요소의 CSS 셀렉터

**요금제 정보:**
11. **plan_name_selector**: 실제 통신 요금제명과 요금의 CSS 셀렉터

**기타 정보:**
12. **benefits_selector**: 혜택/사은품/프로모션의 CSS 셀렉터
13. **image_selector**: 제품 이미지의 CSS 셀렉터 (보통 "img")

**페이지네이션:**
14. **pagination_type**: "pagination" | "infinite_scroll" | "none"
15. **next_button_selector**: 다음 페이지 버튼의 CSS 셀렉터

# 응답 형식 (JSON)

\`\`\`json
{
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
}
\`\`\`

# 분석 규칙

- CSS 셀렉터는 가능한 한 구체적이고 안정적으로 (id, class, data-* 속성 사용)
- 상대 셀렉터를 사용할 수 있음 (예: ".card > .title")
- 리스팅에 표시되지 않은 정보는 null로 설정

# HTML

{html_content}

위 HTML을 분석하여 JSON만 출력하세요. 추가 설명 없이 JSON만 반환하세요.
`;

// ============================================================================
// 상세 페이지 옵션 분석
// ============================================================================

export const DETAIL_PAGE_OPTIONS_SYSTEM = `
당신은 휴대폰 구매 옵션 UI 분석 전문가입니다.
상세 페이지에서 통신사, 가입유형, 요금제, 할부, 용량, 색상 등의
선택 옵션을 찾고 추출하는 것이 당신의 역할입니다.
`;

export const DETAIL_PAGE_OPTIONS_PROMPT = `
다음 HTML은 휴대폰 상세 페이지입니다.
이 페이지에서 구매 옵션 UI를 분석하여 정보를 추출해주세요.

# 추출할 정보

1. **통신사 선택 UI** - 셀렉터, 타입, 옵션 목록 추출 방법
2. **가입유형 선택 UI** (번호이동/기기변경/신규가입)
3. **요금제 선택 UI**
4. **할부/약정 선택 UI**
5. **용량 선택 UI** (64GB, 128GB 등)
6. **색상 선택 UI**

# 응답 형식 (JSON)

\`\`\`json
{
  "carrier": {
    "selector": "#carrier-select",
    "type": "select",
    "option_selector": "option",
    "exists": true
  },
  "signup_type": {
    "selector": "input[name='signup']",
    "type": "radio",
    "option_selector": "input[name='signup']",
    "exists": true
  },
  "plan": {
    "selector": ".plan-list .plan-item",
    "type": "button",
    "option_selector": ".plan-list .plan-item",
    "exists": true
  },
  "installment": {
    "selector": "#installment",
    "type": "select",
    "option_selector": "option",
    "exists": true
  },
  "storage": {
    "selector": ".storage-btn",
    "type": "button",
    "option_selector": ".storage-btn",
    "exists": true
  },
  "color": {
    "selector": ".color-btn",
    "type": "button",
    "option_selector": ".color-btn",
    "exists": true
  }
}
\`\`\`

# 분석 규칙

- "exists"가 false면 해당 옵션이 페이지에 없는 것
- 타입을 정확히 판단 (select/radio/button/tab)
- 옵션이 없으면 exists: false

# HTML

{html_content}

위 HTML을 분석하여 JSON만 출력하세요.
`;

// ============================================================================
// 가격/정책 영역 분석
// ============================================================================

export const PRICING_AREA_SYSTEM = `
당신은 가격 정보 추출 전문가입니다.
휴대폰 구매 페이지에서 가격, 할부, 지원금 등의 정보를 찾아 추출합니다.
`;

export const PRICING_AREA_PROMPT = `
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

\`\`\`json
{
  "final_price": { "selector": ".final-price", "exists": true },
  "installment_principal": { "selector": ".installment-amount", "exists": true },
  "monthly_payment": { "selector": ".monthly-payment", "exists": true },
  "subsidy_official": { "selector": ".official-subsidy", "exists": true },
  "subsidy_additional": { "selector": ".additional-subsidy", "exists": true },
  "plan_condition": { "selector": ".plan-condition", "exists": true },
  "policy_text": { "selector": ".policy-notice", "exists": true }
}
\`\`\`

# HTML

{html_content}

위 HTML을 분석하여 JSON만 출력하세요.
`;

// ============================================================================
// Phase 3B: 화면 기반 정책 추출
// ============================================================================

export const SCREEN_PAGE_STRUCTURE_SYSTEM = `
당신은 휴대폰 구매 페이지 분석 전문가입니다.
상세 페이지의 HTML을 분석하여 다음을 식별해야 합니다:
1. 옵션 선택 UI (용량, 색상, 통신사, 가입유형, 요금제)
2. 가격 표시 영역 (출고가, 지원금, 할부금, 최종가)

정확한 CSS 셀렉터를 제공하여 Playwright로 요소를 찾을 수 있도록 해야 합니다.

🚨 중요: 실제 HTML 구조를 분석하여 존재하는 요소의 실제 셀렉터를 반환하세요.
`;

export const SCREEN_PAGE_STRUCTURE_PROMPT = `
주어진 HTML에서 실제로 존재하는 요소의 셀렉터를 찾으세요.

# HTML (실제 페이지)
{html}

# 분석 방법

1. **HTML을 직접 읽으세요**: class, id, name 속성을 확인
2. **실제 존재하는 요소만 반환**: 추측하지 마세요
3. **테스트 가능한 셀렉터**: document.querySelector()로 찾을 수 있어야 함

# 찾아야 할 요소

## 옵션 선택 UI

**용량 (storage)**: "256GB", "512GB", "1TB" 같은 텍스트가 있는 버튼/탭/select
**색상 (color)**: 색상 선택 UI
**통신사 (carrier)**: SKT, KT, LG U+ 등
**가입유형 (join_type)**: "번호이동", "기기변경", "신규가입"
**요금제 (plan)**: 요금제 선택 드롭다운이나 버튼

## 가격 표시 영역

- **출고가**: "출고가", "기기가격" 근처의 금액
- **공시지원금**: "공시지원금", "공통지원금" 근처의 금액
- **추가지원금**: "추가 지원금", "제휴할인" 근처의 금액
- **할부원금**: "할부원금" 근처의 금액
- **월 할부금**: "월 할부금", "월 납부" 근처의 금액

# 응답 형식 (JSON)

{
  "options": {
    "storage": { "type": "button", "selector": ".actual-storage-class" },
    "color": { "type": "button", "selector": ".actual-color-class" },
    "carrier": { "type": "button", "selector": ".actual-carrier-class" },
    "join_type": { "type": "button", "selector": ".actual-jointype-class" }
  },
  "pricing": {
    "retail_price_selector": ".actual-retail-class",
    "public_subsidy_selector": ".actual-subsidy-class",
    "additional_subsidy_selector": ".actual-additional-class",
    "installment_principal_selector": ".actual-installment-class",
    "monthly_payment_selector": ".actual-monthly-class"
  }
}

**JSON만 출력하세요. 예시 값을 그대로 반환하지 마세요!**
`;

export const SCREEN_EXTRACT_PRICING_SYSTEM = `
당신은 웹 페이지에서 가격 정보를 추출하는 전문가입니다.
HTML에서 휴대폰 구매 관련 가격 정보를 정확히 파싱해야 합니다.

🚨 핵심 규칙:
1. 반드시 HTML에서 실제 텍스트를 찾아야 합니다
2. 예시 값을 반환하지 마세요
3. 가격은 주로 <span class="unit-w">숫자</span> 패턴으로 표시됩니다
`;

export const SCREEN_EXTRACT_PRICING_PROMPT = `
주어진 HTML에서 **실제 가격 정보**를 추출하세요.

# HTML (실제 페이지)
{html}

# 추출 작업

HTML을 읽으면서 다음 키워드를 찾고, 그 근처의 **실제 숫자**를 추출하세요:

1. **출고가** → "출고가" 키워드 찾기 → 그 근처의 숫자
2. **공시지원금** → "공시지원금" 또는 "공시지원" 키워드 → 근처 숫자
3. **추가 지원금** → "추가 지원금" 또는 "추가지원금" 키워드 → 근처 숫자
4. **할부원금** → "할부원금" 키워드 → 근처 숫자
5. **월 할부금** → "월 할부금" 키워드 → 근처 숫자
6. **월 통신요금** → "월 통신요금" 키워드 → 근처 숫자
7. **요금제** → 요금제명 → 그 근처의 월요금

# 추출 결과 (JSON)

{
  "retail_price": 1980000,
  "public_subsidy": null,
  "additional_subsidy": -550000,
  "installment_principal": 1430000,
  "monthly_payment": 63314,
  "final_price": 145064,
  "plan_name": "5GX 프리미엄",
  "plan_monthly_fee": 109000
}

# 중요

- **콤마 제거**: "1,980,000" → 1980000
- **마이너스**: "-550,000" → -550000
- **정보 없으면**: null

**JSON만 출력하세요.**
`;

// ============================================================================
// 유틸리티 함수
// ============================================================================

export function formatListingAnalysisPrompt(htmlContent: string): string {
  return LISTING_PAGE_ANALYSIS_PROMPT.replace('{html_content}', htmlContent);
}

export function formatDetailOptionsPrompt(htmlContent: string): string {
  return DETAIL_PAGE_OPTIONS_PROMPT.replace('{html_content}', htmlContent);
}

export function formatPricingAreaPrompt(htmlContent: string): string {
  return PRICING_AREA_PROMPT.replace('{html_content}', htmlContent);
}

export function formatScreenPageStructurePrompt(html: string): string {
  const truncatedHtml = html.length > 20000 ? html.slice(0, 20000) + '\n\n...(나머지 HTML 생략)...' : html;
  return SCREEN_PAGE_STRUCTURE_PROMPT.replace('{html}', truncatedHtml);
}

export function formatScreenExtractPricingPrompt(html: string): string {
  const truncatedHtml = html.length > 15000 ? html.slice(0, 15000) + '\n\n...(나머지 HTML 생략)...' : html;
  return SCREEN_EXTRACT_PRICING_PROMPT.replace('{html}', truncatedHtml);
}
