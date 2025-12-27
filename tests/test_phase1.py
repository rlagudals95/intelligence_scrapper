"""
Phase 1 테스트: 핵심 인프라
"""
import pytest
import asyncio
from pathlib import Path
import json

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.state import StateManager
from src.utils.logger import get_logger, setup_logger
from src.utils.delay import random_delay, fixed_delay


# ============================================================================
# Config 테스트
# ============================================================================

def test_config_creation():
    """SiteConfig 생성 테스트"""
    config = SiteConfig(
        target_url="https://example.com",
        delay_min=1.0,
        delay_max=3.0,
        pruning_threshold=3
    )
    
    assert config.target_url == "https://example.com"
    assert config.listing_url == "https://example.com"  # 자동 설정
    assert config.delay_min == 1.0
    assert config.delay_max == 3.0
    assert config.pruning_threshold == 3
    print("✅ Config 생성 테스트 통과")


def test_config_validation():
    """SiteConfig 검증 테스트"""
    # delay_min > delay_max 오류
    with pytest.raises(ValueError):
        SiteConfig(
            target_url="https://example.com",
            delay_min=5.0,
            delay_max=3.0
        )
    
    # pruning_threshold < 1 오류
    with pytest.raises(ValueError):
        SiteConfig(
            target_url="https://example.com",
            pruning_threshold=0
        )
    
    print("✅ Config 검증 테스트 통과")


# ============================================================================
# State Manager 테스트
# ============================================================================

def test_state_manager_basic():
    """StateManager 기본 기능 테스트"""
    state_file = "checkpoints/test_state.json"
    
    # 기존 파일 삭제
    if Path(state_file).exists():
        Path(state_file).unlink()
    
    state = StateManager(state_file)
    
    # URL 방문 테스트
    url = "https://example.com/product1"
    assert not state.is_url_visited(url)
    
    state.mark_url_visited(url)
    assert state.is_url_visited(url)
    
    # 옵션 상태 테스트
    options = {"color": "red", "size": "large"}
    assert not state.is_state_visited(url, options)
    
    state.mark_state_visited(url, options)
    assert state.is_state_visited(url, options)
    
    print("✅ StateManager 기본 기능 테스트 통과")


def test_state_manager_persistence():
    """StateManager 영속화 테스트"""
    state_file = "checkpoints/test_state_persist.json"
    
    # 기존 파일 삭제
    if Path(state_file).exists():
        Path(state_file).unlink()
    
    # 첫 번째 인스턴스: 데이터 저장
    state1 = StateManager(state_file)
    state1.mark_url_visited("https://example.com/product1")
    state1.mark_url_visited("https://example.com/product2")
    state1.save()
    
    # 두 번째 인스턴스: 데이터 로드
    state2 = StateManager(state_file)
    assert state2.is_url_visited("https://example.com/product1")
    assert state2.is_url_visited("https://example.com/product2")
    assert not state2.is_url_visited("https://example.com/product3")
    
    print("✅ StateManager 영속화 테스트 통과")


def test_state_hash_consistency():
    """State 해시 일관성 테스트"""
    url = "https://example.com/product"
    options1 = {"color": "red", "size": "large"}
    options2 = {"size": "large", "color": "red"}  # 순서 다름
    
    hash1 = StateManager.hash_state(url, options1)
    hash2 = StateManager.hash_state(url, options2)
    
    # 순서가 달라도 같은 해시
    assert hash1 == hash2
    
    # 다른 옵션은 다른 해시
    options3 = {"color": "blue", "size": "large"}
    hash3 = StateManager.hash_state(url, options3)
    assert hash1 != hash3
    
    print("✅ State 해시 일관성 테스트 통과")


# ============================================================================
# Browser Manager 테스트
# ============================================================================

@pytest.mark.asyncio
async def test_browser_manager_lifecycle():
    """BrowserManager 생명주기 테스트"""
    config = SiteConfig(
        target_url="https://example.com",
        headless=False
    )
    
    browser = BrowserManager(config)
    
    # 시작
    await browser.start()
    page = await browser.get_page()
    assert page is not None
    
    # 종료
    await browser.close()
    print("✅ BrowserManager 생명주기 테스트 통과")


