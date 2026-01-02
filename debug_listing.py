"""
리스팅 크롤러 디버깅
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.listing import ListingCrawler


async def main():
    url = "https://hi-phone.kr/index.php?channel=list&cate=103001000000"
    
    print(f"🧪 리스팅 크롤러 디버깅")
    print(f"URL: {url}\n")
    
    # LLM Client
    if os.getenv("GEMINI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
    elif os.getenv("OPENAI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.OPENAI)
    else:
        print("❌ API 키 없음")
        return
    
    # Browser
    config = SiteConfig(target_url=url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser:
        print("브라우저 시작...\n")
        
        page = await browser.get_page()
        await browser.goto(url)
        await asyncio.sleep(3)
        
        print(f"페이지 로드 완료: {await page.title()}\n")
        
        # PageAnalyzer로 구조 분석
        from src.utils.list_page_analyzer import PageAnalyzer
        analyzer = PageAnalyzer(llm_client)
        
        print("페이지 구조 분석 중...")
        page_structure = await analyzer.analyze_listing_page(page, use_screenshot=True)
        
        print(f"\n📊 페이지 구조 분석 결과:")
        print(f"  product_card_selector: {page_structure.get('product_card_selector')}")
        print(f"  product_name_selector: {page_structure.get('product_name_selector')}")
        print(f"  detail_link_selector: {page_structure.get('detail_link_selector')}")
        print(f"  pagination_type: {page_structure.get('pagination_type')}")
        
        # 실제 카드 개수 확인
        if page_structure.get('product_card_selector'):
            cards = await page.query_selector_all(page_structure['product_card_selector'])
            print(f"\n✅ 발견된 상품 카드: {len(cards)}개")
        else:
            print(f"\n❌ product_card_selector가 없습니다!")
            
        print("\n전체 구조:")
        import json
        print(json.dumps(page_structure, ensure_ascii=False, indent=2))
        
        print("\n" + "="*60)
        print("이제 ListingCrawler로 크롤링 시도...")
        print("="*60 + "\n")
        
        crawler = ListingCrawler(llm_client, browser)
        items = await crawler.crawl(url)
        
        print(f"\n✅ 수집된 상품: {len(items)}개\n")
        
        for i, item in enumerate(items[:5], 1):
            print(f"{i}. {item.model_name}")
            print(f"   URL: {item.detail_url[:60]}...")
            print()


if __name__ == "__main__":
    asyncio.run(main())

