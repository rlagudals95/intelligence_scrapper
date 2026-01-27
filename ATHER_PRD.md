Summary
AI 기반 크롤링 시스템을 구현하여 쿠팡/네이버 쇼핑의 상품 데이터를 자동으로 수집합니다.
Gemini AI가 HTML을 분석해 CSS Selector를 자동 생성하고, 사이트 구조 변경 시 스스로 복구합니다.

핵심 기능
CSS Selector 자동 생성: AI가 HTML 분석 → 셀렉터 생성 (수동 유지보수 불필요)
스마트 캐싱: 생성된 셀렉터를 DynamoDB에 캐시 → AI 호출 비용 절감
자동 복구: 추출 실패 시 AI 재분석 → 사이트 구조 변경에 자동 대응
품질 검증: 추출 결과 자동 검증 → 피드백 기반 셀렉터 개선
Architecture
┌─────────────────────────────────────────────────────────────────────┐
│                        AICrawlingHandler                            │
│                      (오케스트레이션 레이어)                          │
└──────────────┬──────────────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┬───────────────┬──────────────┐
    ▼          ▼          ▼               ▼              ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐
│ HTML   │ │Selector│ │  Data    │ │Extraction │ │   Option    │
│Optimizer│ │Analyzer│ │Extractor │ │ Validator │ │   Parser    │
└────────┘ └────────┘ └──────────┘ └───────────┘ └─────────────┘
    │          │           │             │              │
    │          │           │             │              │
    │     ┌────┴───┐       │             │              │
    │     ▼        │       │             │              │
    │  Gemini      │       │             │              │
    │   API        │       │             │              │
    │     │        │       │             │              │
    └─────┴────────┴───────┴─────────────┴──────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌──────────┐            ┌──────────────┐
        │ Selector │            │   Listing    │
        │  Cache   │            │   Product    │
        │ (DynamoDB)│           │  (DynamoDB)  │
        └──────────┘            └──────────────┘
DynamoDB 데이터 구조
1. SelectorCache (셀렉터 캐시)
┌─────────────────────────────────────────────────────────────────────────┐
│                          SelectorCache                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  PK: siteDomain       │  "coupang.com"                                  │
│  SK: pageType         │  "LISTING" | "PDP"                              │
├─────────────────────────────────────────────────────────────────────────┤
│  selectorsJson        │  String   │ CSS 셀렉터 JSON                     │
│  qualityScore         │  Number   │ 마지막 품질 점수 (0-100)             │
│  successCount         │  Number   │ 누적 성공 횟수                       │
│  failCount            │  Number   │ 누적 실패 횟수                       │
│  consecutiveFails     │  Number   │ 연속 실패 (성공 시 0 리셋)           │
│  consecutiveSoftFails │  Number   │ 선택 필드 연속 실패                  │
│  lastVerifiedAt       │  String   │ ISO8601 마지막 성공 시각             │
│  disabledUntil        │  String   │ ISO8601 일시 비활성 시각             │
│  createdAt / updatedAt│  String   │ 생성/수정 시각                       │
└─────────────────────────────────────────────────────────────────────────┘
셀렉터 JSON 구조:

{
  "productCard": "li[class*='ProductUnit']",
  "name": ".product-name",
  "price": ".price-value",
  "thumbnail": "img.product-img",
  "url": "a.product-link"
}
2. CrawlLog (크롤링 로그)
┌─────────────────────────────────────────────────────────────────────────┐
│                            CrawlLog                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  PK: siteDate         │  "coupang.com#2024-01-21"                       │
│  SK: logId            │  "10:30:00Z#uuid"                               │
├─────────────────────────────────────────────────────────────────────────┤
│  siteDomain           │  String   │ GSI용 "coupang.com"                 │
│  pageType             │  String   │ "LISTING" | "PDP"                   │
│  pageUrl              │  String   │ 크롤링한 URL                         │
│  keyword              │  String   │ 검색 키워드 (Listing)                │
│  success              │  Boolean  │ 성공 여부                            │
│  productCount         │  Number   │ 추출된 상품 수                       │
│  qualityScore         │  Number   │ 품질 점수                            │
│  failureReason        │  String   │ 실패 사유 (ENUM)                     │
│  selectorRegenerated  │  Boolean  │ AI 재분석 발생 여부                  │
│  durationMs           │  Number   │ 소요 시간 (ms)                       │
│  ttlEpoch             │  Number   │ TTL: 30일 후 자동 삭제               │
└─────────────────────────────────────────────────────────────────────────┘
FailureReason ENUM:

