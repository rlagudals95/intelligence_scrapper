# Phase 3: 휴대폰 상세페이지 옵션 정책 수집

## 🎯 목표
휴대폰 상세페이지에서 **모든 옵션 경우의 수**에 따른 가격/정책 정보를 수집

## 📋 수집 대상 정보
- **옵션**: 용량, 색상, 통신사, 가입유형, 요금제, 할부기간
- **가격 정책**: 출고가, 공시지원금, 추가지원금, 할부원금, 월 할부금, 요금제 조건

---

## 🏗️ 아키텍처: 2단계 Fallback 전략

### 전략 개요
```
Phase 3A (우선): API 기반 추출
    ↓ (실패 시)
Phase 3B (방어): 화면 기반 추출
```

---

## 📡 Phase 3A: API 기반 추출 (우선 전략)

### 개념
옵션 선택 시 백엔드 API가 호출되는 경우, API 응답에서 직접 정책 정보를 추출

### 구현 단계

#### Step 1: API 모니터링
```python
class APIMonitor:
    """
    Playwright로 모든 네트워크 요청/응답 캡처
    - page.on("response") 사용
    - JSON 응답만 수집
    """
```

**작업:**
1. 페이지 로드 시 모든 API 호출 캡처
2. 응답 데이터(JSON) 저장
3. 타임스탬프 기록

#### Step 2: 관련 API 식별 (LLM 기반)
```python
class APIAnalyzer:
    """
    LLM이 캡처된 API 응답을 분석하여 정책 관련 API 식별
    """
```

**LLM 판단 기준:**
- API 응답에 가격, 지원금, 요금제 정보가 포함되어 있는가?
- 옵션 선택과 연관된 API인가?
- 정책 계산 결과가 포함되어 있는가?

**프롬프트 예시:**
```
다음 API 응답을 분석하세요.
이 응답이 휴대폰 가격/정책 정보를 포함하는지 판단하세요.

API URL: /api/phone/calculate
응답 데이터: {...}

질문:
1. 가격 정보가 있는가? (출고가, 할인가 등)
2. 지원금 정보가 있는가?
3. 요금제 정보가 있는가?

응답 형식:
{
  "is_relevant": true/false,
  "contains": ["가격", "공시지원금", ...],
  "confidence": 0.95
}
```

#### Step 3: 옵션 조합 생성 (LLM 기반)
```python
class OptionCombinationGenerator:
    """
    LLM이 페이지를 분석하여 모든 옵션과 조합 생성
    """
```

**작업:**
1. HTML에서 옵션 UI 요소 식별
2. 각 옵션의 선택 가능한 값 추출
3. 효율적인 조합 생성 (가지치기 전략)

**가지치기 전략:**
- 용량: 모두 테스트
- 색상: 첫 번째만 (가격 동일)
- 통신사: 모두 테스트
- 가입유형: 모두 테스트
- 요금제: 상위 3개만
- 할부: 24개월만

#### Step 4: API 기반 정책 수집
```python
class APIPolicyCollector:
    """
    각 옵션 조합에 대해:
    1. 옵션 선택 (Playwright 클릭)
    2. API 응답 대기
    3. LLM이 API 응답에서 정책 추출
    """
```

**플로우:**
```
for 각 조합:
    1. Playwright로 옵션 선택
    2. 2초 대기 (API 호출 완료)
    3. 최근 API 응답 가져오기
    4. LLM이 응답 파싱
       {
         "final_price": "1,496,000원",
         "subsidy_official": "500,000원",
         ...
       }
    5. Variant 객체 생성
```

**성공 조건:**
- API 응답에서 필요한 정보 추출 성공
- 최소 80% 이상 조합에서 성공

**실패 시 → Phase 3B로 fallback**

---

## 🖥️ Phase 3B: 화면 기반 추출 (방어 전략)

### 개념
API가 없거나 실패한 경우, 화면에 표시된 가격 정보를 직접 읽어서 추출

### 구현 단계

#### Step 1: 페이지 구조 분석 (LLM)
```python
class PageStructureAnalyzer:
    """
    LLM이 HTML과 스크린샷을 분석하여 UI 구조 파악
    """
```

