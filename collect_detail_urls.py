"""
Phase 2 리스팅 크롤링으로 갤럭시 S25, 아이폰 17 상세 URL 수집
수집된 URL들을 JSON 파일로 저장하여 Phase 3에서 사용
"""
import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.listing import ListingCrawler


# PLAN.md의 리스팅 URL들
LISTING_URLS = {
    # 삼성전자 (갤럭시 S25)
    "하이폰_삼성": "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
    "띵폰_삼성": "https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
    "배달의폰_삼성": "https://www.deliveryphone.co.kr/phone/list/2",
    "성지폰_삼성": "https://sungjiphone.com/phone/list/2",
    "폰슐랭_삼성": "https://phonechelin.shop/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
    "엘지티샵_삼성": "https://lgtshop.co.kr/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
    "투게더몰_삼성": "https://uplustogethermall.com/section/samsung",
    "KT마켓_삼성": "https://ktmarket.co.kr/phone/samsung",
    
    # 아이폰
    "하이폰_아이폰": "https://hi-phone.kr/index.php?channel=list&cate=103002000000",
    "띵폰_아이폰": "https://ddingphone.com/list?sst=c&cid=APPLE",
    "배달의폰_아이폰": "https://www.deliveryphone.co.kr/phone/list/3",
    "성지폰_아이폰": "https://sungjiphone.com/phone/list/3",
    "폰슐랭_아이폰": "https://phonechelin.shop/mshop/list?sst=c&cid=APPLE",
    "엘지티샵_아이폰": "https://lgtshop.co.kr/mshop/list?sst=c&cid=APPLE",
    "투게더몰_아이폰": "https://uplustogethermall.com/section/apple",
    "KT마켓_아이폰": "https://ktmarket.co.kr/phone/apple",
}


def filter_target_models(items: list) -> list:
    """아이폰17과 갤럭시 S25 관련 상품만 필터링"""
    target_keywords = [
        # 아이폰 17 관련
        "아이폰 17", "아이폰17", "iphone 17", "iphone17",
        # 갤럭시 S25 관련  
        "갤럭시 s25", "갤럭시s25", "galaxy s25", "galaxys25", "s25"
    ]
    
    filtered_items = []
    for item in items:
        model_name_lower = item.model_name.lower()
        if any(keyword.lower() in model_name_lower for keyword in target_keywords):
            filtered_items.append(item)
    
    return filtered_items


async def collect_all_detail_urls():
    """모든 사이트에서 상세 URL 수집"""
    print("="*80)
    print("🔍 갤럭시 S25, 아이폰 17 상세 URL 수집 시작")
    print("="*80 + "\n")
    
    # LLM Client 초기화
    if os.getenv("GEMINI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
        print("✅ LLM: Gemini\n")
    elif os.getenv("OPENAI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.OPENAI)
        print("✅ LLM: OpenAI\n")
    else:
        print("❌ API 키 없음")
        return
    
    all_detail_urls = {}
    total_collected = 0
    
    for idx, (site_name, listing_url) in enumerate(LISTING_URLS.items(), 1):
        print(f"\n[{idx}/{len(LISTING_URLS)}] {site_name} 처리 중...")
        print(f"URL: {listing_url}")
        
        try:
            config = SiteConfig(
                target_url=listing_url,
                headless=True,
                timeout=60000
            )
            
            async with BrowserManager(config) as browser:
                crawler = ListingCrawler(llm_client, browser)
                
                # 리스팅 크롤링
                items = await crawler.crawl(listing_url)
                print(f"  📦 전체 수집: {len(items)}개")
                
                # 필터링
                filtered_items = filter_target_models(items)
                print(f"  🎯 필터링: {len(filtered_items)}개 (갤럭시S25/아이폰17)")
                
                if filtered_items:
                    # 상세 URL 저장
                    urls_data = []
                    for item in filtered_items:
                        urls_data.append({
                            "model_name": item.model_name,
                            "detail_url": item.detail_url,
                            "carrier": item.carrier,
                            "signup_type": item.signup_type
                        })
                        print(f"    - {item.model_name}: {item.detail_url[:60]}...")
                    
                    all_detail_urls[site_name] = {
                        "listing_url": listing_url,
                        "count": len(filtered_items),
                        "products": urls_data
                    }
                    total_collected += len(filtered_items)
                else:
                    print(f"  ⚠️  필터링된 상품 없음")
                    all_detail_urls[site_name] = {
                        "listing_url": listing_url,
                        "count": 0,
                        "products": []
                    }
        
        except Exception as e:
            print(f"  ❌ 오류: {str(e)}")
            all_detail_urls[site_name] = {
                "listing_url": listing_url,
                "error": str(e),
                "count": 0,
                "products": []
            }
    
    # 결과 저장
    output_dir = Path("output/integration")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"detail_urls_{timestamp}.json"
    
    result = {
        "collected_at": datetime.now().isoformat(),
        "total_sites": len(LISTING_URLS),
        "total_products": total_collected,
        "sites": all_detail_urls
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 요약 출력
    print("\n" + "="*80)
    print("📊 수집 결과 요약")
    print("="*80)
    print(f"총 사이트: {len(LISTING_URLS)}개")
    print(f"총 수집된 상품: {total_collected}개")
    
    success_sites = sum(1 for s in all_detail_urls.values() if s.get('count', 0) > 0)
    print(f"성공한 사이트: {success_sites}개")
    
    print(f"\n💾 저장 위치: {output_file}")
    
    # 사이트별 요약
    print("\n사이트별 수집 현황:")
    for site_name, data in all_detail_urls.items():
        count = data.get('count', 0)
        status = "✅" if count > 0 else "❌"
        print(f"  {status} {site_name}: {count}개")
    
    print("\n" + "="*80)
    print("✅ 수집 완료!")
    print("="*80)
    
    return result


if __name__ == "__main__":
    result = asyncio.run(collect_all_detail_urls())

