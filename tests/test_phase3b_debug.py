"""
Phase 3B 디버그 테스트
"""
import pytest
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.screen_extractor import ScreenExtractor


TEST_URL = "https://hi-phone.kr/index.php?channel=view&uid=10381&cate=108000000000"


@pytest.mark.asyncio
async def test_debug_options_extraction():
    """
    디버그: 옵션 추출 상세 확인
    """
    print("\n" + "="*70)
    print("🐛 디버그: 옵션 추출 확인")
    print("="*70 + "\n")
    
    # API 키 확인 - Gemini 우선
    if os.getenv("GEMINI_API_KEY"):
        provider = LLMProvider.GEMINI
        model = "gemini-3.0-flash-preview"
        print(f"✨ Gemini API 사용: {model}")
    elif os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
        model = None  # 기본 모델 사용
        print(f"🤖 OpenAI API 사용")
    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = LLMProvider.ANTHROPIC
        model = None
        print(f"🤖 Anthropic API 사용")
    else:
        pytest.skip("API 키 없음")
        return
    
    llm_client = LLMClient(provider=provider, model=model) if model else LLMClient(provider=provider)
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        extractor = ScreenExtractor(llm_client)
        
        # Step 1: 페이지 구조 분석
        print("[Step 1] 페이지 구조 분석...")
        structure = await extractor.analyze_page_structure(page)
        
        print("\n📊 분석된 구조:")
        import json
        print(json.dumps(structure, ensure_ascii=False, indent=2))
        
        # Step 2: 실제 HTML에서 셀렉터 확인
        print("\n[Step 2] 셀렉터 검증...")
        
        for option_type, option_info in structure.get("options", {}).items():
            selector = option_info.get("selector")
            ui_type = option_info.get("type")
            
            print(f"\n{option_type} ({ui_type}):")
            print(f"  셀렉터: {selector}")
            
            try:
                elements = await page.locator(selector).all()
                print(f"  발견된 요소: {len(elements)}개")
                
                if elements:
                    # 첫 번째 요소의 정보 출력
                    first_elem = elements[0]
                    text = await first_elem.text_content()
                    tag = await first_elem.evaluate("el => el.tagName")
                    print(f"  첫 번째 요소:")
                    print(f"    - 태그: {tag}")
                    print(f"    - 텍스트: {text[:50]}...")
                    
                    if ui_type == "select":
                        # select의 option들 확인
                        options = await page.locator(f"{selector} option").all_text_contents()
                        print(f"    - 옵션 개수: {len(options)}")
                        print(f"    - 옵션: {options}")
                else:
                    print(f"  ⚠️  요소를 찾을 수 없음!")
                    
            except Exception as e:
                print(f"  ❌ 오류: {e}")
        
        # Step 3: 선택 가능한 옵션 추출
        print("\n[Step 3] 선택 가능한 옵션 추출...")
        available = await extractor.get_available_options(page, structure)
        
        print(f"\n✅ 추출된 옵션:")
        print(json.dumps(available, ensure_ascii=False, indent=2))
        
        if not available:
            print("\n⚠️  옵션이 추출되지 않았습니다!")
            print("   → 페이지 구조 분석이 정확하지 않을 수 있습니다")
            print("   → 셀렉터가 실제 HTML 구조와 맞지 않을 수 있습니다")


@pytest.mark.asyncio
async def test_save_html_for_analysis():
    """
    디버그: HTML 파일 저장
    """
    print("\n" + "="*70)
    print("🐛 디버그: HTML 파일 저장")
    print("="*70 + "\n")
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # HTML 저장
        html = await page.content()
        
        from pathlib import Path
        output_dir = Path("output/debug")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        html_file = output_dir / "ddingphone_page.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTML 저장 완료: {html_file}")
        print(f"   크기: {len(html):,} bytes")
        print(f"\n💡 이 파일을 열어서 실제 HTML 구조를 확인하세요")
        print(f"   옵션 선택 UI를 찾아서 정확한 셀렉터를 파악할 수 있습니다")


if __name__ == "__main__":
    asyncio.run(test_debug_options_extraction())