**분석 대상:**
- 옵션 선택 UI 위치 및 셀렉터
- 가격 표시 영역 위치 및 셀렉터
- 동적 업데이트 영역 식별

#### Step 2: 옵션 선택 및 가격 추출
```python
class ScreenBasedExtractor:
    """
    화면 기반 정책 수집
    """
```

**플로우:**
```
for 각 조합:
    1. Playwright로 옵션 선택
    2. 1초 대기 (화면 업데이트)
    3. 현재 HTML 추출
    4. LLM이 HTML에서 가격 영역 분석
       - "출고가: 1,496,000원" 패턴 찾기
       - "공시지원금: 500,000원" 추출
    5. Variant 객체 생성
```

**LLM 프롬프트 예시 (화면 기반):**
```
현재 페이지 HTML:
<div class="price-area">
  <div class="retail-price">출고가 1,496,000원</div>
  <div class="subsidy">공시지원금 500,000원</div>
  <div class="discount">추가 할인 200,000원</div>
  <div class="installment">할부원금 796,000원</div>
  <div class="plan-info">5G 프리미어 슈퍼 (월 115,000원)</div>
</div>

질문: 다음 정보를 추출하고 숫자만 반환하세요 (콤마와 '원' 제거)

응답 형식 (JSON):
{
  "retail_price": 1496000,
  "public_subsidy": 500000,
  "additional_discount": 200000,
  "installment_fee": 796000,
  "plan_name": "5G 프리미어 슈퍼",
  "plan_fee": 115000,
  "addons": []
}

**숫자는 반드시 정수(int)로, 문자열(string)이 아닙니다.**
```

**LLM 프롬프트 예시 (API 기반):**
```
다음은 옵션 선택 후 호출된 API 응답입니다.
이 응답에서 가격 정보를 추출하세요.

API URL: /api/phone/calculate
API 응답:
{
  "result": "success",
  "data": {
    "devicePrice": 1496000,
    "publicSubsidy": 500000,
    "additionalDiscount": 200000,
    "installmentAmount": 796000,
    "planName": "5G 프리미어 슈퍼",
    "monthlyPlanFee": 115000,
    "insurance": {
      "name": "휴대폰 보험",
      "monthlyFee": 12000,
      "minMonths": 6
    }
  }
}

질문: 위 API 응답을 표준 형식으로 변환하세요.

응답 형식 (JSON):
{
  "retail_price": 1496000,
  "public_subsidy": 500000,
  "additional_discount": 200000,
  "installment_fee": 796000,
  "plan_name": "5G 프리미어 슈퍼",
  "plan_fee": 115000,
  "addons": [
    {
      "name": "휴대폰 보험",
      "price": 12000,
      "keep_months": 6
    }
  ]
}

**필드명을 정확히 매칭하고, 숫자는 정수로 반환하세요.**
```

---

## 🔄 통합: HybridExtractor