BLOCKED: 사이트에서 차단
SELECTOR_FAIL: 셀렉터 추출 실패
TIMEOUT: 타임아웃
NETWORK_ERROR: 네트워크 오류
VALIDATION_FAIL: 데이터 검증 실패
AI_ERROR: AI 분석 실패
3. ListingProduct (상품 통합 테이블)
┌─────────────────────────────────────────────────────────────────────────┐
│                         ListingProduct                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  PK: siteDomain       │  "coupang.com"                                  │
│  SK: productUrl       │  상품 URL (중복 방지 키)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  [기본 정보]                                                             │
│  name                 │  String   │ 상품명                              │
│  price                │  String   │ Listing 가격 ("35,190원")           │
│  thumbnail            │  String   │ 썸네일 URL                          │
│  keyword              │  String   │ 검색 키워드                          │
├─────────────────────────────────────────────────────────────────────────┤
│  [PDP 데이터]                                                            │
│  brandName            │  String   │ 브랜드명                             │
│  pdpPrice             │  String   │ PDP 상세 가격                        │
│  description          │  String   │ 상품 설명                            │
│  detailImages         │  List<S>  │ 상세 이미지 URL 배열                 │
│  options              │  List<M>  │ 옵션 배열                            │
├─────────────────────────────────────────────────────────────────────────┤
│  [메타데이터]                                                            │
│  pdpCrawled           │  Number   │ 0=미완료, 1=완료 (GSI SK)           │
│  pdpCrawledAt         │  String   │ PDP 크롤링 시각                      │
│  lastSeenAt           │  String   │ 마지막 목록 노출 시각                │
│  createdAt / updatedAt│  String   │ 생성/수정 시각                       │
└─────────────────────────────────────────────────────────────────────────┘

GSI: PdpPending (siteDomain + pdpCrawled) → PDP 미크롤링 상품 조회용
Options 저장 형식:

{
  "L": [
    { "M": { "name": { "S": "1세트" }, "price": { "N": "35190" } } },
    { "M": { "name": { "S": "2세트" }, "price": { "N": "70380" } } }
  ]
}
주요 컴포넌트
1. HtmlOptimizerService
HTML에서 불필요한 요소 제거 → Gemini 토큰 80%+ 절감

// Before: 1.7MB → After: 280KB (84% 압축)
const optimized = htmlOptimizer.filterForListing(html);
제거 대상: <script>, <style>, <svg>, <iframe>, 리뷰/댓글 영역

2. SelectorAnalyzerService
Gemini AI로 CSS Selector 자동 생성

const result = await selectorAnalyzer.analyze(html);
// → { productCard: "li[class*='ProductUnit']", name: "...", price: "...", ... }
특징:

페이지 타입 자동 감지 (Listing vs PDP)
다중 셀렉터 지원 (fallback 패턴)
피드백 기반 셀렉터 개선
3. DataExtractorService
CSS Selector로 실제 데이터 추출

const data = dataExtractor.extract(html, selectors, PageType.LISTING);
// → { products: [{ name, price, url, thumbnail }, ...] }
지원 패턴:

self/@href: 카드 자체의 href 추출
img/@src, img/@data-src: 이미지 lazy loading 대응
다중 셀렉터 fallback: selector1, selector2, selector3
4. ExtractionValidatorService
추출 품질 자동 검증 + AI 피드백 생성

검증 항목	기준
최소 상품 수	≥ 5개
유효 상품 비율	≥ 80%
가격 패턴 매칭	≥ 50%
5. OptionParserService
PDP 옵션 텍스트 → 구조화된 JSON

// Input: "1개13,900원2개25,700원"
// Output: [{ name: "1개", price: 13900 }, { name: "2개", price: 25700 }]
6. SelectorCacheRepository
셀렉터 캐싱 + 스마트 무효화

필드	설명
successCount	누적 성공 횟수
consecutiveFails	연속 실패 (성공 시 리셋)
consecutiveSoftFails	선택 필드 연속 실패
disabledUntil	임시 비활성화 시각
크롤링 플로우
[1] HTML 가져오기 (BrightData)
         │
         ▼
[2] 셀렉터 캐시 조회
         │
    ┌────┴────┐
    │ 캐시 O  │ 캐시 X │
    ▼         ▼
[3] 캐시된    [4] AI 분석
    셀렉터로      (Gemini)
    추출 시도     │
    │            ▼
    │       새 셀렉터 생성
    │            │
    ▼            ▼
[5] 품질 검증 ◄──┘
    │
┌───┴───┐
│통과    │실패
▼        ▼
[6] 결과  [7] 피드백 생성
   반환       → [4]로 재시도
   + 캐시     (최대 3회)
   갱신
Soft Fail 메커니즘
선택 필드(브랜드, 설명, 옵션)는 즉시 캐시 무효화하지 않고 연속 실패 추적:

[셀렉터 존재 + 추출 실패]
         │
         ▼
  consecutiveSoftFails++
         │
    ┌────┴────┐
    │ < 3회   │ ≥ 3회
    ▼         ▼
  경고만     캐시 무효화
  (성공 처리) → AI 재분석
