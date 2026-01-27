테스트 실행 방법
1. 단위 테스트 (Unit Tests)

npm test              # 모든 단위 테스트 실행
npm run test:watch    # 파일 변경 시 자동 재실행
2. 멀티 사이트 테스트 (크롤링)

# 모든 사이트 테스트 (삼성)
npm run test:sites

# 특정 사이트만 테스트
npm run test:sites -- --sites 하이폰,딜리버리폰,성지폰,폰슐랭

# 특정 모델 검색
npm run test:sites -- --models "갤럭시 S25"

# 애플 제품 테스트
npm run test:sites -- --models "아이폰 17" --sites 하이폰

# force
npm run test:site -- -m "갤럭시 S25" -s 하이폰 --force

# 브라우저 보이게 실행
npm run test:sites -- --no-headless
3. 단일 사이트 스크래핑

# 간단한 스크래핑
npm run scrape:simple

# 전체 스크래핑 (CLI)
npm run scrape -- --site 하이폰 --url "https://hi-phone.kr/..." --models "갤럭시 S25"
4. 결과 확인
JSON 결과: output/scraping/
CSV 결과: output/scraping/csv/
테스트 결과: output/test-results/{timestamp}/



# 전체 삼성폰 스크래핑 (모델 필터링 없음)
npm run test:sites -- --sites 하이폰,딜리버리폰,성지폰,폰슐랭 --all --force

# 전체 애플폰 스크래핑
npm run test:sites -- --sites 하이폰 --all --apple-only --force

# scrape-simple에서 전체 스크래핑
npm run scrape:simple -- -s 하이폰 --all
npm run scrape:simple -- -s 하이폰 --all --apple