### 전체 플로우
```python
class HybridExtractor:
    """
    Phase 3A와 3B를 통합한 하이브리드 추출기
    최종 ScrapingResult JSON 생성
    """
    
    async def extract_all_policies(
        self, 
        detail_url: str, 
        site_name: str
    ) -> ScrapingResult:
        """
        상세 페이지에서 모든 정책 수집
        
        Returns:
            ScrapingResult: 최종 JSON 형식 데이터
        """
        
        # Step 1: 페이지 로드 및 API 모니터링 시작
        monitor = APIMonitor()
        monitor.start_monitoring(page)
        await page.goto(detail_url)
        await asyncio.sleep(2)
        
        # Step 2: 제품 기본 정보 추출
        product_info = await self.extract_product_info(page)
        # {
        #   "sku_code": "갤럭시 S25",
        #   "available_storages": ["256GB", "512GB", "1TB"]
        # }
        
        # Step 3: API 분석
        relevant_apis = await self.identify_relevant_apis(monitor)
        
        # Step 4: 각 저장용량별로 처리
        products = []
        
        for storage in product_info["available_storages"]:
            # Step 4-1: 옵션 조합 생성 (해당 용량 기준)
            combinations = await self.generate_combinations(
                page, 
                fixed_storage=storage
            )
            # [
            #   {"storage": "256GB", "carrier": "SKT", 
            #    "join_type": "기기변경", "plan": "5G 프리미어"},
            #   ...
            # ]
            
            # Step 4-2: 각 조합별 정책 수집
            policies = []
            
            for combo in combinations:
                # 옵션 선택
                await self.select_options(page, combo)
                await asyncio.sleep(2)
                
                # Phase 3A: API 우선
                policy_data = None
                if relevant_apis:
                    api_response = monitor.get_latest_response()
                    policy_data = await self.extract_from_api(api_response)
                
                # Phase 3B: 화면 기반 fallback
                if not policy_data:
                    policy_data = await self.extract_from_screen(page)
                
                # Policy 객체 생성
                if policy_data:
                    policy = Policy(
                        policy_id=self.generate_hash(combo),
                        carrier=combo["carrier"],
                        mno_join_type=parse_join_type(combo["join_type"]),
                        mobile_plan=MobilePlan(
                            name=combo["plan"],
                            monthly_fee=policy_data["plan_fee"]
                        ),
                        discount_type=parse_discount_type(combo["discount_type"]),
                        pricing=Pricing(
                            mno_retail_price=policy_data["retail_price"],
                            public_subsidy=policy_data["public_subsidy"],
                            discount=policy_data["additional_discount"],
                            sku_installment_fee=policy_data["installment_fee"]
                        ),
                        addons=policy_data.get("addons", []),
                        source="api" if relevant_apis else "screen"
                    )
                    policies.append(policy)
            
            # Product 생성
            product = Product(
                product_id=self.generate_hash(product_info["sku_code"] + storage),
                sku_code=product_info["sku_code"],
                sku_storage=parse_storage(storage),
                policies=policies
            )
            products.append(product)
        
        # Step 5: 최종 ScrapingResult 생성
        result = ScrapingResult(
            captured_at=datetime.now(timezone(timedelta(hours=9))),
            source=Source(
                site=site_name,
                url=detail_url
            ),
            products=products
        )
        
        return result
```

### 사용 예시

```python
# 1. 추출기 초기화
extractor = HybridExtractor(llm_client)

# 2. 정책 수집
result = await extractor.extract_all_policies(
    detail_url="https://phonechelin.shop/mshop/view/70",
    site_name="폰슐랭샵"
)

# 3. JSON 출력
json_output = result.model_dump_json(indent=2, ensure_ascii=False)
print(json_output)

# 4. 파일 저장
output_path = f"output/policies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(json_output)
```

---

## 📊 데이터 스키마

### 최종 출력 형식 (JSON)

```json
{
  "captured_at": "2025-12-30T12:00:00+09:00",
  "source": {
    "site": "폰슐랭샵",
    "url": "https://phonechelin.shop/"
  },
  "products": [
    {
      "product_id": "hash13904u0gjhfedg80re",
      "sku_code": "갤럭시 S25",
      "sku_storage": "STORAGE_256G",
      "policies": [
        {
          "policy_id": "hash910234ur09jgf9gj",
          "carrier": "SKT",
          "mno_join_type": "DEVICE_CHANGE",
          "mobile_plan": {
            "name": "5G 프리미어 슈퍼",
            "monthly_fee": 115000
          },
          "discount_type": "PUBLIC_SUBSIDY",
          "pricing": {
            "mno_retail_price": 1250000,
            "public_subsidy": 300000,
            "discount": 200000,
            "sku_installment_fee": 750000
          },
          "addons": [
            {
              "name": "휴대폰 보험",
              "price": 12000,
              "keep_months": 6
            }
          ]
        }
      ]
    }
  ]
}
```

### Python 스키마 (Pydantic)

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class StorageType(str, Enum):
    """저장용량 타입"""
    STORAGE_128G = "STORAGE_128G"
    STORAGE_256G = "STORAGE_256G"
    STORAGE_512G = "STORAGE_512G"
    STORAGE_1T = "STORAGE_1T"