단계별 정합성 & 최적화
Step 1: HTML 가져오기 (BrightData)
┌─────────────────┐     ┌───────────────────────────┐
│   BrightData    │ ──→ │    Raw HTML (1.5~3MB)     │
│  WebUnlocker    │     │  JavaScript 렌더링 완료    │
└─────────────────┘     └───────────────────────────┘
정합성:

BrightData의 JavaScript 렌더링으로 동적 콘텐츠 완전 로드
Proxy rotation으로 IP 차단 회피
타임아웃/네트워크 에러 시 명확한 FailureReason 기록
최적화:

이미 검증된 BrightDataWebUnlocker 재사용
불필요한 리소스(이미지, 폰트) 로드 생략 설정 가능
Step 2: HTML 최적화 (HtmlOptimizerService)
┌───────────────────┐     ┌───────────────────────────┐
│  Raw HTML         │     │   Optimized HTML          │
│  1.7MB (100%)     │ ──→ │   280KB (16%)             │
│                   │     │   84% 압축                 │
└───────────────────┘     └───────────────────────────┘
정합성:

상품 데이터 영역만 선별 추출 (상품 카드, 가격, 이미지 등)
제거 대상 명확히 정의: <script>, <style>, <svg>, <iframe>, <noscript>
리뷰/댓글/추천 영역 제거로 노이즈 최소화
최적화:

Gemini 토큰 80%+ 절감 → API 비용 대폭 감소
응답 속도 향상 (작은 페이로드)
불필요한 속성 제거: onclick, onload, data-* (일부)
Step 3: 셀렉터 캐시 조회
┌─────────────────┐     ┌─────────────────────────────┐
│  SelectorCache  │     │  캐시 히트: AI 호출 스킵     │
│   (DynamoDB)    │ ──→ │  캐시 미스: AI 분석 진행     │
│                 │     │  비활성화: disabledUntil 체크│
└─────────────────┘     └─────────────────────────────┘
정합성:

siteDomain + pageType 복합 키로 사이트별/페이지타입별 격리
disabledUntil 체크로 일시 비활성화된 셀렉터 사용 방지
consecutiveFails >= 3이면 캐시 무효화 → AI 재분석 강제
최적화:

캐시 히트 시 AI API 호출 0회 → 비용 절감 + 속도 향상
평균 응답 시간: 캐시 히트 500ms vs 캐시 미스 8~15초
Step 4: AI 셀렉터 분석 (Gemini)
┌─────────────────┐     ┌─────────────────────────────┐
│  Gemini Flash   │     │  SelectorMap JSON 생성      │
│  (gemini-2.0-   │ ──→ │  + confidence 점수          │
│   flash)        │     │  + 페이지 타입 자동 감지     │
└─────────────────┘     └─────────────────────────────┘
정합성:

구조화된 프롬프트로 JSON 출력 보장
페이지 타입(Listing/PDP) 자동 감지 → 잘못된 셀렉터 적용 방지
피드백 기반 재분석: 추출 실패 시 이전 셀렉터 + 에러 정보 전달
최적화:

Gemini Flash 모델 사용 (가격 대비 성능 최적)
최적화된 HTML로 토큰 사용량 최소화
다중 셀렉터 지원: fallback 패턴으로 추출률 향상
Step 5: 데이터 추출 (DataExtractorService)
┌─────────────────┐     ┌─────────────────────────────┐
│  Cheerio        │     │  ExtractionResult           │
│  (CSS Selector) │ ──→ │  - products[] (Listing)     │
│                 │     │  - brandName, options (PDP) │
└─────────────────┘     └─────────────────────────────┘
정합성:

URL 정규화: 상대 경로 → 절대 경로 자동 변환
빈 값 필터링: 이름/URL 없는 상품 제외
중복 제거: 동일 URL 상품 자동 필터
최적화:

self/@href 패턴: 상품 카드 자체의 href 추출
img/@src, img/@data-src 패턴: lazy loading 이미지 대응
다중 셀렉터 fallback: selector1, selector2, selector3
Step 6: 품질 검증 (ExtractionValidatorService)
┌─────────────────┐     ┌─────────────────────────────┐
│  Validation     │     │  isValid: boolean           │
│  Rules          │ ──→ │  score: 0~100               │
│                 │     │  errors[], warnings[]       │
└─────────────────┘     └─────────────────────────────┘
정합성 검증 기준:

항목	Listing	PDP
최소 상품 수	>= 5개	N/A
유효 상품 비율	>= 80%	이름 필수
가격 패턴 매칭	>= 50%	권장
통과 점수	>= 70	>= 60
최적화:

