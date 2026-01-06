#!/usr/bin/env python3
"""요금제 추출 간단 테스트"""
import asyncio
from playwright.async_api import async_playwright
from src.core.llm_client import LLMClient
from src.utils.detail_page_analyzer import DetailPageAnalyzer
import json

async def test_site(site_name: str, url: str):
    print(f"\n{'='*70}")
    print(f"🧪 테스트: {site_name}")
    print(f"{'='*70}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 브라우저 console 메시지 캡처
        page.on("console", lambda msg: print(f"    [Browser Console] {msg.text}"))
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            llm = LLMClient()
            analyzer = DetailPageAnalyzer(llm)
            
            # Step 2만 테스트
            result = await analyzer._step2_analyze_option_ui(page)
            
            print(f"\n✅ 결과:")
            print(f"   용량: {result.get('options', {}).get('storage', 'N/A')}")
            print(f"   통신사: {result.get('options', {}).get('carrier', 'N/A')}")
            print(f"   가입유형: {result.get('options', {}).get('join_type', 'N/A')}")
            
            plans = result.get('options', {}).get('plan', [])
            print(f"   요금제: {len(plans)}개")
            for i, plan in enumerate(plans[:5], 1):
                print(f"      {i}. {plan.get('name', 'N/A')} - {plan.get('price', 'N/A')}원")
            
            # JSON 저장
            output_file = f"output/test_{site_name}_plan_extraction.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 저장: {output_file}")
            
        finally:
            await browser.close()

async def main():
    # 하이폰 테스트
    await test_site(
        "하이폰",
        "https://hi-phone.kr/shop/item.php?it_id=1736904092"
    )
    
    # 띵폰 테스트
    await test_site(
        "띵폰", 
        "https://ddingphone.com/view/143?code=S1738560449"
    )
    
    print("\n" + "="*70)
    print("테스트 완료!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())

