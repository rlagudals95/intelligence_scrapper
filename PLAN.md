# 구현 계획 (PLAN)

## 🎯 프로젝트 개요

웹 자동화 기반 휴대폰 기종/요금제 데이터 수집 에이전트

- **목표**: 리스팅 페이지에서 상세 URL 전수 수집 → 각 상세페이지에서 옵션 카탈로그 100% 수집 → 가격/정책 영향 옵션 조합 순회 (가지치기 포함)
- **출력**: 구조화된 JSON

---

## 📋 기술 스택

- **언어**: Python 3.11+
- **패키지 관리**: uv
- **웹 자동화**: Playwright (SSR/CSR 모두 대응)
- **데이터 구조**: Pydantic (타입 안전 JSON 스키마)
- **로깅**: structlog
- **유틸리티**: httpx (robots.txt 체크), tenacity (재시도)

---

## 📝 단계별 구현 계획

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

### **Phase 2: 리스팅 페이지 크롤러 (100% 전수)**

#### 2-1. ListingCrawler 클래스 (`crawlers/listing.py`)

**입력**: 랜딩 페이지 URL  
**출력**: `List[Dict[str, str]]` - detail_url 목록

**기능**:

1. 페이지네이션 처리
   - "다음 페이지" 혹은 페이지네이션을 의미하는 버튼 클릭
   - 마지막 페이지 판단

2. 무한 스크롤 처리
   - 스크롤 끝까지 반복
   - 새 컨텐츠 로딩 대기
   - 더 이상 로드되지 않으면 종료

3. 상품 카드에서 추출
   - `product_name`: 상품명
   - `list_url`: 리스팅 페이지 URL
   - `detail_url`: 상세 페이지 URL

#### 2-2. URL 중복 제거
- `detail_url` 유니크 집합 생성
- 누락 검증 로직 (리스트 카운트 vs 수집 카운트)

#### 2-3. 에러 핸들링
- 접근 불가 페이지는 `errors` 리스트에 기록
- 로그인 필요 시 `"login_required"` 기록 후 중단

---

### **Phase 3: 상세페이지 옵션 카탈로그 수집 (100% 전수)**

#### 3-1. OptionsCatalogExtractor 클래스 (`crawlers/catalog.py`)

**입력**: detail_url  
**출력**: `OptionsCatalog` (모든 옵션 목록)

**기능**:
1. 모든 옵션 UI 스캔 (클릭 없이 DOM 분석)
   - `<select>` 드롭다운
   - `<input type="radio">` 라디오 버튼
   - 체크박스
   - 커스텀 버튼 그룹 (data-* 속성 기반)

2. 각 옵션별 수집
   - 통신사 (SKT/KT/LGU+)
   - 가입유형 (번호이동/기기변경/신규가입)
   - 요금제 목록 (이름/월정액/혜택 설명)
   - 할부/약정 기간
   - 용량 (64GB, 128GB, 256GB 등)
   - 색상
   - 기타 옵션 (사은품, 부가서비스)

3. 비활성(disabled) 옵션 처리
   - 목록에 포함
   - `disabled: true` + `reason: "..."` 기록

#### 3-2. 옵션 정규화 (`utils/normalizer.py`)
- 텍스트 트림, 공백 정리
- 가격 숫자 파싱 (정규표현식: `\d{1,3}(,\d{3})*`)
- 단위 통일 (원, 만원 → 숫자)

---

### **Phase 4: 옵션 조합 순회 엔진 (가지치기 포함)**

#### 4-1. VariantTraverser 클래스 (`crawlers/traverser.py`)

**입력**: detail_url + OptionsCatalog  
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

#### 4-3. PricingExtractor (`crawlers/pricing.py`)
페이지에서 가격/정책 영역 파싱:
- `final_price`: 최종가
- `installment_principal`: 할부원금
- `monthly_payment`: 월 납부금
- `subsidy_official`: 공시지원금
- `subsidy_additional`: 추가지원금
- `plan_combination`: 요금제 결합 조건
- `policy_text`: 정책/면책/주의사항 텍스트

#### 4-4. State Hasher (`utils/hasher.py`)
- 옵션 조합 해시 생성 (중복 방지)
- `hash = SHA256(detail_url + sorted(options.items()))`

---

### **Phase 5: 출력 및 저장**

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
        # 1. robots.txt 체크
        if not check_robots_txt(self.config.target_url):
            raise PermissionError("robots.txt 위반")
        
        # 2. 리스팅 크롤러로 detail_url 전수 수집
        listing_crawler = ListingCrawler(self.browser_manager)
        detail_urls = await listing_crawler.crawl(self.config.listing_url)
        self.logger.info(f"수집된 detail_url 개수: {len(detail_urls)}")
        
        # 3. 각 detail_url 처리
        results = []
        for idx, detail_url in enumerate(detail_urls):
            self.logger.info(f"[{idx+1}/{len(detail_urls)}] 처리 중: {detail_url}")
            
            try:
                # 3-a. 옵션 카탈로그 추출
                catalog_extractor = OptionsCatalogExtractor(self.browser_manager)
                options_catalog = await catalog_extractor.extract(detail_url)
                
                # 3-b. 옵션 순회 (Variant 수집)
                traverser = VariantTraverser(self.browser_manager, self.config)
                variants = await traverser.traverse(detail_url, options_catalog)
                
                # 3-c. 결과 저장
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
        
        # 4. JSON 파일 출력
        serializer = ResultSerializer()
        serializer.save(results, f"output/result_{timestamp()}.json")
        
        # 5. 통계 로그
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
3. ✅ **Phase 2** → 리스팅 크롤러 구현 + 테스트
4. ✅ **Phase 3** → 옵션 카탈로그 추출 구현 + 테스트
5. ✅ **Phase 4** → 옵션 순회 엔진 구현 + 테스트
6. ✅ **Phase 5** → 출력/저장 로직
7. ✅ **Phase 6** → 메인 오케스트레이터 통합
8. ✅ **Phase 7** → 전체 테스트 및 검증

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

### 🛡️ 준수사항
- robots.txt 체크
- 1~3초 랜덤 딜레이
- 로그인 필요 시 즉시 중단
- 에러 발생 시 다음으로 진행

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