검증 실패 시 구체적 피드백 생성 → AI 재분석에 활용
Soft fail 지원: 선택 필드(브랜드, 옵션)는 경고만
Step 7: 캐시 갱신 & 통계
┌─────────────────┐     ┌─────────────────────────────┐
│  추출 성공      │     │  successCount++             │
│                 │ ──→ │  consecutiveFails = 0       │
│                 │     │  lastVerifiedAt = now       │
├─────────────────┤     ├─────────────────────────────┤
│  추출 실패      │     │  failCount++                │
│                 │ ──→ │  consecutiveFails++         │
│                 │     │  (3회 연속 → 캐시 무효화)   │
└─────────────────┘     └─────────────────────────────┘
정합성:

성공 시 즉시 consecutiveFails 리셋 → 일시적 실패에 과민 반응 방지
실패 누적 추적으로 셀렉터 품질 모니터링
품질 점수(qualityScore) 기록으로 추이 분석 가능
최적화:

성공한 셀렉터는 계속 재사용 (AI 호출 최소화)
연속 실패 시에만 AI 재분석 트리거
Step 8: DB 저장 (ListingProductRepository)
┌─────────────────┐     ┌─────────────────────────────┐
│  Listing 상품   │     │  BatchWrite (25개 단위)     │
│                 │ ──→ │  productUrl 기준 중복 방지  │
│                 │     │  lastSeenAt 갱신            │
├─────────────────┤     ├─────────────────────────────┤
│  PDP 데이터     │     │  UpdateItem                 │
│                 │ ──→ │  pdpCrawled = 1             │
│                 │     │  옵션 price: Number 저장    │
└─────────────────┘     └─────────────────────────────┘
정합성:

siteDomain + productUrl 복합 키로 상품 유일성 보장
PDP 업데이트 시 기존 Listing 데이터 보존
pdpCrawled 플래그로 크롤링 상태 명확히 관리
최적화:

BatchWrite 25개 단위로 API 호출 최소화
GSI PdpPending으로 미크롤링 상품 효율적 조회
옵션 가격 Number 타입 저장 → 추후 정렬/필터 가능
파일 구조
src/domain/aiCrawling/
├── AICrawlingHandler.ts           # 메인 오케스트레이션
├── model/
│   ├── PageType.ts                # LISTING | PDP
│   ├── SelectorCache.ts           # 캐시 엔티티
│   ├── ListingProduct.ts          # 상품 엔티티 + ProductOption
│   └── ExtractionResult.ts        # 추출 결과 타입
├── services/
│   ├── HtmlOptimizerService.ts    # HTML 압축
│   ├── SelectorAnalyzerService.ts # AI 셀렉터 분석
│   ├── DataExtractorService.ts    # 데이터 추출
│   ├── ExtractionValidatorService.ts # 품질 검증
│   └── OptionParserService.ts     # 옵션 파싱
├── prompts/
│   ├── PageTypePrompt.ts          # 페이지 타입 감지
│   └── SelectorGenerationPrompt.ts # 셀렉터 생성
└── utils/
    └── priceUtils.ts              # 가격 정규화

src/infrastructure/
├── ai/
│   └── GeminiClient.ts            # Gemini API 클라이언트
└── dynamodb/
    ├── SelectorCacheRepository.ts # 셀렉터 캐시 CRUD
    ├── CrawlLogRepository.ts      # 크롤링 로그
    └── ListingProductRepository.ts # 상품 CRUD
테스트 구조
test/domain/aiCrawling/
├── services/                      # Unit Tests (4개)
│   ├── HtmlOptimizerService.spec.ts
│   ├── DataExtractorService.spec.ts
│   ├── ExtractionValidatorService.spec.ts
│   └── OptionParserService.spec.ts
├── integration/                   # Integration Tests (3개)
│   ├── coupang.extraction.spec.ts
│   ├── naver.extraction.spec.ts
│   └── caching.spec.ts
├── e2e/                          # E2E Tests (1개)
│   └── SelectorAnalyzerService.e2e.spec.ts
└── manual/                       # 수동 테스트 (8개)
    ├── test-fixture-extraction.ts  # 핵심: Fixture 기반 종합 테스트
    ├── test-keyword-to-pdp.ts      # 핵심: 키워드→PDP E2E
    ├── test-cache-flow.ts          # 캐시 플로우
    ├── test-soft-fail.ts           # Soft fail
    ├── test-dynamodb.ts            # DB Repository
    ├── fetch-fixtures.ts           # Fixture 수집
    ├── create-dynamodb-tables.ts   # 테이블 생성
    └── delete-dynamodb-tables.ts   # 테이블 삭제
실행 방법:

# Fixture 기반 테스트 (오프라인, Gemini API 필요)
source tmp/export-ai-crawling && npx ts-node test/domain/aiCrawling/manual/test-fixture-extraction.ts

