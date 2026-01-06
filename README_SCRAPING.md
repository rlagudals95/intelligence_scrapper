# 휴대폰 정책 스크래핑 가이드

## 🚀 빠른 시작

### 1. 환경변수 설정 (.env)

```bash
# LLM API 키 (하나 이상 필요)
GEMINI_API_KEY=your_gemini_api_key_here
# 또는
OPENAI_API_KEY=your_openai_api_key_here
# 또는
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# 슬랙 웹훅 URL (선택적)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 2. 사용 방법

#### 방법 1: 명령줄로 직접 실행 (추천!)

```bash
# 기본 사용법
python scrape_phones.py \
  --list-url "https://hi-phone.kr/index.php?channel=list&cate=103001000000" \
  --models "갤럭시S25,아이폰17"

# 사이트 이름 지정
python scrape_phones.py \
  --list-url "https://www.deliveryphone.co.kr/phone/list/2" \
  --models "갤럭시S25,갤럭시S25플러스" \
  --site-name "딜리버리폰"

# 브라우저 표시하기 (디버깅용)
python scrape_phones.py \
  --list-url "https://..." \
  --models "갤럭시S25" \
  --no-headless

# 슬랙 알림 비활성화
python scrape_phones.py \
  --list-url "https://..." \
  --models "갤럭시S25" \
  --no-slack
```

#### 방법 2: 설정 파일 사용

1. 설정 파일 생성 (`my_scrape.json`):

```json
{
  "list_url": "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
  "models": ["갤럭시S25", "아이폰17"],
  "site_name": "하이폰_삼성"
}
```

2. 실행:

```bash
python scrape_phones.py --config my_scrape.json
```

#### 방법 3: 배치 스크래핑 (여러 사이트)

1. 배치 설정 파일 생성 (`batch_scrape.json`):

```json
{
  "sites": [
    {
      "list_url": "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
      "models": ["갤럭시S25", "아이폰17"],
      "site_name": "하이폰_삼성"
    },
    {
      "list_url": "https://www.deliveryphone.co.kr/phone/list/2",
      "models": ["갤럭시S25"],
      "site_name": "딜리버리폰_삼성"
    },
    {
      "list_url": "https://hi-phone.kr/index.php?channel=list&cate=103002000000",
      "models": ["아이폰17"],
      "site_name": "하이폰_아이폰"
    }
  ]
}
```

2. 실행:

```bash
# 직접 실행
uv run python scrape_phones.py --batch-config batch_scrape.json

# Makefile 사용
make scrape-batch CONFIG=batch_scrape.json

# 예제 실행
make scrape-batch-example
```

#### 방법 4: Makefile 사용

```bash
# URL과 모델명 지정
make scrape URL='https://hi-phone.kr/...' MODELS='갤럭시S25,아이폰17'

# 설정 파일로 실행
make scrape-from-config CONFIG=my_scrape.json

# 예제 실행 (하이폰)
make scrape-example

# 배치 스크래핑
make scrape-batch CONFIG=batch_scrape.json
```

## 📋 지원 사이트

| 사이트 | 리스트 URL 예시 |
|--------|----------------|
| 하이폰 (삼성) | `https://hi-phone.kr/index.php?channel=list&cate=103001000000` |
| 하이폰 (애플) | `https://hi-phone.kr/index.php?channel=list&cate=103002000000` |
| 딜리버리폰 (삼성) | `https://www.deliveryphone.co.kr/phone/list/2` |
| 딜리버리폰 (애플) | `https://www.deliveryphone.co.kr/phone/list/3` |
| 성지폰 (삼성) | `https://sungjiphone.com/phone/list/2` |
| 투게더몰 (삼성) | `https://uplustogethermall.com/section/samsung` |

## 🎯 모델명 입력 팁

### 정확한 매칭을 위한 모델명

- ✅ **갤럭시S25** - "갤럭시 S25", "GalaxyS25" 등 자동 매칭
- ✅ **아이폰17** - "아이폰 17", "iPhone17" 등 자동 매칭
- ✅ **갤럭시S25플러스** - 정확한 모델명
- ✅ **갤럭시폴드7** - 폴더블 기종

### 여러 모델 동시 검색

```bash
--models "갤럭시S25,갤럭시S25플러스,갤럭시S25울트라"
```

## 📊 결과 출력

### 1. 콘솔 출력

