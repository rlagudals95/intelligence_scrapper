.PHONY: help install test test-phase1 test-phase2 test-all clean
.PHONY: test-hiphone test-ddingphone test-deliveryphone debug-ddingphone

# 기본 타겟
help:
	@echo "📋 사용 가능한 명령어:"
	@echo ""
	@echo "  make install              - 의존성 설치 및 Playwright 설정"
	@echo "  make test-phase1          - Phase 1 테스트 실행"
	@echo "  make test-phase2          - Phase 2 전체 테스트 실행"
	@echo "  make test-all             - 모든 테스트 실행"
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