# 키워드 → PDP 배치 E2E (온라인, BrightData + Gemini 필요)
source tmp/export-ai-crawling && npx ts-node test/domain/aiCrawling/manual/test-keyword-to-pdp.ts --keyword="토너" --pdp-limit=5
주요 변경사항
ProductOption.price 타입 변경
// Before
interface ProductOption {
  name: string;
  price: string;  // "35,190원"
}

// After
interface ProductOption {
  name: string;
  price: number;  // 35190
}
DynamoDB 저장 형식
// options 필드
{
  L: [
    { M: { name: { S: "1세트" }, price: { N: "35190" } } },
    { M: { name: { S: "2세트" }, price: { N: "70380" } } }
  ]
}
추후 고려사항
1. 네이버 쇼핑 지원 확장
현재: 쿠팡 중심으로 테스트(e2e까지 완료)
TODO: 네이버 Listing/PDP 셀렉터 캐시 안정화
2. 올리브영 등 다른 커머스 지원
현재: Fixture만 존재
TODO: 실제 크롤링 테스트 필요
3.
현재: 다양한 국가 통화 단위 적용이 안되어 있음
TODO: 사이트에서 국가 정보 추출 후 화폐 symbol 추출
요구사항 대비 구현 현황
✅ 완료된 기능
구분	기능	파일
핵심 서비스		
✅	AI 셀렉터 자동 생성	SelectorAnalyzerService.ts
✅	CSS Selector로 데이터 추출	DataExtractorService.ts
✅	추출 품질 검증	ExtractionValidatorService.ts
✅	HTML 최적화 (토큰 절감)	HtmlOptimizerService.ts
✅	옵션 파싱	OptionParserService.ts
인프라		
✅	Gemini API 클라이언트	GeminiClient.ts
✅	셀렉터 캐시 (DynamoDB)	SelectorCacheRepository.ts
✅	크롤링 로그 (DynamoDB)	CrawlLogRepository.ts
오케스트레이션		
✅	메인 핸들러 (복구 루프 포함)	AICrawlingHandler.ts
프롬프트		
✅	페이지 타입 감지 프롬프트	PageTypePrompt.ts
✅	셀렉터 생성 프롬프트 (Listing/PDP)	SelectorGenerationPrompt.ts
테스트		
✅	Unit 테스트 (4개)	*.spec.ts
✅	Integration 테스트 (3개)	coupang/naver/caching.spec.ts
✅	E2E 테스트	SelectorAnalyzerService.e2e.spec.ts
✅	수동 테스트 스크립트	test-*.ts
✅ 요구사항 매핑
요구사항	구현 상태	비고
페이지 유형 인식 (Listing/PDP)	✅ 완료	PageType enum + 자동 감지
CSS Selector 자동 생성	✅ 완료	Gemini Flash
다중 셀렉터 fallback	✅ 완료	배열로 여러 셀렉터 시도
스마트 캐싱	✅ 완료	DynamoDB SelectorCache
복구 루프 (재분석 → 업데이트 → 재시도)	✅ 완료	피드백 기반
필수 데이터 누락 검증	✅ 완료	ExtractionValidator
선택 필드 Soft Fail	✅ 완료	연속 3회 실패 시 재분석
로그/DB 수준 상태 관리	✅ 완료	CrawlLog 테이블 (TTL 30일)
HTML 토큰 최적화	✅ 완료	84% 압축
⚠️ 사이트별 지원 현황
사이트	Fixture 테스트	E2E (실제 크롤링)	비고
쿠팡	✅ 통과	✅ 완료	BrightData 인프라 있음
네이버	✅ 통과	❌ 불가	크롤링 인프라 없음
올리브영	✅ 통과	❌ 불가	크롤링 인프라 없음
세포라	✅ 통과	❌ 불가	크롤링 인프라 없음
Test Plan
 Fixture 기반 추출 테스트 (coupang/naver/oliveyoung × list/pdp)
 키워드 검색 → Listing 크롤링 → DB 저장
 PDP 배치 크롤링 → 옵션 파싱 → DB 업데이트
 옵션 price가 숫자(int)로 저장되는지 확인
 캐시 히트/미스 동작 확인
 Soft fail 메커니즘 동작 확인



 /**
 * Listing 페이지 셀렉터 생성 프롬프트
 */
