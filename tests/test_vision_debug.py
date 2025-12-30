"""
Vision 디버그: 화면에 어떤 요금제가 보이는지 확인
"""
import pytest
import asyncio
import os
import base64
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider


TEST_URL = "https://uplustogethermall.com/mshop/view/60?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804"


@pytest.mark.asyncio
async def test_vision_see_plans():
    """Vision이 화면에서 어떤 요금제를 보는지 확인"""
    
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY 없음")
        return
    
    llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # 드롭다운 열기
        print("드롭다운 열기...")
        await page.evaluate("""
            document.querySelector('button.bill-view')?.click();
            document.querySelector('.bill-view-more')?.click();
        """)
        await asyncio.sleep(3)
        
        # 화면 캡처
        screenshot = await page.screenshot(full_page=False, quality=70, type='jpeg')
        screenshot_b64 = base64.b64encode(screenshot).decode()
        img_url = f"data:image/jpeg;base64,{screenshot_b64}"
        
        # Vision에게 물어보기
        prompt = """
이 화면에 어떤 요금제들이 보이나요?

모든 요금제와 월요금을 나열하세요:

[
  {"name": "프리미어 슈퍼", "monthly_fee": 115000},
  {"name": "프리미어 에센셜", "monthly_fee": 85000},
  {"name": "심플 플러스", "monthly_fee": 61000},
  ...
]

**화면에 보이는 모든 요금제를 추출하세요. JSON만 출력.**
"""
        
        resp = await llm_client.complete_with_vision(
            prompt=prompt,
            image_url=img_url,
            system_message="화면의 모든 요금제를 정확히 나열하세요."
        )
        
        print(f"\n{'='*70}")
        print("Vision이 본 요금제:")
        print(f"{'='*70}")
        print(resp)
        
        # 61,000원 확인
        if "61000" in resp or "61,000" in resp:
            print("\n✅ 61,000원 발견!")
        else:
            print("\n❌ 61,000원 없음")
        
        # 브라우저 확인
        print(f"\n⏸️  브라우저를 10초간 확인하세요...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(test_vision_see_plans())

