# 구현 계획 (PLAN)

## 🎯 프로젝트 개요

**LLM 기반 지능형 휴대폰 기종/정책 데이터 수집 에이전트**

- **목표**: 리스팅 페이지에서 상세 URL 전수 수집 → 각 상세페이지에서 옵션 카탈로그 100% 수집 → 가격/정책 영향 옵션 조합 순회 (가지치기 포함)
- **핵심 차별점**: LLM이 페이지 맥락을 읽고 판단하여 사이트별 구조 차이를 자동으로 처리하는 지능형 스크래퍼

대상 사이트

하이폰
https://hi-phone.kr/index.php?channel=list&cate=103001000000 (삼성전자)
https://hi-phone.kr/index.php?channel=list&cate=103002000000 (아이폰)

띵폰
https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90 (삼성전자)
https://ddingphone.com/list?sst=c&cid=APPLE (아이폰)


딜리버리폰
https://www.deliveryphone.co.kr/phone/list/2 (삼성전자)
https://www.deliveryphone.co.kr/phone/list/3 (아이폰)


성지폰
https://sungjiphone.com/phone/list/2 (삼성전자)
https://sungjiphone.com/phone/list/3 (아이폰)

폰슐랭
https://phonechelin.shop/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90 (삼성전자)
https://phonechelin.shop/mshop/list?sst=c&cid=APPLE (아이폰)

엘지티샵
https://lgtshop.co.kr/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90 (삼성전자)
https://lgtshop.co.kr/mshop/list?sst=c&cid=APPLE (아이폰)

유플러스투게더몰
https://uplustogethermall.com/section/samsung (삼성전자)
https://uplustogethermall.com/section/apple (아이폰)


케이티 마트

https://ktmarket.co.kr/phone/samsung (삼성전자)
https://ktmarket.co.kr/phone/apple (아이폰)



- **출력**: 구조화된 JSON

---

## 📋 기술 스택

- **언어**: Python 3.11+
- **패키지 관리**: uv
- **웹 자동화**: Playwright (SSR/CSR 모두 대응)
- **LLM**: OpenAI API (GPT-4o 또는 Claude API via Anthropic)
- **데이터 구조**: Pydantic (타입 안전 JSON 스키마)
- **로깅**: structlog
- **유틸리티**: tenacity (재시도)

---

## 📝 단계별 구현 계획

각 단계마다 테스트도 필수로 구현

### **Phase 0: 프로젝트 초기화**

#### 0-1. 프로젝트 구조 설정
- uv 프로젝트 초기화 (`uv init`)
- pyproject.toml 설정
- 디렉토리 구조 생성

#### 0-2. 의존성 설치
```bash
uv add playwright pydantic httpx structlog tenacity
uv run playwright install
```

#### 0-3. 데이터 스키마 정의 (Pydantic 모델)
- `ProductModel`: 단말 정보
- `OptionsCatalog`: 옵션 카탈로그 (전수)
- `Variant`: 가격/정책 조합
- `ScrapingResult`: 최종 출력 스키마

---

### **Phase 1: 핵심 인프라 구축**

#### 1-1. Configuration 관리 (`core/config.py`)
```python
class SiteConfig:
    - target_url: str
    - delay_min: float = 1.0
    - delay_max: float = 3.0
    - user_agent: str
    - timeout: int = 30
    - max_retries: int = 3
    - pruning_threshold: int = 3  # 가지치기 임계값
```

#### 1-2. Browser Manager (`core/browser.py`)
- Playwright 브라우저 초기화/종료
- 페이지 컨텍스트 관리
- 타임아웃/재시도 로직
- 페이지 로딩 대기 (networkidle, domcontentloaded)

#### 1-3. State Manager (`core/state.py`)
- 방문한 detail_url 추적 (Set)
- 옵션 상태 해시 추적 (detail_url + options_hash)
- JSON 파일 기반 영속화 (중간 저장)

#### 1-4. Logger 설정 (`utils/logger.py`)
- structlog 기반 구조화된 로그
- 진행상황, 에러, 가지치기 이벤트 기록
- 파일 + 콘솔 동시 출력

---

### **Phase 2: LLM 기반 리스팅 페이지 데이터 수집**

**목표**: 리스팅 페이지에서 휴대폰 기종 정보를 LLM이 맥락을 파악하여 전수 수집