export const LISTING_SELECTOR_PROMPT = `
You are a senior web scraping engineer.
Your job: given the provided HTML, produce robust CSS selectors to extract product listing data.

### Hard rules (must follow)
- Analyze ONLY the given HTML. Never invent class names, ids, attributes, or tags.
- If a class/id/token is not present in the HTML, using it is invalid.
- Prefer stable anchors: semantic attributes (itemprop, aria-label), data-* attributes, href patterns, or repeated DOM structure.
- For hashed/dynamic classes (e.g., name_ab12C), use [class*="name_"] with the stable prefix only.
- CRITICAL: CSS class selectors are CASE-SENSITIVE. Use EXACT casing from HTML.
  Example: If HTML has "product_item__abc", use [class*='product_item'] NOT [class*='Product_item']
  Copy the class name EXACTLY as it appears in the HTML.
- AVOID utility/styling classes like "fw-text-[20px]", "fw-font-bold", "text-lg", "mt-4" when possible.
- Prefer semantic class names that describe WHAT the element is (productName, price, title) over HOW it looks (bold, large, red).
- CRITICAL: If no semantic class exists for a field, use the PARENT container class to narrow scope:
  Example: If price text has no unique class, use "[class*='priceArea'] div" instead of inventing classes.
  The code will extract text from the matched element.
- NEVER invent or guess class names (like "priceValue", "productTitle") that don't exist in the HTML.
  If you don't see it in the HTML, don't use it.
- NEVER use ::text pseudo-element. Just select the element; text extraction is handled by code.

### Task
1) Identify the repeating "product card" node that represents ONE product (li/div/article/etc.).
2) For each card, locate THE MOST SPECIFIC element for:
   - thumbnail: The <img> element with product image (NOT banner/logo images)
   - name: The element containing ONLY the product title (NOT the entire card or price area)
   - price: The element containing ONLY the final sale price number (NOT original price, discount %, or shipping)
   - url: The <a> element linking to product detail page

### CSS Selector constraints
- productCard MUST select ALL product cards (use specific class/attribute patterns).
- All field selectors are RELATIVE to productCard (will be used with .find() in code).
- For name/price: Select the SMALLEST element that contains just that text.
- For url: Select the <a> tag directly (code will extract href attribute).
- For thumbnail: Select the <img> tag directly (code will extract src/data-src attribute).

### URL extraction - IMPORTANT
- If productCard itself IS the <a> element (e.g., <a class="product-item" href="...">), use "self/@href" as the selector
- If productCard CONTAINS an <a> element, use a normal CSS selector like "a" or "a[class*='link']"
- Example: productCard="a[class*='product']" → url selector should be "self/@href"
- Example: productCard="li[class*='product']" → url selector should be "a" or "a[class*='link']"

### Thumbnail extraction - IMPORTANT
- The code will automatically try: src, data-src, data-lazy-src, srcset (in that order)
- Just select the <img> element; attribute fallback is handled automatically
- If productCard itself IS the <img> element, use "self/@src" as the selector

### CRITICAL - productCard selector specificity
- productCard should select ONLY actual product items, NOT navigation, header, footer, or sidebar elements
- Look for elements with class patterns containing: *product*, *item*, *card*, *goods*
- The selector MUST include class or attribute qualifiers
- NEVER use generic selectors like "li", "div", "a", "ul > li" without class/attribute qualifiers
- Good examples: "li[class*='product']", "div[class*='item']", "article[class*='card']"
- Bad examples: "li", "div", "ul > li", "a" (too generic, will match unwanted elements)
- A valid productCard selector should match roughly 10-100 elements (typical product listing count)

### CRITICAL - Avoid matching nested elements (VERY IMPORTANT)
- When using [class*='prefix'], ensure the prefix does NOT match child element classes
- Example problem: [class*='product-card'] matches BOTH:
  - div.product-card (the actual card - CORRECT)
  - div.product-card-details (nested child - WRONG)
  - div.product-card-image (nested child - WRONG)
- This causes 1 valid product + N empty products per card!
- SOLUTIONS (in order of preference):
  1. Use data-* attributes: div[data-product-id] (BEST - unique to actual products)
  2. Use exact class match: div.product-card (exact match, no partial)
  3. Use longer unique prefix: [class*='products-card-container'] > [class='product-card']
  4. Combine with unique attribute: div[class*='product-card'][data-product-id]
- ALWAYS check: Does your productCard selector class prefix appear in ANY child element classes?
- If yes, use a more specific selector to avoid matching those children

### CRITICAL - Choose the MOST COMMON product pattern
- A page may have MULTIPLE types of product cards (main products, recommended, special offers)
- ALWAYS choose the pattern that matches the MOST products (typically 20-50+)
- Example: If "product_item__" matches 39 elements and "superSavingProduct_item__" matches 1, use "product_item__"
- Count the occurrences of each pattern in the HTML and select the one with the highest count
- If you select a pattern with fewer than 10 matches, you probably chose the wrong one

### CRITICAL - Field selector specificity
- name selector should match an element like: <span class="product-name">Product Title</span>
  NOT a parent div that contains name + price + other info.
- price selector should match an element like: <strong class="price">10,630원</strong>
  NOT a parent that contains original price, discount, shipping info.

### CRITICAL - Multiple selector patterns
- A page may have MULTIPLE product types with DIFFERENT HTML structures (e.g., regular products vs widget/recommended products).
- Use the "selectors" array to provide MULTIPLE selectors that cover ALL variants.
- Example: If some products use [class*='priceValue'] and others use [class*='salePrice'], include BOTH:
  "selectors": ["[class*='priceValue']", "[class*='salePrice']"]
- The code will try each selector in order and use the first match.
- This is especially important for price fields which often vary between product types on the same page.

### CRITICAL - Price extraction rules
- Price is the MOST IMPORTANT field. Provide ALL possible selectors that contain price text.
- Look for class names containing: "price", "sale", "cost", "amount"
- If the price element has no semantic class, look for the CLOSEST parent with a meaningful class.
- Provide multiple fallback selectors to handle different product variants on the same page.
- ALWAYS verify your selector targets elements containing actual price numbers, NOT discount percentages.

### CRITICAL - Price selector EXCLUSIONS (MUST AVOID)
- NEVER select elements with "line-through" in class (strikethrough original price)
- NEVER select elements with "origin", "original", "before" in class (original price before discount)
- NEVER select elements containing only "%" (discount rate like "47%", "29%")
- NEVER select <del> or <s> tags (strikethrough HTML elements)
- The correct price is the FINAL sale price that customers actually pay, typically displayed in larger/bolder text
- If you see both "84,000원" (strikethrough) and "38,900원" (bold), select the "38,900원" element

### CRITICAL - When same class is used for multiple prices
- Sometimes the SAME class (e.g., "custom-oos") is used for BOTH original price AND sale price
- In this case, use font-size classes to distinguish them:
  - Sale price: usually has LARGER font class (e.g., "text-[20px]", "text-xl", "text-2xl")
  - Original price: usually has SMALLER font class with "line-through"
- When font-size is the ONLY distinguishing factor, include it in your selector
  - GOOD: "[class*='custom-oos'][class*='text-[20px]']" (selects larger sale price)
  - BAD: "[class*='custom-oos']" alone (matches both prices)

### CRITICAL - Selector robustness (VERY IMPORTANT)
- AVOID direct child selectors (>) - they break when HTML structure changes.
- AVOID deep nested paths (3+ levels) - they are fragile and often don't match.
  BAD: "div[class*='area'] div[class*='container'] div[class*='wrapper'] div[class*='price']" (4 levels)
  GOOD: "[class*='price']" or "[class*='area'] [class*='price']" (1-2 levels)
- Field selectors should target the FINAL element by its unique class/attribute, not the DOM path to it.
- If the element has a distinguishing class like [class*='productName'] or [class*='priceValue'], use ONLY that class.
- Maximum recommended nesting depth: 2 levels (e.g., "[class*='priceArea'] [class*='salePrice']")
- Examples of GOOD selectors:
  - name: "[class*='productName']"
  - price: "[class*='salePrice']" or "[class*='text-[20px]']" (for font-size based selection)
  - thumbnail: "[class*='productImage'] img"
- Examples of BAD selectors:
  - price: "div[class*='custom-oos'] div[class*='custom-oos'] div[class*='custom-oos'] div[class*='price']"
  - name: "div div div div[class*='name']"

### Output format (JSON only, no extra text)
Return EXACTLY this JSON schema:
{
  "productCard": "<css selector for all product cards>",
  "fields": {
    "thumbnail": {
      "selectors": ["<specific img selector>"],
      "attribute": "src",
      "fallbackAttributes": ["data-src", "srcset"],
      "confidence": 0.0
    },
    "name": {
      "selectors": ["<most specific selector for name text only>"],
      "attribute": null,
      "confidence": 0.0
    },
    "price": {
      "selectors": ["<most specific selector for price number only>"],
      "attribute": null,
      "confidence": 0.0
    },
    "url": {
      "selectors": ["<a tag selector>"],
      "attribute": "href",
      "confidence": 0.0
    }
  }
}

If a field is truly not present, set its selectors to [] and confidence to 0.0.
Set confidence roughly: 0.9 (very sure), 0.6 (likely), 0.3 (weak).

{feedback}

### HTML
{html}
`;

