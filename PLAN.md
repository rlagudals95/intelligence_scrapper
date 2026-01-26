# 개발 계획: 스마트 캐싱 시스템

## 개요

PRD에 따라 LLM 호출을 최소화하는 "스마트 캐싱" 시스템 구현.
- LLM은 **분석가** 역할 (처음 한 번만 페이지 구조 분석)
- 분석 결과를 **캐싱**하여 재사용
- 정상 상황에서는 **LLM 호출 0회**

---

## Phase 1: 페이지 구조 캐시 (Local JSON)

### 목표
LLM이 분석한 페이지 구조(셀렉터)를 로컬 JSON 파일로 저장하고 재사용

### 구현 항목

#### 1.1 PageStructureCache 클래스
```typescript
// src/core/page-structure-cache.ts
interface CachedPageStructure {
  siteId: string;                    // 사이트 식별자 (예: "하이폰")
  pageType: 'listing' | 'detail';
  url_pattern: string;               // URL 패턴 (쿼리 파라미터 제외)
  structure: ListingAnalysisResult | DetailOptionsResult;
  htmlHash: string;                  // HTML 구조 해시 (변경 감지용)
  createdAt: string;
  lastUsedAt: string;
  successCount: number;              // 성공 횟수
  failureCount: number;              // 실패 횟수
}
```

#### 1.2 캐시 저장소
```
checkpoints/
├── page-structures/
│   ├── 하이폰_listing.json
│   ├── 하이폰_detail.json
│   ├── 딜리버리폰_listing.json
│   └── ...
```

#### 1.3 캐시 조회 로직
```
1. URL에서 siteId + pageType 추출
2. 캐시 파일 존재 확인
3. 존재하면:
   - HTML 구조 해시 비교
   - 해시 동일 → 캐시 사용
   - 해시 다름 → LLM 재분석 (구조 변경됨)
4. 없으면:
   - LLM 분석 실행
   - 결과 캐시 저장
```

#### 1.4 실패 카운터
- 캐시된 셀렉터로 추출 실패 시 `failureCount++`
- `failureCount >= 3` → LLM 재분석 트리거
- 성공 시 `failureCount = 0`, `successCount++`

---

## Phase 2: HTML 구조 해시

### 목표
페이지의 "구조적 변화"만 감지 (컨텐츠 변화 무시)

### 구현 항목

#### 2.1 구조 해시 생성
```typescript
// src/utils/html-hasher.ts
function getStructureHash(html: string): string {
  // 1. HTML 파싱
  // 2. 텍스트 컨텐츠 제거 (숫자, 가격 등)
  // 3. class, id 속성만 추출
  // 4. 구조 트리 생성
  // 5. SHA256 해시
}
```

#### 2.2 해시 비교 전략
- 리스팅 페이지: 상품 카드 영역의 구조만 해시
- 상세 페이지: 옵션 선택 UI + 가격 영역 구조 해시

---

## Phase 3: 캐시 통합

### 목표
기존 크롤러에 캐시 시스템 통합

### 수정 파일
- `src/crawlers/listing.ts` - ListingCrawler
- `src/utils/list-page-analyzer.ts` - ListPageAnalyzer
- `src/utils/detail-page-analyzer.ts` - DetailPageAnalyzer
- `src/services/phone-scraper-service.ts` - 메인 서비스

### 크롤러 흐름 변경
```
기존:
  1. 페이지 이동
  2. LLM 분석 (매번)
  3. 데이터 추출

변경 후:
  1. 페이지 이동
  2. 캐시 확인
     - 캐시 있음 + 구조 동일 → 캐시 사용
     - 캐시 없음 or 구조 변경 → LLM 분석 → 캐시 저장
  3. 데이터 추출
  4. 추출 성공/실패에 따라 캐시 카운터 업데이트
```

---

## Phase 4: CLI 명령어

### 캐시 관련 명령어
```bash
# 캐시 목록 확인
npm run cache:list

# 특정 사이트 캐시 삭제 (재분석 강제)
npm run cache:clear -- --site 하이폰

# 전체 캐시 삭제
npm run cache:clear -- --all

# 캐시 상태 확인
npm run cache:status
```

---

## Phase 5: DynamoDB 마이그레이션 (이후)

### 목표
로컬 JSON → DynamoDB로 캐시 저장소 변경

### 테이블 설계
```
Table: PageStructureCache
- PK: siteId
- SK: pageType
- Attributes:
  - url_pattern
  - structure (JSON)
  - htmlHash
  - timestamps
  - counters
```

### 구현 항목
- `src/core/cache-storage.ts` - 스토리지 인터페이스
- `src/core/local-cache-storage.ts` - 로컬 JSON 구현
- `src/core/dynamodb-cache-storage.ts` - DynamoDB 구현

---

## 우선순위 및 일정

| Phase | 내용 | 우선순위 |
|-------|------|----------|
| Phase 1 | 페이지 구조 캐시 (Local JSON) | P0 - 필수 |
| Phase 2 | HTML 구조 해시 | P0 - 필수 |
| Phase 3 | 캐시 통합 | P0 - 필수 |
| Phase 4 | CLI 명령어 | P1 - 권장 |
| Phase 5 | DynamoDB 마이그레이션 | P2 - 이후 |

---

## 성공 지표

1. **LLM 호출 최소화**
   - 동일 사이트 2회차 이후 LLM 호출 0회
   - 구조 변경 시에만 재분석

2. **캐시 히트율**
   - 목표: 95% 이상

3. **비용 절감**
   - 일일 스크래핑 시 LLM 비용 90% 감소

---

## 파일 구조 (예정)

```
src/
├── core/
│   ├── page-structure-cache.ts    # 캐시 관리자
│   ├── cache-storage.ts           # 스토리지 인터페이스
│   └── local-cache-storage.ts     # 로컬 JSON 스토리지
├── utils/
│   └── html-hasher.ts             # 구조 해시 유틸
├── cli/
│   └── cache-commands.ts          # 캐시 CLI
```