#### 2-1. LLM Client (`core/llm_client.py`)
- OpenAI API 또는 Anthropic API 클라이언트
- 재시도 로직 (rate limit 처리)
- 토큰 사용량 추적
- 비용 모니터링
- Vision API 지원 (스크린샷 분석)

#### 2-2. 리스팅 페이지 Prompt Templates (`utils/prompts.py`)
- 리스팅 페이지 구조 분석 프롬프트
- 상품 카드 셀렉터 추출 가이드
- **리스팅에서 보이는 정보 추출 가이드**:
  * 휴대폰 기종명
  * 변경유형 (통신사이동, 번호이동, 기기변경, 신규가입 등)
  * 출고가
  * 할인가/최종가
  * 요금제 정보 (리스팅에 표시된 경우)
  * 상세 URL
- 페이지네이션 감지 프롬프트
- 시스템 메시지 (리스팅 분석 전문가 역할)

#### 2-3. Listing Page Analyzer (`utils/page_analyzer.py`)
- LLM을 활용한 리스팅 페이지 구조 분석
- HTML + 스크린샷을 LLM에 제공
- LLM 응답에서 JSON 추출 및 파싱
- **1차 분석: 페이지 구조 파악**
  * 상품 카드 셀렉터 (`product_card_selector`)
  * 각 정보의 셀렉터 추출:
    - 기종명 셀렉터
    - 변경유형 셀렉터
    - 출고가 셀렉터
    - 할인가/최종가 셀렉터
    - 요금제 셀렉터
    - 상세 URL 셀렉터
  * 페이지네이션 타입 (`pagination_type`)
  * 다음 버튼 셀렉터 (`next_button_selector`)
- **2차 분석: 데이터 추출**
  * LLM이 제공한 셀렉터로 각 상품 카드에서 정보 추출
  * 텍스트 정규화 (가격, 요금제명 등)

#### 2-4. ListingCrawler 클래스 (`crawlers/listing.py`)

**입력**: 리스팅 페이지 URL  
**출력**: `List[PhoneListingItem]` - 리스팅에서 수집한 휴대폰 정보

```python
class PhoneListingItem:
    model_name: str              # 휴대폰 기종명 (예: "갤럭시 S24 Ultra")
    signup_type: Optional[str]   # 변경유형 (예: "번호이동", "기기변경", "신규가입")
    retail_price: Optional[str]  # 출고가
    discount_price: Optional[str] # 할인가/최종가
    plan_name: Optional[str]     # 요금제 (리스팅에 표시된 경우)
    detail_url: str              # 상세 페이지 URL
    image_url: Optional[str]     # 제품 이미지
```

**동작 방식**:

1. **LLM으로 페이지 구조 분석 (1회)**
   - 페이지 로드 후 스크린샷 + HTML 추출
   - PageAnalyzer를 통해 LLM에 분석 요청
   - 동적으로 각 정보의 셀렉터 획득
   - 페이지네이션 방식 파악

2. **모든 페이지 순회하며 데이터 수집**
   ```python
   all_items = []
   current_page = 1
   
   while True:
       # 2-1. 현재 페이지의 상품 카드 선택
       cards = await page.query_selector_all(product_card_selector)
       
       # 2-2. 각 카드에서 정보 추출
       for card in cards:
           item = PhoneListingItem(
               model_name=await extract_text(card, model_name_selector),
               signup_type=await extract_text(card, signup_type_selector),
               retail_price=await extract_text(card, retail_price_selector),
               discount_price=await extract_text(card, discount_price_selector),
               plan_name=await extract_text(card, plan_selector),
               detail_url=await extract_link(card, detail_url_selector),
               image_url=await extract_image(card, image_selector)
           )
           all_items.append(item)
       
       # 2-3. 페이지네이션 처리
       if pagination_type == "pagination":
           has_next = await click_next_button()
           if not has_next:
               break
       elif pagination_type == "infinite_scroll":
           has_more = await scroll_and_wait()
           if not has_more:
               break
       else:
           break  # 단일 페이지
       
       current_page += 1
   ```

3. **데이터 정제 및 검증**
   - 가격 정규화 (쉼표 제거, 숫자 변환)
   - 중복 제거 (detail_url 기준)
   - 필수 필드 검증 (model_name, detail_url)

#### 2-5. 테스트 전략

**단위 테스트** (`tests/test_phase2_unit.py`):
- LLM Client 초기화 및 호출
- Prompt Templates 생성
- JSON 파싱 및 추출
- 토큰 추적, 비용 모니터링

