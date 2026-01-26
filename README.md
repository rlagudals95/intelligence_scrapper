# Phone Scraper V2 - TypeScript Version

LLM 기반 지능형 휴대폰 정책 스크래퍼의 TypeScript 버전입니다.

## 요구사항

- Node.js 20+
- npm 또는 pnpm

## 설치

```bash
# 의존성 설치
npm install

# Playwright 브라우저 설치
npx playwright install chromium
```

## 환경 변수 설정

`.env.example`을 `.env`로 복사하고 API 키를 설정하세요:

```bash
cp .env.example .env
```

필수 환경 변수:
- `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` 또는 `GEMINI_API_KEY` (최소 하나)
- `SLACK_WEBHOOK_URL` (선택사항)

## 사용법

### 간단 모드 (추천)

```bash
# 삼성 갤럭시 스크래핑
npm run scrape:simple -- -s 하이폰 -m "갤럭시S25"

# 아이폰 스크래핑
npm run scrape:simple -- -s 딜리버리폰 -m "아이폰17"

# 브라우저 표시
npm run scrape:simple -- -s 하이폰 -m "갤럭시S25" --no-headless
```

지원 사이트:
- 하이폰
- 딜리버리폰
- 성지폰
- 폰슐랭
- 엘지티샵
- 투게더몰
- 띵폰

### 상세 모드

```bash
# URL 직접 지정
npm run scrape -- -u "https://hi-phone.kr/..." -m "갤럭시S25,아이폰17" -s 하이폰

# 최대 제품 수 제한
npm run scrape -- -u "https://..." -m "갤럭시S25" --max 5

# Slack 알림 비활성화
npm run scrape -- -u "https://..." --no-slack
```

## 프로젝트 구조

```
ts-version/
├── src/
│   ├── core/           # 핵심 인프라
│   │   ├── config.ts   # 설정 관리
│   │   ├── browser.ts  # Playwright 브라우저 관리
│   │   ├── llm-client.ts # LLM API 클라이언트
│   │   └── state.ts    # 상태 관리
│   ├── models/         # Zod 스키마
│   ├── crawlers/       # 크롤러
│   ├── services/       # 서비스
│   └── utils/          # 유틸리티
├── output/             # 결과물 (JSON, CSV)
├── logs/               # 로그 파일
└── checkpoints/        # 체크포인트
```

## 스크립트

```bash
# 빌드
npm run build

# 개발 모드
npm run dev

# 타입 체크
npm run typecheck

# 린트
npm run lint

# 포맷
npm run format

# 테스트
npm run test
```

## 기술 스택

- **언어**: TypeScript 5.x
- **런타임**: Node.js 20+
- **웹 자동화**: Playwright
- **스키마 검증**: Zod
- **LLM**: OpenAI, Anthropic, Google Gemini
- **로깅**: Pino
- **HTTP**: Axios

## 출력 형식

### JSON
```json
{
  "products": [
    {
      "name": "갤럭시 S25",
      "policies": [
        {
          "carrier": "SKT",
          "joinType": "번호이동",
          "plan": { "name": "5G 프리미어", "monthlyFee": 89000 },
          "pricing": {
            "retailPrice": 1500000,
            "publicSubsidy": 500000,
            "finalPrice": 1000000
          }
        }
      ]
    }
  ],
  "capturedAt": "2025-01-26T...",
  "source": { "siteName": "하이폰", "url": "..." }
}
```

### CSV
```
통신사,가입유형,할인유형,요금제명,월요금,출고가,공시지원금,추가할인,최종가,월할부금
SKT,번호이동,공시지원금,5G 프리미어,89000,1500000,500000,0,1000000,41666
```

## 라이선스

MIT
