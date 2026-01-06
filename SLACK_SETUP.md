# 슬랙 알림 설정 가이드

## 1. 슬랙 웹훅 URL 생성

1. https://api.slack.com/apps 접속
2. "Create New App" 클릭
3. "From scratch" 선택
4. App 이름 입력 (예: "Phone Scraper Bot")
5. Workspace 선택
6. "Incoming Webhooks" 활성화
7. "Add New Webhook to Workspace" 클릭
8. 알림을 받을 채널 선택
9. Webhook URL 복사

## 2. 환경변수 설정

`.env` 파일에 다음 내용 추가:

```bash
# 슬랙 웹훅 URL
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## 3. 테스트

```bash
# 단일 사이트 통합 테스트 (슬랙 알림 포함)
make test-integration-single

# 다중 사이트 통합 테스트 (슬랙 알림 포함)
make test-integration-multi
```

## 4. 슬랙 알림 메시지 형식

### 개별 사이트 결과
```
✅ 스크래핑 결과: 하이폰_삼성

상태: 성공
소요 시간: 45.2초
제품 수: 1개
정책 수: 36개

상세 정보:
• 전체 제품 URL: 8개
• 분석한 제품: 1개 (테스트)
• LLM 요청: 3회

⏰ 2026-01-06 19:30:15
```

### 통합 결과 요약
```
🎯 통합 스크래핑 결과 요약

전체 사이트: 2개
성공 사이트: 2개 ✅
제품 수: 2개
정책 수: 72개

사이트별 결과:
✅ 하이폰_삼성: 1개 제품, 36개 정책
✅ 딜리버리폰_삼성: 1개 제품, 36개 정책

LLM 요청: 6회
토큰 사용: 125,432
비용: $0.3213
소요 시간: 90.5초

⏰ 2026-01-06 19:32:00
```

## 5. 주의사항

- 웹훅 URL은 **절대 공개 저장소에 커밋하지 마세요**
- `.env` 파일은 `.gitignore`에 포함되어 있습니다
- 슬랙 웹훅 URL이 없어도 테스트는 정상 작동합니다 (알림만 비활성화)