**통합 테스트** (`tests/test_phase2_integration.py`):
실제 대상 사이트에서 데이터 수집 검증

1. **하이폰 리스팅 페이지 테스트**
   ```python
   async def test_hiphone_listing_collection():
       url = "https://hi-phone.kr/index.php?channel=list&cate=103001000000"
       crawler = ListingCrawler(llm_client, browser_manager)
       items = await crawler.crawl(url)
       
       # 검증
       assert len(items) >= 10, "최소 10개 이상의 상품 수집"
       
       # 첫 번째 상품 검증
       first_item = items[0]
       assert first_item.model_name, "기종명이 있어야 함"
       assert first_item.detail_url, "상세 URL이 있어야 함"
       assert "http" in first_item.detail_url, "절대 URL이어야 함"
       
       # 가격 정보 검증 (리스팅에 표시된 경우)
       if first_item.discount_price:
           assert first_item.discount_price.replace(",", "").isdigit()
       
       # 출력 확인
       print(f"✅ 수집된 상품 수: {len(items)}")
       for i, item in enumerate(items[:3], 1):
           print(f"  {i}. {item.model_name}")
           print(f"     변경유형: {item.signup_type or 'N/A'}")
           print(f"     출고가: {item.retail_price or 'N/A'}")
           print(f"     할인가: {item.discount_price or 'N/A'}")
           print(f"     요금제: {item.plan_name or 'N/A'}")
           print(f"     상세: {item.detail_url[:50]}...")
   ```

2. **띵폰 리스팅 페이지 테스트**
   ```python
   async def test_ddingphone_listing_collection():
       url = "https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90"
       # 동일한 검증 로직
   ```

3. **페이지네이션 테스트**
   - 다음 페이지 버튼 감지 확인
   - 여러 페이지에서 데이터 수집 확인
   - 중복 제거 확인

4. **데이터 품질 검증**
   - 모든 항목에 model_name과 detail_url이 있는지
   - 가격 정보가 숫자로 파싱 가능한지
   - URL이 유효한 형식인지

**성공 기준**:
- ✅ 하이폰, 띵폰에서 각각 10개 이상의 상품 정보 수집
- ✅ LLM이 사이트별로 다른 구조를 자동으로 파악
- ✅ 기종명, 가격, 상세 URL이 정확히 추출됨
- ✅ 페이지네이션이 올바르게 작동
- ✅ 데이터 품질 검증 통과

---

### **Phase 3: LLM 기반 상세 페이지 옵션 분석**

**전제 조건**: Phase 2에서 수집한 `PhoneListingItem`의 `detail_url` 사용

**목표**: 상세 페이지에서 모든 선택 가능한 옵션 카탈로그를 100% 수집

#### 3-1. 상세 페이지 Prompt Templates (`utils/prompts.py` 확장)
- 옵션 추출 프롬프트
  * 통신사, 가입유형, 요금제, 할부, 용량, 색상 등
  * 각 옵션의 UI 타입 (드롭다운/버튼/라디오) 식별
- 가격/정책 영역 식별 프롬프트
  * 최종 가격 표시 영역
  * 할인 정보 영역
  * 약정 정보 영역

#### 3-2. Detail Page Analyzer (`utils/page_analyzer.py` 확장)
- LLM을 활용한 상세 페이지 분석
- 옵션 구조 분석:
  * 각 옵션의 셀렉터 추출
  * 옵션 값 목록 추출
  * 비활성 옵션 감지
- 가격/정책 영역 식별:
  * 가격 표시 셀렉터
  * 할인 정보 셀렉터
  * 업데이트 감지 방법

#### 3-3. OptionsCatalogExtractor 클래스 (`crawlers/catalog.py`)

**입력**: Phase 2에서 수집한 detail_url  
**출력**: `OptionsCatalog` (모든 옵션 목록)

**LLM 기반 동작 방식**:

1. **LLM으로 옵션 UI 자동 식별**
   - 상세 페이지 로드 후 스크린샷 + HTML 추출
   - DetailPageAnalyzer를 통해 LLM에 분석 요청
   - 각 옵션(통신사, 가입유형 등)의 셀렉터와 타입 획득

