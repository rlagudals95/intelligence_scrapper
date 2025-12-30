.PHONY: help install test test-phase1 test-phase2 test-phase3 test-all clean
.PHONY: test-hiphone test-ddingphone test-deliveryphone debug-ddingphone
.PHONY: test-phase3-step1 test-phase3-step2 test-phase3-step3 test-phase3-step4
.PHONY: test-phase3b-step1 test-phase3b-step2 test-ddingphone-api test-ddingphone-api3

# 기본 타겟
help:
	@echo "📋 사용 가능한 명령어:"
	@echo ""
	@echo "  make install              - 의존성 설치 및 Playwright 설정"
	@echo "  make test-phase1          - Phase 1 테스트 실행"
	@echo "  make test-phase2          - Phase 2 전체 테스트 실행"
	@echo "  make test-phase3          - Phase 3 전체 테스트 실행"
	@echo "  make test-all             - 모든 테스트 실행"
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
	@echo "  make debug-ddingphone     - 띵폰 페이지 디버깅"
	@echo "  make clean                - 캐시 및 임시 파일 정리"

# 의존성 설치
install:
	@echo "📦 의존성 설치 중..."
	uv sync
	@echo "🎭 Playwright 브라우저 설치 중..."
	uv run playwright install chromium

# Phase 1 테스트
test-phase1:
	@echo "🧪 Phase 1 테스트 실행 중..."
	uv run pytest tests/test_phase1.py -v

# Phase 2 전체 테스트
test-phase2:
	@echo "🧪 Phase 2 테스트 실행 중..."
	uv run pytest tests/test_phase2.py -v -s

# Phase 3 전체 테스트
test-phase3:
	@echo "🚀 Phase 3 전체 테스트 실행 중..."
	uv run pytest tests/test_phase3.py -v -s --tb=short

# Phase 3 Step 별 테스트
test-phase3-step1:
	@echo "🔍 Phase 3 Step 1: API 모니터링 기본 테스트"
	uv run pytest tests/test_phase3.py::test_api_monitor_basic -v -s --tb=short

test-phase3-step2:
	@echo "🤖 Phase 3 Step 2: LLM 기반 API 분석"
	uv run pytest tests/test_phase3.py::test_llm_api_analysis -v -s --tb=short

test-phase3-step3:
	@echo "🎮 Phase 3 Step 3: 인터랙션 후 API 모니터링"
	uv run pytest tests/test_phase3.py::test_api_monitor_with_manual_interaction -v -s --tb=short

test-phase3-step4:
	@echo "📊 Phase 3 Step 4: API 데이터 구조 분석"
	uv run pytest tests/test_phase3.py::test_api_data_structure -v -s --tb=short

# 띵폰 상세 분석
test-ddingphone-api:
	@echo "🔬 띵폰 API 상세 분석 (파일 저장)"
	uv run pytest tests/test_phase3_ddingphone.py::test_ddingphone_api_detailed_analysis -v -s --tb=short

test-ddingphone-api3:
	@echo "🔬 띵폰 API #3 심층 분석 (LLM)"
	uv run pytest tests/test_phase3_ddingphone.py::test_ddingphone_api3_deep_analysis -v -s --tb=short

# Phase 3B 테스트
test-phase3b-step1:
	@echo "🖥️ Phase 3B Step 1: 페이지 구조 분석"
	uv run pytest tests/test_phase3.py::test_screen_page_structure_analysis -v -s --tb=short

test-phase3b-step2:
	@echo "💰 Phase 3B Step 2: 화면 가격 추출"
	uv run pytest tests/test_phase3.py::test_screen_extract_pricing -v -s --tb=short

test-phase3b-step3:
	@echo "⚡ Phase 3B Step 3: 전체 플로우 (5개 조합)"
	uv run pytest tests/test_phase3.py::test_screen_collect_all_policies -v -s --tb=short

test-phase3b-full:
	@echo "🔥 Phase 3B Full: 전체 수집 (20개 조합)"
	uv run pytest tests/test_phase3.py::test_screen_full_collection -v -s --tb=short

test-phase3b-debug:
	@echo "🐛 Phase 3B 디버그: 옵션 추출 확인"
	uv run pytest tests/test_phase3b_debug.py::test_debug_options_extraction -v -s --tb=short

test-phase3b-manual:
	@echo "🎯 Phase 3B 수동: 정확한 셀렉터로 정책 수집"
	uv run pytest tests/test_phase3b_manual.py::test_ddingphone_manual_extraction -v -s --tb=short

test-phase3b-agent:
	@echo "🤖 Phase 3B Agent: LLM 추론 기반 정책 수집 (범용)"
	uv run pytest tests/test_phase3b_agent.py -v -s --tb=short

# 특정 사이트 테스트
test-hiphone:
	@echo "🧪 하이폰 리스팅 수집 테스트..."
	uv run pytest tests/test_phase2.py::test_listing_collection[하이폰] -v -s --tb=line

test-ddingphone:
	@echo "🧪 띵폰 리스팅 수집 테스트..."
	uv run pytest tests/test_phase2.py::test_listing_collection[띵폰] -v -s --tb=line

test-deliveryphone:
	@echo "🧪 딜리버리폰 리스팅 수집 테스트..."
	uv run pytest tests/test_phase2.py::test_listing_collection[딜리버리폰] -v -s --tb=line

# 모든 테스트 실행
test-all:
	@echo "🧪 전체 테스트 실행 중..."
	uv run pytest tests/ -v

# 간편 테스트 (test만 입력)
test: test-all

# 띵폰 디버깅
debug-ddingphone:
	@echo "🔍 띵폰 페이지 디버깅 중..."
	uv run python debug_ddingphone.py

# 정리
clean:
	@echo "🧹 캐시 및 임시 파일 정리 중..."
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ 정리 완료!"