class JoinType(str, Enum):
    """가입 유형"""
    DEVICE_CHANGE = "DEVICE_CHANGE"      # 기기변경
    NUMBER_TRANSFER = "NUMBER_TRANSFER"  # 번호이동

class DiscountType(str, Enum):
    """할인 방식"""
    PUBLIC_SUBSIDY = "PUBLIC_SUBSIDY"      # 공시지원금
    CONTRACT_DISCOUNT = "CONTRACT_DISCOUNT"  # 선택약정

class MobilePlan(BaseModel):
    """요금제 정보"""
    name: str           # "5G 프리미어 슈퍼"
    monthly_fee: int    # 115000 (원)

class Pricing(BaseModel):
    """가격 정책"""
    mno_retail_price: int       # 출고가
    public_subsidy: int         # 공시지원금
    discount: int               # 추가지원금
    sku_installment_fee: int    # 할부원금

class Addon(BaseModel):
    """부가 서비스"""
    name: str           # "휴대폰 보험"
    price: int          # 12000 (월)
    keep_months: int    # 6개월 유지

class Policy(BaseModel):
    """정책 (하나의 옵션 조합)"""
    policy_id: str                    # 해시 ID
    carrier: str                      # "SKT", "KT", "LGU+"
    mno_join_type: JoinType          # 가입유형
    mobile_plan: MobilePlan          # 요금제
    discount_type: DiscountType      # 할인방식
    pricing: Pricing                 # 가격정책
    addons: Optional[List[Addon]]    # 부가서비스
    source: str = "api"              # "api" or "screen"

class Product(BaseModel):
    """제품 (하나의 SKU)"""
    product_id: str              # 해시 ID
    sku_code: str                # "갤럭시 S25"
    sku_storage: StorageType     # 저장용량
    policies: List[Policy]       # 정책 리스트

class Source(BaseModel):
    """데이터 출처"""
    site: str    # "폰슐랭샵"
    url: str     # 사이트 URL

class ScrapingResult(BaseModel):
    """최종 스크래핑 결과"""
    captured_at: datetime        # 수집 시간
    source: Source               # 출처
    products: List[Product]      # 제품 리스트
```

### 데이터 변환 로직

LLM/API 응답 → Python 객체 → JSON 출력

```python
# 1. LLM이 추출한 텍스트 데이터를 숫자로 변환
def parse_price(price_str: str) -> int:
    """'1,250,000원' -> 1250000"""
    return int(price_str.replace(',', '').replace('원', '').strip())

def parse_storage(storage_str: str) -> StorageType:
    """'256GB' -> StorageType.STORAGE_256G"""
    mapping = {
        "128GB": StorageType.STORAGE_128G,
        "256GB": StorageType.STORAGE_256G,
        "512GB": StorageType.STORAGE_512G,
        "1TB": StorageType.STORAGE_1T,
    }
    return mapping.get(storage_str)

def parse_join_type(join_str: str) -> JoinType:
    """'번호이동' -> JoinType.NUMBER_TRANSFER"""
    mapping = {
        "기기변경": JoinType.DEVICE_CHANGE,
        "번호이동": JoinType.NUMBER_TRANSFER,
    }
    return mapping.get(join_str)

def parse_discount_type(discount_str: str) -> DiscountType:
    """'공시지원금' -> DiscountType.PUBLIC_SUBSIDY"""
    mapping = {
        "공시지원금": DiscountType.PUBLIC_SUBSIDY,
        "선택약정": DiscountType.CONTRACT_DISCOUNT,
    }
    return mapping.get(discount_str)
```

---

## 🧪 테스트 전략

### 1. API 모니터링 테스트
```bash
make test-api-monitor
```
**목적:**
- 어떤 API가 호출되는지 확인
- 응답 데이터 구조 파악
- LLM이 API를 정확히 식별하는지 검증

**출력 예시:**
```
📡 감지된 API:
  • GET /api/phone/detail?id=123
  • POST /api/calculate/subsidy
    응답: {"devicePrice": 1496000, "subsidy": 500000, ...}
  