2. **동적으로 옵션 값 추출**
   - LLM이 제공한 셀렉터로 옵션 UI 접근
   - UI 타입에 따라 값 추출:
     * `<select>`: option 태그 수집
     * `<input type="radio">`: label 또는 value 수집
     * 커스텀 버튼: data-* 또는 텍스트 수집
   - 사이트마다 다른 구조에 자동 적응

3. **LLM으로 옵션 의미 파악 및 정규화**
   - 추출한 텍스트를 LLM이 분류/정규화
   - 예: "SKT", "SK텔레콤", "에스케이텔레콤" → 모두 "SKT"
   - 비활성 옵션 사유 추출 (품절, 선택불가 등)

4. **가격/정책 영역 식별**
   - LLM이 제공한 셀렉터로 가격 표시 영역 파악
   - 업데이트 감지 방법 (요소 변화, 로딩 표시 등)

#### 3-4. 테스트 전략
- **단위 테스트**: 상세 페이지 프롬프트, JSON 파싱
- **통합 테스트**: Phase 2에서 추출한 실제 URL 사용
  * 하이폰, 띵폰 등의 실제 상세 페이지 분석
  * LLM이 옵션 셀렉터를 올바르게 추출하는지 검증
  * 추출된 옵션 카탈로그 구조 확인
  * 최소 5개 이상의 옵션 카테고리 추출 확인

---

### **Phase 4: 옵션 조합 순회 엔진 (가지치기 포함)**

**전제 조건**: Phase 3에서 추출한 옵션 카탈로그 사용

#### 4-1. VariantTraverser 클래스 (`crawlers/traverser.py`)

**입력**: detail_url + Phase 3의 OptionsCatalog  
**출력**: `List[Variant]`

**알고리즘**:

```python
# 우선순위 축 정의
priority_axes = [
    "carrier",      # 통신사
    "signup_type",  # 가입유형
    "plan",         # 요금제
    "installment",  # 할부/약정
    "storage",      # 용량
    "color",        # 색상
    "others"        # 기타
]

def traverse(current_options, axis_index, previous_state):
    """재귀적 옵션 순회"""
    if axis_index >= len(priority_axes):
        return  # 모든 축 완료
    
    axis = priority_axes[axis_index]
    no_change_count = 0
    
    for option_value in catalog[axis]:
        # 1. 옵션 선택 (클릭/드롭다운 변경)
        select_option(axis, option_value)
        
        # 2. 가격/정책 영역 갱신 대기
        wait_for_price_update()
        
        # 3. 현재 상태 추출
        current_state = extract_current_pricing()
        
        # 4. 이전 상태와 비교
        if has_pricing_changed(current_state, previous_state):
            save_variant(current_state)
            no_change_count = 0
            previous_state = current_state
        else:
            no_change_count += 1
        
        # 5. 가지치기 조건
        if no_change_count >= config.pruning_threshold:
            logger.info(f"가격 영향 없음 - 축 순회 중단: {axis}")
            break
        
        # 6. 하위 축 탐색
        traverse(current_options, axis_index + 1, previous_state)
```

