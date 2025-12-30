"""
요금제 선택 단계별 디버깅
"""
import pytest
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider


TEST_URL = "https://www.deliveryphone.co.kr/phone/detail/136/0000412381"


@pytest.mark.asyncio
async def test_step1_open_plan_selector():
    """
    Step 1: 요금제 선택 요소 클릭
    
    목표: 드롭다운/popup이 제대로 열리는지 확인
    """
    print("\n" + "="*70)
    print("🔍 Step 1: 요금제 선택 요소 클릭")
    print("="*70)
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # 요금제 관련 요소 찾기
        print("[1-1] 요금제 관련 요소 탐색")
        
        # "요금제" 텍스트가 있는 요소
        plan_elements = await page.locator('*:has-text("요금제")').all()
        print(f"  '요금제' 텍스트 요소: {len(plan_elements)}개")
        
        # onclick 속성이 있는 a 태그
        onclick_links = await page.locator('a[onclick]').all()
        print(f"  onclick 링크: {len(onclick_links)}개")
        
        for i, link in enumerate(onclick_links[:5], 1):
            onclick = await link.get_attribute('onclick')
            print(f"    [{i}] {onclick[:50]}...")
        
        # [1-2] 클릭 시도
        print(f"\n[1-2] 요금제 popup 열기")
        
        try:
            # popup 링크 클릭
            popup_link = page.locator('a[onclick*="popup"], a[onclick*="price"]')
            count = await popup_link.count()
            print(f"  popup 링크: {count}개")
            
            if count > 0:
                await popup_link.first.click(force=True)
                await asyncio.sleep(3)
                print(f"  ✅ 클릭 완료, 3초 대기")
        except Exception as e:
            print(f"  ❌ 클릭 실패: {e}")
        
        # [1-3] 결과 확인
        print(f"\n[1-3] popup 상태 확인")
        
        # popup 요소 확인
        popup_count = await page.locator('.popup, .modal').count()
        popup_visible = await page.locator('.popup:visible, .modal:visible').count()
        print(f"  popup 요소: {popup_count}개 (visible: {popup_visible}개)")
        
        # popup 내용 확인
        popup_html = await page.evaluate("""
            document.querySelector('.popup, .modal')?.innerHTML || ''
        """)
        print(f"  popup HTML: {len(popup_html)} bytes")
        
        # popup 내부 tr 확인
        tr_in_popup = await page.evaluate("""
            document.querySelectorAll('.popup tr, .modal tr').length
        """)
        print(f"  popup 내부 tr: {tr_in_popup}개")
        
        # 89,000원 존재 여부
        has_89000 = await page.evaluate("""
            document.body.innerHTML.includes('89,000') || document.body.innerHTML.includes('89000')
        """)
        print(f"  89,000원 존재: {has_89000}")
        
        # 브라우저 확인 시간
        print(f"\n⏸️  브라우저를 10초간 확인하세요...")
        await asyncio.sleep(10)
        
        print("\n" + "="*70)
        print("✅ Step 1 완료")
        print("="*70)


@pytest.mark.asyncio
async def test_step2_click_filtered_plan():
    """
    Step 2: 필터링 요금제 클릭
    
    목표: 89,000원 요금제를 찾아서 클릭하는지 확인
    """
    print("\n" + "="*70)
    print("🔍 Step 2: 필터링 요금제 클릭")
    print("="*70)
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # [2-1] popup 열기
        print("[2-1] popup 열기")
        await page.evaluate("""
            const link = document.querySelector('a[onclick*="popup"]');
            if (link) link.click();
        """)
        await asyncio.sleep(3)
        print("  ✅ popup 열기 완료\n")
        
        # [2-2] 89,000원 요금제 찾기
        print("[2-2] 89,000원 요금제 찾기")
        
        result = await page.evaluate("""
            const targetFee = 89000;
            const allRows = document.querySelectorAll('tr');
            
            let matches = [];
            
            for (const row of allRows) {
                const text = row.textContent;
                const feeMatches = text.match(/(\\d{1,3}),?(\\d{3})/g);
                
                if (feeMatches) {
                    for (const match of feeMatches) {
                        const fee = parseInt(match.replace(/,/g, ''));
                        if (fee === targetFee) {
                            matches.push({
                                text: text.substring(0, 100),
                                hasOnclick: !!row.getAttribute('onclick'),
                                onclick: row.getAttribute('onclick')?.substring(0, 50)
                            });
                        }
                    }
                }
            }
            
            return {
                searched: allRows.length,
                matches: matches
            };
        """)
        
        print(f"  검색 대상: {result['searched']}개 tr")
        print(f"  매칭: {len(result['matches'])}개")
        
        for i, match in enumerate(result['matches'], 1):
            print(f"\n  [{i}] {match['text']}")
            print(f"      onclick: {match['hasOnclick']}")
            if match['hasOnclick']:
                print(f"      코드: {match['onclick']}")
        
        # [2-3] 클릭 시도
        if result['matches']:
            print(f"\n[2-3] 첫 번째 매칭 클릭 시도")
            
            clicked = await page.evaluate("""
                const targetFee = 89000;
                const allRows = document.querySelectorAll('tr');
                
                for (const row of allRows) {
                    const text = row.textContent;
                    const feeMatches = text.match(/(\\d{1,3}),?(\\d{3})/g);
                    
                    if (feeMatches) {
                        for (const match of feeMatches) {
                            const fee = parseInt(match.replace(/,/g, ''));
                            if (fee === targetFee) {
                                const onclick = row.getAttribute('onclick');
                                if (onclick) {
                                    eval(onclick);
                                    return 'onclick 실행됨';
                                }
                                row.click();
                                return 'click 실행됨';
                            }
                        }
                    }
                }
                
                return '매칭 없음';
            """)
            
            print(f"  결과: {clicked}")
            await asyncio.sleep(2)
        
        print(f"\n⏸️  브라우저를 10초간 확인하세요...")
        await asyncio.sleep(10)
        
        print("\n" + "="*70)
        print("✅ Step 2 완료")
        print("="*70)


if __name__ == "__main__":
    # Step 1 먼저
    asyncio.run(test_step1_open_plan_selector())
    
    # Step 2
    # asyncio.run(test_step2_click_filtered_plan())