✅ 관련 API 식별: 1개
   - /api/calculate/subsidy (confidence: 0.95)
```

### 2. 단일 조합 테스트
```bash
make test-single-combo
```
**목적:**
- 하나의 옵션 조합만 테스트
- API/화면 양쪽 방법 비교
- 데이터 변환 검증

**출력 예시:**
```json
{
  "test_combination": {
    "storage": "256GB",
    "carrier": "SKT",
    "join_type": "기기변경"
  },
  "extraction_results": {
    "api_method": {
      "success": true,
      "time": "1.2s",
      "data": {
        "retail_price": 1496000,
        "public_subsidy": 500000
      }
    },
    "screen_method": {
      "success": true,
      "time": "2.5s",
      "data": {
        "retail_price": 1496000,
        "public_subsidy": 500000
      }
    }
  },
  "validation": "✅ 일치"
}
```

### 3. 전체 수집 테스트
```bash
make test-phase3-full
```
**목적:**
- 모든 조합 수집
- 성공률 측정
- LLM 비용 및 시간 측정

**출력 예시:**
```
🔄 하이브리드 추출 결과:
   
총 조합: 24개
  - API 성공: 18개 (75%)
  - 화면 성공: 5개 (21%)
  - 실패: 1개 (4%)

⏱️ 성능:
  - 총 소요시간: 2분 30초
  - 평균 조합당: 6.25초
  - API 평균: 3.2초
  - 화면 평균: 8.5초

💰 LLM 비용:
  - 총 요청: 45회
  - 총 토큰: 125,000 tokens
  - 예상 비용: $0.25 USD

✅ 최종 JSON 생성 완료
   파일: output/policies_20251230_120000.json
```

### 4. 다중 사이트 테스트
```bash
make test-phase3-multi-site
```
**목적:**
- 여러 사이트에서 동시 테스트
- 사이트별 성공률 비교
- 범용성 검증

**출력 예시:**
```
📊 사이트별 결과:

폰슐랭샵:
  ✅ 성공률: 95% (19/20)
  ⚡ API 사용: 85%

성지폰:
  ✅ 성공률: 90% (18/20)
  ⚡ API 사용: 40%

띵폰:
  ✅ 성공률: 92% (23/25)
  ⚡ API 사용: 60%

