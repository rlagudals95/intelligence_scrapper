.PHONY: help install test test-phase1 test-phase2 test-phase3 test-all clean
.PHONY: test-hiphone test-ddingphone test-deliveryphone debug-ddingphone
.PHONY: test-phase3-step1 test-phase3-step2 test-phase3-step3 test-phase3-step4
.PHONY: test-phase3b-step1 test-phase3b-step2 test-ddingphone-api test-ddingphone-api3
.PHONY: test-integration test-integration-quick

# 기본 타겟
help:
	@echo "📋 사용 가능한 명령어:"
	@echo ""
	@echo "  make install              - 의존성 설치 및 Playwright 설정"
	@echo "  make test-list-analyzer   - Phase 1: 인프라 테스트"
	@echo "  make test-extract-urls    - 리스트 페이지 URL 추출 테스트 🔗"
	@echo "  make test-extract-urls-all - 전체 사이트 URL 추출 (통합) 🌐"
	@echo ""
	@echo "  === 상세 페이지 분석 테스트 ==="
	@echo "  make test-detail-page-analyzer-step1 - Step 1: 기본 정보 추출 📋"
	@echo "  make test-detail-page-analyzer-step2 - Step 2: 옵션 UI 분석 🎛️"
	@echo "  make test-detail-page-analyzer-step3 - Step 3: 옵션 값 추출 📝"
	@echo "  make test-detail-page-analyzer-step4 - Step 4: 조합 생성 🔀"
	@echo "  make test-detail-page-analyzer-step5 - Step 5: 정책 추출 💰"
	@echo "  make test-detail-page-analyzer-step6 - Step 6: 스키마 변환 📊"
	@echo "  make test-detail-page-analyzer-full  - 전체 통합 테스트 🚀"
	@echo ""
	@echo "  make test-phase3-step1    - Phase 3 Step 1: API 모니터링 기본 테스트 🔍"
	@echo "  make test-phase3-step2    - Phase 3 Step 2: LLM 기반 API 분석 🤖"
	@echo "  make test-phase3-step3    - Phase 3 Step 3: 인터랙션 후 API 모니터링 🎮"
	@echo "  make test-phase3-step4    - Phase 3 Step 4: API 데이터 구조 분석 📊"
	@echo ""
	@echo "  === Phase 3B: 화면 기반 추출 ==="
	@echo "  make test-phase3b-step1   - Phase 3B Step 1: 페이지 구조 분석 🖥️"
	@echo "  make test-phase3b-step2   - Phase 3B Step 2: 화면 가격 추출 💰"
	@echo "  make test-phase3b-step3   - Phase 3B Step 3: 전체 플로우 (5개 조합) ⚡"
	@echo "  make test-phase3b-full    - Phase 3B Full: 전체 수집 (20개 조합) 🔥"
	@echo ""
	@echo "  make test-hiphone         - 하이폰 리스팅 수집 테스트"
	@echo "  make test-ddingphone      - 띵폰 리스팅 수집 테스트"
	@echo "  make test-deliveryphone   - 딜리버리폰 리스팅 수집 테스트"
	@echo ""
	@echo "  === 통합 테스트 ==="
	@echo "  make collect-urls               - Phase 2: 모든 사이트에서 상세 URL 수집 📋"
	@echo "  make test-integration-from-urls - Phase 3: 수집된 URL로 전체 정책 수집 (추천!) 🎯"
	@echo "  make test-integration           - 전체 파이프라인 통합 테스트 (리스팅→상세→정책) 🔄"
	@echo "  make test-integration-quick     - 빠른 통합 테스트 (1개 상품만) ⚡"
	@echo "  make test-integration-simple    - 간소화 통합 테스트 (1개 사이트) 🎯"
	@echo "  make test-integration-multi     - 다중 사이트 통합 테스트 (2개 사이트) 🚀"
	@echo "  make test-integration-all       - 전체 사이트 통합 테스트 (모든 사이트) 🌐"
	@echo ""
	@echo "  make debug-ddingphone     - 띵폰 페이지 디버깅"
	@echo "  make clean                - 캐시 및 임시 파일 정리"

# 의존성 설치
install:
	@echo "📦 의존성 설치 중..."
	uv sync
	@echo "🎭 Playwright 브라우저 설치 중..."
	uv run playwright install chromium

