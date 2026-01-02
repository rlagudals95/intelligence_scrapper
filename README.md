# Phone Scraper V2

웹 자동화 기반 휴대폰 기종/요금제 데이터 수집 에이전트

## 🎯 프로젝트 개요

리스팅 페이지에서 상세 URL을 **100% 전수** 수집하고, 각 상세페이지에서 옵션 카탈로그를 **100% 수집**하며, 가격/정책에 영향을 주는 옵션 조합을 가지치기를 통해 효율적으로 순회하여 구조화된 JSON으로 출력합니다.

## 📋 기술 스택

- **언어**: Python 3.11+
- **패키지 관리**: uv
- **웹 자동화**: Playwright (Chromium)
- **데이터 검증**: Pydantic
- **로깅**: structlog
- **재시도**: tenacity

## 🚀 설치 및 실행

### 1. 프로젝트 클론 및 의존성 설치

```bash
cd phone_scrapper_v2

# uv로 의존성 설치 (가상환경 자동 생성)
uv sync

# Playwright 브라우저 설치
uv run playwright install chromium
```

### 2. 실행

```bash
# 메인 스크립트 실행 (Phase 2 이후 구현)
uv run python -m src.agent
```

## 📂 프로젝트 구조

```
phone_scrapper_v2/
├── src/
│   ├── models/
│   │   └── schemas.py          # Pydantic 데이터 모델
│   ├── core/
│   │   ├── config.py           # 설정 관리
│   │   ├── browser.py          # 브라우저 관리
│   │   └── state.py            # 상태 관리 (중복 방지)
│   ├── crawlers/               # 크롤러 (Phase 2+ 구현 예정)
│   │   ├── listing.py          # 리스팅 크롤러
│   │   ├── catalog.py          # 옵션 카탈로그 추출
│   │   ├── traverser.py        # 옵션 순회 엔진
│   │   └── pricing.py          # 가격 파싱
│   ├── utils/
│   │   ├── logger.py           # 로깅 설정
│   │   └── delay.py            # 랜덤 딜레이
│   └── agent.py                # 메인 오케스트레이터 (Phase 6 구현 예정)
├── tests/                      # 테스트
├── output/                     # JSON 결과 저장
├── logs/                       # 로그 파일
└── checkpoints/                # 중간 저장

```

## ✅ 구현 현황

### Phase 0: 프로젝트 초기화 ✅
- [x] uv 프로젝트 초기화
- [x] 의존성 설치
- [x] Pydantic 스키마 정의

### Phase 1: 핵심 인프라 ✅
- [x] Configuration 관리 (`core/config.py`)
- [x] Browser Manager (`core/browser.py`)
- [x] State Manager (`core/state.py`)
- [x] Logger 설정 (`utils/logger.py`)

### Phase 2: LLM 통합 ✅
- [x] LLM Client (`core/llm_client.py`) - OpenAI/Anthropic 지원
- [x] Page Analyzer (`utils/list_page_analyzer.py`) - LLM 기반 페이지 분석
- [x] Prompt Templates (`utils/prompts.py`) - 리스팅/옵션/가격 분석
- [x] 테스트 작성 및 통과

### Phase 3: LLM 기반 리스팅 크롤러 🔜
- [ ] ListingCrawler LLM 통합
- [ ] 동적 셀렉터 추출
- [ ] 페이지네이션 자동 감지

### Phase 4: LLM 기반 옵션 카탈로그 🔜
- [ ] OptionsCatalogExtractor LLM 통합
- [ ] 자동 옵션 UI 식별
- [ ] 옵션 의미 파악 및 정규화

### Phase 5: 옵션 순회 엔진 🔜
- [ ] VariantTraverser 구현
- [ ] 가지치기 로직
- [ ] PricingExtractor LLM 통합

### Phase 6: 출력 및 저장 🔜
- [ ] ResultSerializer 구현
- [ ] JSON 출력

### Phase 7: 메인 오케스트레이터 🔜
- [ ] PhoneScraperAgent 구현
- [ ] 에러 복구 로직

### Phase 8: 테스트 및 검증 🔜
- [ ] 단위 테스트
- [ ] 통합 테스트

## 🔧 핵심 컴포넌트

### SiteConfig
사이트별 스크래핑 설정 관리
- 대상 URL, 딜레이, 타임아웃, 가지치기 임계값 등

### BrowserManager
Playwright 브라우저 관리
- 브라우저 초기화/종료
- 페이지 이동, 스크롤, 대기 등

### StateManager
중복 방지 및 방문 추적
- detail_url 방문 여부
- 옵션 조합 상태 해시 추적

### Logger
구조화된 로깅 (structlog)
- 파일 + 콘솔 동시 출력
- JSON 형식 로그

## 📄 출력 형식

```json
{
  "products": [
    {
      "detail_url": "https://...",
      "product_name": "갤럭시 S24",
      "options_catalog": {
        "carriers": ["SKT", "KT", "LGU+"],
        "plans": [...],
        "storages": [...],
        "colors": [...]
      },
      "variants": [
        {
          "selected_options": {...},
          "pricing": {...},
          "policy_text": "..."
        }
      ]
    }
  ],
  "metadata": {
    "scraped_at": "2025-12-27T10:30:00Z",
    "total_products": 50,
    "total_variants": 823
  }
}
```

## 📌 핵심 원칙

✅ **100% 전수 수집**
- 리스팅 페이지의 모든 detail_url
- 상세페이지의 모든 옵션 카탈로그

⚠️ **부분 전수 (가지치기)**
- 가격/정책 영향 있는 옵션 조합만 순회
- 연속 N회 변화 없으면 중단

🚫 **중복 방지**
- detail_url + 옵션 상태 해시 추적

## 📖 참고 문서

- [PRD.md](./PRD.md) - 요구사항 정의서
- [PLAN.md](./PLAN.md) - 상세 구현 계획

## 📝 라이선스

내부 사용 전용