전체 평균: 92.3%
```

---

## 🎯 성능 목표

| 항목 | 목표 |
|------|------|
| 수집 성공률 | 95% 이상 |
| 처리 시간 | 조합당 3-5초 |
| LLM 비용 | 조합당 $0.01 이하 |
| API 우선 성공률 | 70% 이상 |

---

## 📝 구현 순서

### Week 1: 기반 구축 (Day 1-3)
**목표:** API 모니터링 및 식별

- [ ] **Day 1:** 프로젝트 구조 설정
  - `src/crawlers/api_monitor.py` 생성
  - `src/models/phase3_schemas.py` 생성 (Pydantic 스키마)
  - 기본 테스트 파일 생성

- [ ] **Day 2:** APIMonitor 구현
  - Playwright 네트워크 모니터링
  - API 응답 캡처 및 저장
  - 테스트: 실제 사이트에서 API 확인

- [ ] **Day 3:** LLM 기반 API 식별
  - API 응답 내용 분석 프롬프트
  - 관련 API 필터링 로직
  - 테스트: API 식별 정확도

### Week 2: Phase 3A 완성 (Day 4-7)
**목표:** API 기반 정책 추출

- [ ] **Day 4:** 옵션 조합 생성
  - `src/crawlers/option_combinator.py` 생성
  - LLM으로 옵션 UI 분석
  - 가지치기 전략 구현

- [ ] **Day 5:** API 기반 추출
  - `src/crawlers/api_policy_extractor.py` 생성
  - API 응답 → Policy 객체 변환
  - 데이터 파싱 및 검증

- [ ] **Day 6:** 통합 테스트
  - 단일 사이트 전체 플로우
  - JSON 출력 검증
  - 에러 처리

- [ ] **Day 7:** 성능 최적화
  - API 캡처 타이밍 조정
  - 중복 요청 제거
  - 로깅 개선

### Week 3: Phase 3B 구현 (Day 8-10)
**목표:** 화면 기반 Fallback

- [ ] **Day 8:** 화면 분석
  - `src/crawlers/screen_policy_extractor.py` 생성
  - LLM 기반 HTML 파싱
  - 가격 영역 식별

- [ ] **Day 9:** 데이터 추출
  - HTML → Policy 객체 변환
  - 숫자 파싱 및 정규화
  - Phase 3A와 동일한 출력 형식

- [ ] **Day 10:** Fallback 통합
  - API 실패 시 자동 전환
  - 성공률 측정
  - 테스트

### Week 4: 통합 및 완성 (Day 11-14)
**목표:** HybridExtractor 완성 및 배포 준비

- [ ] **Day 11:** HybridExtractor 통합
  - `src/crawlers/hybrid_extractor.py` 생성
  - Phase 3A + 3B 통합
  - ScrapingResult JSON 생성

- [ ] **Day 12:** 다중 사이트 테스트
  - 3개 이상 사이트 테스트
  - 사이트별 성공률 측정
  - 범용성 검증

- [ ] **Day 13:** 최적화 및 안정화
  - 성능 튜닝
  - 에러 처리 강화
  - 재시도 로직

- [ ] **Day 14:** 문서화 및 배포
  - API 문서 작성
  - 사용 예시 작성
  - README 업데이트

---

## 📁 파일 구조

```
src/
├── crawlers/
│   ├── api_monitor.py              # API 모니터링
│   ├── api_analyzer.py             # LLM 기반 API 식별
│   ├── option_combinator.py        # 옵션 조합 생성
│   ├── api_policy_extractor.py     # API 기반 추출 (Phase 3A)
│   ├── screen_policy_extractor.py  # 화면 기반 추출 (Phase 3B)
│   └── hybrid_extractor.py         # 통합 추출기 (Main)
│
├── models/
│   └── phase3_schemas.py           # Pydantic 스키마
│
└── utils/
    ├── data_parser.py              # 데이터 파싱 유틸
    └── hash_generator.py           # ID 생성

tests/
├── test_api_monitor.py             # API 모니터링 테스트
├── test_api_extractor.py           # Phase 3A 테스트
├── test_screen_extractor.py        # Phase 3B 테스트
└── test_hybrid_extractor.py        # 통합 테스트

output/
└── policies_*.json                 # 수집 결과 JSON

Makefile                            # 테스트 명령어
phase3_plan.md                      # 이 문서
```

---

## 🚨 주의사항

### 1. Rate Limiting
- 각 요청 사이 1-2초 대기
- API 호출 제한 확인

### 2. LLM 비용 관리
- 불필요한 LLM 호출 최소화
- 캐싱 전략 활용
- 토큰 사용량 모니터링

### 3. 에러 처리
- 네트워크 오류 재시도
- 타임아웃 처리
- 부분 실패 허용 (일부 조합 실패해도 계속)

### 4. 로깅
- 각 단계별 상세 로그
- 실패 원인 기록
- 디버깅 정보 충분히 남기기

---

## 🔧 기술 스택

- **Playwright**: 브라우저 자동화, 네트워크 모니터링
- **LLM (OpenAI GPT-4)**: 
  - API 응답 분석 및 파싱
  - HTML 구조 분석
  - 옵션 조합 생성
- **Pydantic**: 데이터 검증 및 스키마
- **Pytest**: 테스트 프레임워크
- **Asyncio**: 비동기 처리

---

## 🎮 Makefile 명령어

### 개발 단계
```makefile
# 1. API 탐색 (Week 1)
make test-api-monitor          # API 모니터링 테스트
make test-api-identify         # LLM API 식별 테스트

# 2. Phase 3A 개발 (Week 2)
make test-api-extract          # API 기반 추출 테스트
make test-single-combo         # 단일 조합 테스트
make test-api-full            # 전체 조합 테스트