@pytest.mark.asyncio
async def test_browser_manager_navigation():
    """BrowserManager 네비게이션 테스트"""
    config = SiteConfig(
        target_url="https://example.com",
        headless=False,
        timeout=10000
    )
    
    async with BrowserManager(config) as browser:
        # 페이지 이동
        await browser.goto("https://example.com")
        page = await browser.get_page()
        
        # 페이지 타이틀 확인
        title = await page.title()
        assert title is not None
        
        print(f"✅ 페이지 로딩 성공: {title}")


@pytest.mark.asyncio
async def test_browser_manager_new_page():
    """BrowserManager 새 페이지 생성 테스트"""
    config = SiteConfig(
        target_url="https://example.com",
        headless=False
    )
    
    async with BrowserManager(config) as browser:
        page1 = await browser.get_page()
        page2 = await browser.new_page()
        
        assert page1 != page2
        print("✅ 새 페이지 생성 테스트 통과")


# ============================================================================
# Logger 테스트
# ============================================================================

def test_logger_creation():
    """Logger 생성 테스트"""
    logger = get_logger("test_logger")
    assert logger is not None
    
    # 로그 출력 테스트
    logger.info("테스트 로그 메시지", test_key="test_value")
    logger.debug("디버그 메시지")
    logger.warning("경고 메시지")
    
    print("✅ Logger 생성 및 출력 테스트 통과")


# ============================================================================
# Delay 테스트
# ============================================================================

@pytest.mark.asyncio
async def test_random_delay():
    """랜덤 딜레이 테스트"""
    import time
    
    start = time.time()
    await random_delay(0.1, 0.3)
    elapsed = time.time() - start
    
    assert 0.1 <= elapsed <= 0.4  # 약간의 여유
    print(f"✅ 랜덤 딜레이 테스트 통과 ({elapsed:.2f}초)")


@pytest.mark.asyncio
async def test_fixed_delay():
    """고정 딜레이 테스트"""
    import time
    
    start = time.time()
    await fixed_delay(0.2)
    elapsed = time.time() - start
    
    assert 0.2 <= elapsed <= 0.3
    print(f"✅ 고정 딜레이 테스트 통과 ({elapsed:.2f}초)")


# ============================================================================
# 통합 테스트
# ============================================================================

@pytest.mark.asyncio
async def test_phase1_integration():
    """Phase 1 통합 테스트"""
    print("\n" + "="*60)
    print("Phase 1 통합 테스트 시작")
    print("="*60)
    
    # 1. Config 생성
    config = SiteConfig(
        target_url="https://example.com",
        delay_min=0.1,
        delay_max=0.3,
        headless=False
    )
    print("✅ 1. Config 생성 완료")
    
    # 2. State Manager 생성
    state = StateManager("checkpoints/test_integration_state.json")
    print("✅ 2. StateManager 생성 완료")
    
    # 3. Logger 생성
    logger = get_logger("integration_test")
    logger.info("통합 테스트 시작")
    print("✅ 3. Logger 생성 완료")
    
    # 4. Browser Manager 테스트
    async with BrowserManager(config) as browser:
        await browser.goto("https://example.com")
        
        # URL 방문 기록
        state.mark_url_visited("https://example.com")
        assert state.is_url_visited("https://example.com")
        
        # 딜레이
        await random_delay(0.1, 0.2)
        
        print("✅ 4. Browser + State + Delay 통합 완료")
    
    # 5. State 저장
    state.save()
    print("✅ 5. State 저장 완료")
    
    print("="*60)
    print("✅ Phase 1 통합 테스트 성공!")
    print("="*60)


# ============================================================================
# 실제 대상 사이트 테스트 (LLM 없이 기본 검증만)
# ============================================================================