```
======================================================================
🚀 휴대폰 정책 스크래핑 시작
======================================================================
사이트: 하이폰
리스트 URL: https://hi-phone.kr/...
찾을 모델: 갤럭시S25, 아이폰17
======================================================================

📋 [1단계] 제품 URL 추출 중...
   전체 제품: 8개

🔍 [2단계] 타겟 모델 필터링 중...
   ✅ 매칭: 갤럭시 S25 (찾는 모델: 갤럭시S25)
   필터링 결과: 1개 제품

🔍 [3단계] 상세 페이지 분석 중...
   [1/1] 갤럭시 S25
      URL: https://hi-phone.kr/...
      ✅ 정책 24개 추출 완료 (45.2초)

💾 [4단계] 결과 저장 중...
   저장 완료: output/scraping/하이폰_20260106_200530.json

======================================================================
📊 최종 결과
======================================================================
사이트: 하이폰
타겟 모델: 갤럭시S25
처리 제품: 1개
성공: 1개
총 정책: 24개
소요 시간: 52.3초

LLM 요청: 3회
LLM 토큰: 45,123 tokens
LLM 비용: $0.1234 USD
======================================================================

📤 슬랙 알림 전송 중...
   ✅ 슬랙 알림 전송 완료
```

### 2. JSON 파일 (`output/scraping/`)

```json
{
  "site_name": "하이폰",
  "list_url": "https://...",
  "target_models": ["갤럭시S25"],
  "scraped_at": "2026-01-06T20:05:30",
  "total_duration": 52.3,
  "results": [
    {
      "product_name": "갤럭시 S25",
      "url": "https://...",
      "policy_count": 24,
      "duration": 45.2,
      "products": [...]
    }
  ]
}
```

### 3. 슬랙 알림

#### 개별 제품 알림
```
✅ 스크래핑 결과: 하이폰 - 갤럭시 S25

상태: 성공
소요 시간: 45.2초
제품 수: 1개
정책 수: 24개
```

#### 전체 요약
```
🎯 통합 스크래핑 결과 요약

전체 사이트: 1개
성공 사이트: 1개 ✅
제품 수: 1개
정책 수: 24개

사이트별 결과:
✅ 하이폰 - 갤럭시 S25: 1개 제품, 24개 정책

LLM 요청: 3회
토큰 사용: 45,123
비용: $0.1234
소요 시간: 52.3초
```

## ⚙️ 고급 설정

### 여러 사이트 배치 처리

`batch_scrape.sh` 생성:

```bash
#!/bin/bash

# 하이폰 삼성
python scrape_phones.py \
  --list-url "https://hi-phone.kr/index.php?channel=list&cate=103001000000" \
  --models "갤럭시S25,아이폰17" \
  --site-name "하이폰_삼성"

# 딜리버리폰 삼성
python scrape_phones.py \
  --list-url "https://www.deliveryphone.co.kr/phone/list/2" \
  --models "갤럭시S25" \
  --site-name "딜리버리폰_삼성"

echo "✅ 배치 스크래핑 완료!"
```

실행:
```bash
chmod +x batch_scrape.sh
./batch_scrape.sh
```

## 🐛 문제 해결

### 1. 모델을 찾지 못하는 경우

**증상**: "일치하는 제품을 찾지 못했습니다"

**해결**:
- 전체 제품 목록 확인 (콘솔에 출력됨)
- 모델명을 정확하게 입력 (예: "갤럭시S25" → "갤럭시 S25")
- 공백 추가/제거 시도

### 2. 슬랙 알림이 전송되지 않는 경우

**해결**:
- `.env` 파일에 `SLACK_WEBHOOK_URL` 확인
- `--no-slack` 옵션 제거
- 웹훅 URL이 유효한지 확인

### 3. API 키 오류

**해결**:
- `.env` 파일 확인
- API 키가 올바른지 확인
- 최소 하나의 LLM API 키 필요 (GEMINI, OPENAI, ANTHROPIC 중 선택)

## 📝 참고사항

- **헤드리스 모드**: 기본적으로 브라우저가 표시되지 않습니다 (`--no-headless`로 표시 가능)
- **비용**: LLM API 호출 비용이 발생합니다 (제품당 약 $0.05-0.15)
- **시간**: 제품당 약 30-60초 소요
- **정확도**: 모델명 매칭은 유연하게 처리되지만, 정확한 이름 사용 권장