#### 4-2. 요금제 폭발 제어
- 요금제 전체 목록은 `options_catalog`에 저장
- 가격 검증은 샘플링:
  - 최저 요금제 (인덱스 0)
  - 중간 요금제 (인덱스 len//2)
  - 최고 요금제 (인덱스 -1)
  - 가격 변화 지점 발견 시 인접 요금제 추가

#### 4-3. PricingExtractor (`crawlers/pricing.py`) - LLM 기반

**페이지에서 가격/정책 영역 동적 파싱:**

1. **LLM이 가격 영역 식별**
   - 스크린샷을 보고 어디에 가격 정보가 있는지 파악
   - CSS 셀렉터 제공

2. **LLM이 가격 의미 분류**
   - 추출된 숫자들이 무엇을 의미하는지 판단:
     * `final_price`: 최종가
     * `installment_principal`: 할부원금
     * `monthly_payment`: 월 납부금
     * `subsidy_official`: 공시지원금
     * `subsidy_additional`: 추가지원금

3. **LLM이 정책 텍스트 추출**
   - 요금제 결합 조건
   - 정책/면책/주의사항 텍스트
   - 사이트마다 다른 위치/표현 자동 처리

#### 4-4. State Hasher (`utils/hasher.py`)
- 옵션 조합 해시 생성 (중복 방지)
- `hash = SHA256(detail_url + sorted(options.items()))`

---

### **Phase 5: 전체 통합 및 출력**

#### 5-1. ResultSerializer (`utils/serializer.py`)
- Pydantic 모델 → JSON 변환
- 파일 저장: `output/result_{timestamp}.json`
- 스키마 검증 (Pydantic ValidationError 처리)

#### 5-2. 출력 구조
```json
{
  "products": [
    {
      "detail_url": "https://...",
      "product_name": "갤럭시 S24",
      "manufacturer": "삼성전자",
      "model_code": "SM-S921N",
      "base_price": "1234000",
      "status": "판매중",
      "options_catalog": {
        "carriers": ["SKT", "KT", "LGU+"],
        "signup_types": ["번호이동", "기기변경", "신규가입"],
        "plans": [
          {"name": "5G 프리미어 에센셜", "monthly_fee": "89000", "benefits": "..."},
          ...
        ],
        "installments": ["24개월", "30개월", "36개월"],
        "storages": ["256GB", "512GB"],
        "colors": ["그린", "블랙", "화이트"]
      },
      "variants": [
        {
          "selected_options": {
            "carrier": "SKT",
            "signup_type": "번호이동",
            "plan": "5G 프리미어 에센셜",
            "installment": "24개월",
            "storage": "256GB",
            "color": "그린"
          },
          "pricing": {
            "final_price": "567000",
            "installment_principal": "500000",
            "monthly_payment": "20833",
            "subsidy_official": "400000",
            "subsidy_additional": "267000"
          },
          "policy_text": "..."
        },
        ...
      ],
      "errors": []
    }
  ],
  "metadata": {
    "scraped_at": "2025-12-27T10:30:00Z",
    "total_products": 50,
    "total_variants": 823,
    "elapsed_seconds": 1234.56
  }
}
```

---

### **Phase 6: 메인 오케스트레이터**

#### 6-1. PhoneScraperAgent 클래스 (`agent.py`)

```python
class PhoneScraperAgent:
    def __init__(self, config: SiteConfig):
        self.config = config
        self.browser_manager = BrowserManager(config)
        self.state_manager = StateManager()
        self.logger = get_logger()
    
    async def run(self):
        """메인 실행 플로우"""
        # 1. 리스팅 크롤러로 detail_url 전수 수집
        listing_crawler = ListingCrawler(self.browser_manager)
        detail_urls = await listing_crawler.crawl(self.config.listing_url)
        self.logger.info(f"수집된 detail_url 개수: {len(detail_urls)}")
        
        # 2. 각 detail_url 처리
        results = []
        for idx, detail_url in enumerate(detail_urls):
            self.logger.info(f"[{idx+1}/{len(detail_urls)}] 처리 중: {detail_url}")
            
            try:
                # 2-a. 옵션 카탈로그 추출
                catalog_extractor = OptionsCatalogExtractor(self.browser_manager)
                options_catalog = await catalog_extractor.extract(detail_url)
                
                # 2-b. 옵션 순회 (Variant 수집)
                traverser = VariantTraverser(self.browser_manager, self.config)
                variants = await traverser.traverse(detail_url, options_catalog)
                
                # 2-c. 결과 저장
                results.append({
                    "detail_url": detail_url,
                    "options_catalog": options_catalog,
                    "variants": variants,
                    "errors": []
                })
                
                # 중간 저장 (10개마다 체크포인트)
                if (idx + 1) % 10 == 0:
                    save_checkpoint(results)
            
            except Exception as e:
                self.logger.error(f"에러 발생: {detail_url}", error=str(e))
                results.append({
                    "detail_url": detail_url,
                    "errors": [str(e)]
                })
        
        # 3. JSON 파일 출력
        serializer = ResultSerializer()
        serializer.save(results, f"output/result_{timestamp()}.json")
        
        # 4. 통계 로그
        self.logger.info(f"완료 - 제품: {len(results)}, Variants: {sum(len(r['variants']) for r in results)}")
```

#### 6-2. 에러 복구
- 특정 detail_url 실패 시 다음으로 진행
- 중간 결과 주기적 저장 (체크포인트)
- 재시작 시 체크포인트부터 재개

---

### **Phase 7: 테스트 및 검증**

#### 7-1. 단위 테스트
```
tests/
├── test_listing.py         # 리스팅 크롤러
├── test_catalog.py         # 옵션 카탈로그 추출
├── test_traverser.py       # 옵션 순회 엔진
├── test_pricing.py         # 가격 파싱
└── test_state.py           # 상태 관리
```

#### 7-2. 통합 테스트
- 샘플 사이트로 전체 플로우 실행
- 더미 HTML 페이지 생성 → 로컬 서버 → 스크래핑 테스트

#### 7-3. 데이터 검증
- 전수 수집 확인: 리스팅 카운트 vs 수집된 개수
- JSON 스키마 검증 (Pydantic)
- 가지치기 로직 검증

---

## 📂 디렉토리 구조

```
phone_scrapper_v2/
├── pyproject.toml          # uv 프로젝트 설정
├── uv.lock
├── README.md
├── PRD.md                  # 요구사항 정의
├── PLAN.md                 # 이 파일
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic 모델
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # SiteConfig
│   │   ├── browser.py          # BrowserManager
│   │   ├── state.py            # StateManager
│   │   └── robots.py           # RobotsTxtChecker
│   ├── crawlers/
│   │   ├── __init__.py
│   │   ├── listing.py          # ListingCrawler
│   │   ├── catalog.py          # OptionsCatalogExtractor
│   │   ├── traverser.py        # VariantTraverser
│   │   └── pricing.py          # PricingExtractor
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py           # structlog 설정
│   │   ├── hasher.py           # 상태 해시
│   │   ├── normalizer.py       # 텍스트/가격 정규화
│   │   ├── delay.py            # 랜덤 딜레이
│   │   └── serializer.py       # JSON 직렬화
│   └── agent.py                # PhoneScraperAgent (메인)
├── tests/
│   ├── __init__.py
│   ├── test_listing.py
│   ├── test_catalog.py
│   ├── test_traverser.py
│   ├── test_pricing.py
│   └── test_state.py
├── output/                     # JSON 결과 저장
│   └── result_*.json
├── logs/                       # 로그 파일
│   └── scraper_*.log
└── checkpoints/                # 중간 저장
    └── checkpoint_*.json
```

---

## 🚀 구현 순서 (단계별)

1. ✅ **Phase 0** → 프로젝트 초기화 + 스키마 정의
2. ✅ **Phase 1** → 핵심 인프라 (Config, Browser, State, Logger)
3. 🔄 **Phase 2** → LLM 기반 리스팅 페이지 데이터 수집
   - LLM Client 구축
   - 리스팅 페이지 구조 분석
   - 휴대폰 기종, 가격, 요금제 정보 수집
   - 페이지네이션 처리
   - 실제 대상 사이트 테스트
4. 🔜 **Phase 3** → LLM 기반 상세 페이지 옵션 카탈로그 추출
5. 🔜 **Phase 4** → LLM 기반 옵션 조합 순회 엔진 (가지치기)
6. 🔜 **Phase 5** → 전체 통합 및 출력
7. 🔜 **Phase 6** → 메인 오케스트레이터
8. 🔜 **Phase 7** → 전체 테스트 및 검증

---

## 📌 핵심 원칙 재확인

### ✅ 100% 전수 수집
- 리스팅 페이지의 모든 detail_url
- 상세페이지의 모든 옵션 카탈로그

### ⚠️ 부분 전수 (가지치기 포함)
- 가격/정책 영향 있는 옵션 조합만 순회
- 연속 K회 변화 없으면 중단
- 요금제는 샘플링 전략

### 🚫 중복 방지
- detail_url + 옵션 상태 해시 추적
- 동일 조합은 재방문하지 않음

### 🤖 LLM 기반 지능형 처리
- 하드코딩된 셀렉터 없음 - LLM이 페이지 구조 분석
- 사이트별 구조 차이 자동 적응
- 동적으로 변하는 UI에도 대응
- 옵션 의미 파악 및 정규화 (예: "SKT" ≈ "SK텔레콤")

### 🛡️ 준수사항
- 1~3초 랜덤 딜레이 (서버 부하 방지)
- 로그인 필요 시 즉시 중단
- 에러 발생 시 다음으로 진행
- LLM API 사용량 추적 및 제한

---

## 🎯 완료 조건

- [ ] 모든 리스팅 페이지에서 신규 detail_url 발견 불가
- [ ] detail_url 전수 방문 완료
- [ ] 각 상세페이지에서 options_catalog 완성
- [ ] 옵션 순회 규칙에 따른 variants 수집 완료
- [ ] JSON 파일 출력 완료
- [ ] 스키마 검증 통과

---

**구현 준비 완료. Phase 0부터 시작합니다.**