@pytest.mark.asyncio
async def test_target_site_hiphone():
    """하이폰 사이트 - 휴대폰 리스트 페이지 검증"""
    print("\n" + "="*60)
    print("하이폰 사이트 검증")
    print("="*60)
    
    target_url = "https://hi-phone.kr/index.php?channel=list&cate=103001000000"
    
    config = SiteConfig(
        target_url=target_url,
        delay_min=1.0,
        delay_max=2.0,
        headless=False,
        timeout=60000
    )
    print(f"✅ 1. Config 생성: {target_url}")
    
    async with BrowserManager(config) as browser:
        await browser.goto(target_url, wait_until="domcontentloaded")
        page = await browser.get_page()
        
        # 페이지 렌더링 대기
        await asyncio.sleep(3)
        
        # 2. 페이지 로드 확인
        title = await page.title()
        print(f"✅ 2. 페이지 로드 완료: {title}")
        
        # 3. HTML 내용 확인
        html = await page.content()
        
        # 4. 휴대폰 관련 키워드 확인
        phone_keywords = ["갤럭시", "아이폰", "Galaxy", "iPhone", "휴대폰", "스마트폰"]
        found_keywords = [kw for kw in phone_keywords if kw in html or kw in title]
        print(f"✅ 3. 휴대폰 관련 키워드 발견: {found_keywords}")
        
        # 5. 링크 개수 확인 (리스트 페이지인지)
        links = await page.query_selector_all("a")
        print(f"✅ 4. 페이지 내 링크 수: {len(links)}개")
        
        # 6. 검증
        assert len(found_keywords) > 0, "휴대폰 관련 키워드를 찾을 수 없습니다"
        assert len(links) > 10, "리스트 페이지로 보이지 않습니다 (링크 수 부족)"
        
        print("\n" + "="*60)
        print("✅ 하이폰 사이트 검증 완료 - 휴대폰 리스트 페이지 확인")
        print("="*60)


@pytest.mark.asyncio
async def test_target_site_ddingphone():
    """띵폰 사이트 - 휴대폰 리스트 페이지 검증"""
    print("\n" + "="*60)
    print("띵폰 사이트 검증")
    print("="*60)
    
    target_url = "https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90"
    
    config = SiteConfig(
        target_url=target_url,
        delay_min=1.0,
        delay_max=2.0,
        headless=False,
        timeout=60000
    )
    print(f"✅ 1. Config 생성: {target_url}")
    
    async with BrowserManager(config) as browser:
        await browser.goto(target_url, wait_until="domcontentloaded")
        page = await browser.get_page()
        
        # 페이지 렌더링 대기
        await asyncio.sleep(3)
        
        # 2. 페이지 로드 확인
        title = await page.title()
        print(f"✅ 2. 페이지 로드 완료: {title}")
        
        # 3. HTML 내용 확인
        html = await page.content()
        
        # 4. 휴대폰 관련 키워드 확인
        phone_keywords = ["갤럭시", "아이폰", "Galaxy", "iPhone", "휴대폰", "스마트폰", "삼성"]
        found_keywords = [kw for kw in phone_keywords if kw in html or kw in title]
        print(f"✅ 3. 휴대폰 관련 키워드 발견: {found_keywords}")
        
        # 5. 링크 개수 확인 (리스트 페이지인지)
        links = await page.query_selector_all("a")
        print(f"✅ 4. 페이지 내 링크 수: {len(links)}개")
        
        # 6. 검증
        assert len(found_keywords) > 0, "휴대폰 관련 키워드를 찾을 수 없습니다"
        assert len(links) > 10, "리스트 페이지로 보이지 않습니다 (링크 수 부족)"
        
        print("\n" + "="*60)
        print("✅ 띵폰 사이트 검증 완료 - 휴대폰 리스트 페이지 확인")
        print("="*60)


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("\n🧪 Phase 1 테스트 실행\n")
    
    # 동기 테스트
    test_config_creation()
    test_config_validation()
    test_state_manager_basic()
    test_state_manager_persistence()
    test_state_hash_consistency()
    test_logger_creation()
    
    # 비동기 테스트
    asyncio.run(test_random_delay())
    asyncio.run(test_fixed_delay())
    asyncio.run(test_browser_manager_lifecycle())
    asyncio.run(test_browser_manager_navigation())
    asyncio.run(test_browser_manager_new_page())
    
    # 통합 테스트
    asyncio.run(test_phase1_integration())
    
    # 실제 대상 사이트 테스트 (선택적)
    if "--real-sites" in sys.argv:
        print("\n🌐 실제 대상 사이트 테스트 시작\n")
        asyncio.run(test_target_site_hiphone())
        asyncio.run(test_target_site_ddingphone())
    
    print("\n✅ 모든 Phase 1 테스트 통과!\n")

