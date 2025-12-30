"""
배달의폰 디버그
"""
import pytest
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager


TEST_URL = "https://www.deliveryphone.co.kr/phone/detail/136/0000412381"


@pytest.mark.asyncio
async def test_deliveryphone_debug():
    """배달의폰 HTML 저장 및 확인"""
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드: {await page.title()}\n")
        
        # popup 열기
        print("popup 열기...")
        await page.evaluate("""
            const link = document.querySelector('a[onclick*="popup"]');
            if (link) link.click();
        """)
        await asyncio.sleep(2)
        
        # HTML 저장
        html = await page.content()
        
        output_dir = Path("output/debug")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        html_file = output_dir / "deliveryphone_with_popup.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTML 저장: {html_file}")
        print(f"   크기: {len(html):,} bytes")
        
        # 89,000원 검색
        if "89,000" in html or "89000" in html:
            print("\n✅ 89,000원 발견!")
        else:
            print("\n❌ 89,000원 없음")
        
        # 79,000원 검색
        if "79,000" in html or "79000" in html:
            print("✅ 79,000원 발견!")
        else:
            print("❌ 79,000원 없음")


if __name__ == "__main__":
    asyncio.run(test_deliveryphone_debug())