# 상세페이지
test-detail-page-analyzer:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py -v -s --tb=short

test-detail-page-analyzer-all:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py -v -s --tb=short
	uv run pytest tests/test_detail_page_analyzer.py::test_detail_page_analyzer[띵폰_갤럭시S25] -v -s --tb=short
	uv run pytest tests/test_detail_page_analyzer.py::test_detail_page_analyzer[띵폰_아이폰17] -v -s --tb=short
	uv run pytest tests/test_detail_page_analyzer.py::test_detail_page_analyzer[하이폰_갤럭시S25] -v -s --tb=short
	uv run pytest tests/test_detail_page_analyzer.py::test_detail_page_analyzer[하이폰_아이폰17] -v -s --tb=short


test-detail-page-analyzer-step1:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step1_extract_basic_info -v -s --tb=short

test-detail-page-analyzer-step2:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step2_analyze_option_ui -v -s --tb=short

test-detail-page-analyzer-step3:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step3_extract_option_values -v -s --tb=short

test-detail-page-analyzer-step4:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step4_generate_combinations -v -s --tb=short

test-detail-page-analyzer-step5:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step5_extract_policies_sample -v -s --tb=short

test-detail-page-analyzer-step6:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_step6_convert_to_schema -v -s --tb=short

test-detail-page-analyzer-full:
	@echo "🧪 상세페이지 분석 테스트 실행 중..."
	uv run pytest tests/test_detail_page_analyzer.py::test_detail_page_analyzer_full -v -s --tb=short

########################################################

# Phase 1 테스트 (인프라)
test-list-analyzer:
	@echo "🧪 Phase 1 테스트 실행 중..."
	uv run pytest tests/test_list_page_analyzer.py -v

# 리스트 페이지 URL 추출 테스트
test-extract-urls:
	@echo "🧪 리스트 페이지 URL 추출 테스트 실행 중..."
	uv run pytest tests/test_list_page_analyzer.py::test_extract_product_urls -v -s --tb=short

test-extract-urls-all:
	@echo "🧪 전체 사이트 URL 추출 테스트 실행 중..."
	uv run pytest tests/test_list_page_analyzer.py::test_extract_all_sites -v -s --tb=short

# Phase 2 전체 테스트
test-phase2:
	@echo "🧪 Phase 2 테스트 실행 중..."
	uv run pytest tests/test_list_page_analyzer.py -v -s

# 통합 테스트 (리스트 → 상세 → 슬랙)
test-integration-single:
	@echo "🧪 단일 사이트 통합 테스트 실행 중..."
	uv run pytest tests/test_integration.py::test_integration_single_site -v -s --tb=short

test-integration-multi:
	@echo "🧪 다중 사이트 통합 테스트 실행 중..."
	uv run pytest tests/test_integration.py::test_integration_multi_sites -v -s --tb=short

# 메인 스크래핑 스크립트
scrape:
	@echo "🚀 휴대폰 정책 스크래핑 실행 중..."
	@echo "사용법: make scrape URL='https://...' MODELS='갤럭시S25,아이폰17'"
	@if [ -z "$(URL)" ] || [ -z "$(MODELS)" ]; then \
		echo "❌ URL과 MODELS 파라미터가 필요합니다."; \
		echo "예시: make scrape URL='https://hi-phone.kr/...' MODELS='갤럭시S25,아이폰17'"; \
		exit 1; \
	fi
	uv run python scrape_phones.py --list-url "$(URL)" --models "$(MODELS)"

scrape-from-config:
	@echo "🚀 설정 파일로 스크래핑 실행 중..."
	@if [ -z "$(CONFIG)" ]; then \
		echo "❌ CONFIG 파라미터가 필요합니다."; \
		echo "예시: make scrape-from-config CONFIG=scrape_config.json"; \
		exit 1; \
	fi
	uv run python scrape_phones.py --config "$(CONFIG)"

# 예제: 하이폰 갤럭시S25 + 아이폰17
scrape-example:
	@echo "🧪 예제 스크래핑 실행 중..."
	uv run python scrape_phones.py \
		--list-url "https://hi-phone.kr/index.php?channel=list&cate=103001000000" \
		--models "갤럭시S25,아이폰17" \
		--site-name "하이폰_삼성"

# 정리
clean:
	@echo "🧹 캐시 및 임시 파일 정리 중..."
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ 정리 완료!"