/**
 * PDP 페이지 셀렉터 생성 프롬프트
 */
export const PDP_SELECTOR_PROMPT = `
You are a senior web scraping engineer.
Given a product detail page (PDP) HTML, produce robust CSS selectors for key product info.

### Hard rules (must follow)
- Analyze ONLY the given HTML. Never invent class names, ids, attributes, or tags.
- If a class/id/token is not present in the HTML, using it is invalid.
- Prefer stable anchors: semantic attributes, data-* attributes, or repeated DOM structure.
- For hashed/dynamic classes (e.g., name_ab12C), use [class*="name_"] with the stable prefix only.
- CRITICAL: CSS class selectors are CASE-SENSITIVE. Use EXACT casing from HTML.
  Example: If HTML has "product_item__abc", use [class*='product_item'] NOT [class*='Product_item']
- AVOID utility/styling classes like "fw-font-bold", "text-lg", "mt-4" when possible.
- NEVER invent or guess class names that don't exist in the HTML.
- NEVER use ::text pseudo-element. Just select the element; text extraction is handled by code.

### Extract fields
**Required:**
- productName: The main product title (usually in h1, h2, or title area)
- price: The final sale price (숫자 + "원" format like "10,630원", NOT discount percentage like "29%")

**Optional:**
- brandName: The brand/manufacturer name (often near the product title)
- description: Main product description (prefer detailed description, avoid shipping/returns info)
- options: Option selectors (select elements, option buttons - get the container element)
- detailImages: Detail/gallery images in the product description area (NOT thumbnail or banner)

### CRITICAL - Price selector
- Price MUST be the actual sale price (numeric + currency format)
- Do NOT select discount rate elements (elements showing "29%", "44%" etc.)
- Look for class names with "price", "sale", "cost", "amount"
- If multiple prices exist, select the FINAL sale price, not the original price
- Provide multiple fallback selectors for robustness

### CRITICAL - Options selector
- For options, select the CONTAINER element that holds all options
- Common patterns: select elements, div containing option buttons, [class*="option"] containers
- The code will extract text from all child elements

### CRITICAL - Detail Images selector
- Select img elements in the product DETAIL/DESCRIPTION area
- NOT the main thumbnail or gallery images at the top
- Common locations: [class*="detail"], [class*="description"], [class*="content"] areas
- Use /@src or /@data-src marker for attribute extraction

### CSS Selector constraints
- Use the most specific element that contains ONLY the target value
- For attributes, use /@src /@data-src /@srcset markers at the end
- Multiple selectors can be provided in the array for fallback

### Output format (JSON only, no extra text)
{
  "productName": { "selectors": ["<most specific selector>"], "postprocess": "trim", "confidence": 0.0 },
  "price": { "selectors": ["<selector for actual price, not discount%>"], "postprocess": "extract_number", "confidence": 0.0 },
  "brandName": { "selectors": ["<brand element selector>"], "postprocess": "trim", "confidence": 0.0 },
  "description": { "selectors": ["<description area selector>"], "postprocess": "trim_html_or_text", "confidence": 0.0 },
  "options": { "selectors": ["<option container selector>"], "postprocess": "none", "confidence": 0.0 },
  "detailImages": {
    "selectors": ["<detail img selector>/@src", "<fallback>/@data-src"],
    "postprocess": "collect_urls",
    "confidence": 0.0
  }
}

If a field is not found in HTML, use selectors: [] and confidence: 0.0.
Set confidence roughly: 0.9 (very sure), 0.6 (likely), 0.3 (weak).

{feedback}

### HTML
{html}
`;