# 3. Phase 3B 개발 (Week 3)
make test-screen-extract       # 화면 기반 추출 테스트
make test-fallback            # Fallback 로직 테스트

# 4. 통합 (Week 4)
make test-hybrid              # 하이브리드 테스트
make test-multi-site          # 다중 사이트 테스트
make test-phase3-full         # 전체 통합 테스트
```

### 실행 예시
```bash
# 개발 중: 빠른 검증
make test-api-monitor

# 단일 사이트 전체 테스트
make test-phase3-full URL=https://phonechelin.shop/... SITE=폰슐랭샵

# 결과 확인
cat output/policies_20251230_120000.json | jq .
```

---

## 📈 확장 가능성

### 1. 다양한 사이트 대응
**현재:** 3개 사이트 (폰슐랭샵, 성지폰, 띵폰)
**목표:** 10개 이상 사이트

**전략:**
- 사이트별 특수 로직 최소화 (LLM이 자동 적응)
- 공통 패턴 추상화
- 새 사이트 추가 시 설정만 변경

```python
# sites.yaml
- name: "폰슐랭샵"
  url: "https://phonechelin.shop"
  features:
    api_available: true
    dynamic_pricing: true
```

### 2. 병렬 처리
**현재:** 순차 처리 (조합당 3-5초)
**목표:** 병렬 처리 (10배 향상)

**구현:**
```python
# 멀티 브라우저 컨텍스트
contexts = await browser.new_contexts(count=5)

# 병렬 수집
tasks = [
    extract_policy(ctx, combo)
    for ctx, combo in zip(contexts, combinations)
]
results = await asyncio.gather(*tasks)
```

### 3. 스마트 캐싱
**최적화:**
- 동일 옵션 재선택 방지 (30% 시간 절약)
- API 응답 캐싱 (중복 호출 제거)
- LLM 응답 캐싱 (비용 50% 절감)

```python
# 캐시 예시
cache = {
    "api:/api/calculate?storage=256GB&carrier=SKT": {...},
    "llm:parse_price_1496000원": 1496000
}
```

### 4. 실시간 모니터링
**대시보드:**
- 수집 진행률 실시간 표시
- 성공률 그래프
- LLM 비용 추적
- 에러 알림

---

## 💡 베스트 프랙티스

### 1. 효율적인 조합 생성
```python
# ❌ 나쁜 예: 모든 조합 (수백 개)
combinations = itertools.product(
    storages, colors, carriers, join_types, plans, installments
)

# ✅ 좋은 예: 가지치기 (수십 개)
combinations = smart_combinations(
    storages=all,        # 모두
    colors=first_only,   # 첫 번째만
    carriers=all,        # 모두
    join_types=all,      # 모두
    plans=top_3,        # 상위 3개
    installments=["24개월"]  # 고정
)
```

### 2. API 우선 전략
```python
# API 있으면 무조건 API 사용
if api_available:
    result = extract_from_api()  # 빠르고 정확
    if result.is_valid():
        return result

# Fallback
return extract_from_screen()  # 느리지만 확실
```

### 3. 점진적 실패
```python
# 일부 실패해도 계속 진행
for combo in combinations:
    try:
        policy = extract_policy(combo)
        results.append(policy)
    except Exception as e:
        logger.error(f"Failed: {combo} - {e}")
        continue  # 다음 조합으로

# 최소 70% 성공하면 OK
if len(results) / len(combinations) >= 0.7:
    return results
```

---

## ✅ 완료 기준

### Phase 3 완료 조건
- [ ] 3개 이상 사이트에서 90% 이상 성공률
- [ ] JSON 스키마 100% 준수
- [ ] API 우선 전략 70% 이상 활용
- [ ] 조합당 평균 5초 이내 처리
- [ ] LLM 비용 조합당 $0.01 이하
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] 문서화 완료

### 배포 준비 완료
- [ ] 프로덕션 환경 테스트
- [ ] 에러 처리 완벽
- [ ] 로깅 시스템 구축
- [ ] 모니터링 대시보드
- [ ] 운영 매뉴얼 작성

