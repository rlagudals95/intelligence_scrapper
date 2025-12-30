"""
Pytest Configuration and Fixtures
Phase 3용 테스트 설정
"""
import os
import pytest
import pytest_asyncio
import asyncio
from playwright.async_api import async_playwright


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def playwright_instance():
    """Playwright instance"""
    async with async_playwright() as p:
        yield p


@pytest_asyncio.fixture(scope="session")
async def browser(playwright_instance):
    """
    Playwright browser fixture
    
    Phase 3 기본 설정: 브라우저 항상 보이기 (디버깅용)
    """
    # Phase 3에서는 항상 브라우저를 보여줌
    headless = False
    
    print(f"\n{'='*70}")
    print(f"🌐 브라우저 설정")
    print(f"{'='*70}")
    print(f"  • Headless: {headless} (보임 👀)")
    print(f"  • 브라우저 실행 시도 중...")
    print(f"{'='*70}\n")
    
    try:
        print("⏳ Chromium 실행 중... (10초 이내)")
        
        browser = await playwright_instance.chromium.launch(
            headless=headless,
            slow_mo=0,  # 디버깅 시 100으로 변경
            timeout=10000  # 10초 타임아웃
        )
        
        print("✅ 브라우저 실행 성공!\n")
        
        yield browser
        
        print("\n🔄 브라우저 종료 중...")
        await browser.close()
        print("✅ 브라우저 종료 완료\n")
        
    except Exception as e:
        print(f"\n❌ 브라우저 실행 실패: {e}")
        print(f"   원인: Playwright 브라우저가 설치되지 않았을 수 있습니다")
        print(f"   해결: python -m playwright install chromium")
        raise