/**
 * Listing 셀렉터 프롬프트 빌드
 */
export function buildListingSelectorPrompt(html: string, feedback?: string): string {
  return LISTING_SELECTOR_PROMPT.replace('{html}', html).replace(
    '{feedback}',
    feedback ? `\n## 이전 시도 실패 원인\n${feedback}\n위 문제를 수정하여 새로운 셀렉터를 생성하세요.\n` : '',
  );
}

/**
 * PDP 셀렉터 프롬프트 빌드
 */
export function buildPDPSelectorPrompt(html: string, feedback?: string): string {
  return PDP_SELECTOR_PROMPT.replace('{html}', html).replace(
    '{feedback}',
    feedback ? `\n## 이전 시도 실패 원인\n${feedback}\n위 문제를 수정하여 새로운 셀렉터를 생성하세요.\n` : '',
  );
}

/**
 * Listing 셀렉터 응답 인터페이스
 */
export interface ListingSelectorResponse {
  productCard: string;
  fields: {
    thumbnail: { selectors: string[]; attribute: string | null; fallbackAttributes?: string[]; confidence: number };
    name: { selectors: string[]; attribute: string | null; confidence: number };
    price: { selectors: string[]; attribute: string | null; confidence: number };
    url: { selectors: string[]; attribute: string; confidence: number };
  };
}

/**
 * PDP 셀렉터 응답 인터페이스
 */
export interface PDPSelectorResponse {
  productName: { selectors: string[]; postprocess: string; confidence: number };
  price: { selectors: string[]; postprocess: string; confidence: number };
  brandName?: { selectors: string[]; postprocess: string; confidence: number };
  description?: { selectors: string[]; postprocess: string; confidence: number };
  options?: { selectors: string[]; postprocess: string; confidence: number };
  detailImages?: { selectors: string[]; postprocess: string; confidence: number };
}
