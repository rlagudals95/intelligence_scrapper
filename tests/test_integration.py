"""
통합 테스트: 리스팅 수집 → 필터링 → 상세 정책 수집
전체 파이프라인을 하나의 흐름으로 실행
"""
import pytest
import asyncio
import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.listing import ListingCrawler
from src.crawlers.llm_agent_extractor import LLMAgentExtractor
from src.models.schemas import PhoneListingItem


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


def detect_model_name(title: str, model_name_from_listing: str) -> str:
    """페이지 타이틀과 리스팅 정보로 기종명 판단"""
    title_upper = title.upper()
    model_upper = model_name_from_listing.upper()
    
    # 갤럭시 체크 (우선)
    if "갤럭시" in title or "GALAXY" in title_upper or "S25" in title_upper or "S25" in model_upper:
        if "S25" in title_upper or "S 25" in title_upper or "S25" in model_upper:
            return "GALAXY_S25"
        elif "S24" in title_upper or "S 24" in title_upper:
            return "GALAXY_S24"
        else:
            return "GALAXY_S25"  # 기본값
    # 아이폰 체크
    elif "아이폰" in title or "IPHONE" in title_upper or "IPHONE" in model_upper:
        if "17" in title or "17" in model_name_from_listing:
            return "IPHONE17"
        elif "16" in title or "16" in model_name_from_listing:
            return "IPHONE16"
        else:
            return "IPHONE17"  # 기본값
    else:
        return "UNKNOWN_MODEL"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("GEMINI_API_KEY"),
    reason="API 키 없음"
)
@pytest.mark.parametrize("site_name,listing_url,max_detail_pages", [
    # 테스트용으로 각 사이트당 최대 2개 상세페이지만 수집
    ("하이폰-삼성", "https://hi-phone.kr/index.php?channel=list&cate=103001000000", 2),
    ("띵폰-삼성", "https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90", 2),
    # 추가 사이트는 필요시 주석 해제
    # ("배달의폰-삼성", "https://www.deliveryphone.co.kr/phone/list/2", 2),
])
async def test_full_pipeline(site_name: str, listing_url: str, max_detail_pages: int):
    """
    전체 파이프라인 통합 테스트
    
    1. 리스팅 페이지에서 상품 목록 수집
    2. 갤럭시S25/아이폰17 필터링
    3. 각 상세 페이지에서 정책 수집
    4. 결과를 배열로 리턴
    """
    print("\n" + "="*80)
    print(f"🚀 통합 테스트: {site_name}")
    print("="*80)
    print(f"리스팅 URL: {listing_url}")
    print(f"최대 상세 페이지: {max_detail_pages}개")
    print("="*80 + "\n")
    
    # API 키 확인 및 LLM Client 초기화
    if os.getenv("GEMINI_API_KEY"):
        provider = LLMProvider.GEMINI
        model = "gemini-2.5-flash"
        llm_client = LLMClient(provider=provider, model=model)
    elif os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
        llm_client = LLMClient(provider=provider)
    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = LLMProvider.ANTHROPIC
        llm_client = LLMClient(provider=provider)
    else:
        pytest.skip("API 키 없음")
        return
    
    print(f"✅ LLM Client 초기화: {provider.value}\n")
    
    # 브라우저 설정
    config = SiteConfig(
        target_url=listing_url,
        headless=False,  # 디버깅을 위해 headless=False
        timeout=60000
    )
    
    # 최종 결과 배열
    all_results = []
    
    async with BrowserManager(config) as browser_manager:
        print("✅ 브라우저 시작\n")
        
        # ================================================================
        # Phase 1: 리스팅 페이지에서 상품 목록 수집
        # ================================================================
        print("[Phase 1] 리스팅 페이지 크롤링...")
        print("-" * 80)
        
        crawler = ListingCrawler(llm_client, browser_manager)
        all_items = await crawler.crawl(listing_url)
        
        print(f"✅ 전체 수집된 상품: {len(all_items)}개\n")
        
        # ================================================================
        # Phase 2: 갤럭시S25/아이폰17 필터링
        # ================================================================
        print("[Phase 2] 타겟 모델 필터링 (갤럭시S25/아이폰17)...")
        print("-" * 80)
        
        filtered_items = filter_target_models(all_items)
        
        print(f"✅ 필터링된 상품: {len(filtered_items)}개")
        for i, item in enumerate(filtered_items[:max_detail_pages], 1):
            print(f"  {i}. {item.model_name} - {item.detail_url[:60]}...")
        print()
        
        # 최대 개수 제한
        target_items = filtered_items[:max_detail_pages]
        
        if not target_items:
            print("⚠️  필터링된 상품이 없습니다. 테스트를 건너뜁니다.")
            pytest.skip("필터링된 상품 없음")
            return
        
        # ================================================================
        # Phase 3: 각 상세 페이지에서 정책 수집
        # ================================================================
        print(f"[Phase 3] 상세 정책 수집 ({len(target_items)}개 상품)...")
        print("-" * 80)
        
        page = await browser_manager.get_page()
        
        for idx, item in enumerate(target_items, 1):
            print(f"\n[{idx}/{len(target_items)}] {item.model_name} 처리 중...")
            print(f"URL: {item.detail_url}")
            
            try:
                # 상세 페이지 이동
                await page.goto(item.detail_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(2)
                
                page_title = await page.title()
                print(f"페이지 로드: {page_title}")
                
                # 기종명 감지
                model_name = detect_model_name(page_title, item.model_name)
                print(f"기종 감지: {model_name}")
                
                # LLM Agent로 정책 수집
                extractor = LLMAgentExtractor(llm_client, model_name=model_name)
                
                # 최대 10개 조합만 수집 (통합 테스트용)
                policies_result = await extractor.collect_all_policies(
                    page=page,
                    url=item.detail_url,
                    site_name=site_name,
                    max_combinations=10
                )
                
                # 결과 저장
                result_item = {
                    "index": idx,
                    "listing_info": {
                        "model_name": item.model_name,
                        "detail_url": item.detail_url,
                        "carrier": item.carrier,
                        "signup_type": item.signup_type,
                        "retail_price": item.retail_price,
                        "discount_price": item.discount_price,
                    },
                    "policies": policies_result,
                    "success": True,
                    "error": None
                }
                
                all_results.append(result_item)
                
                # 간단한 통계 출력
                total_policies = sum(len(p.policies) for p in policies_result.products)
                print(f"✅ 수집 완료: {len(policies_result.products)}개 제품, {total_policies}개 정책\n")
                
            except Exception as e:
                print(f"❌ 오류 발생: {str(e)}\n")
                
                # 오류도 기록
                result_item = {
                    "index": idx,
                    "listing_info": {
                        "model_name": item.model_name,
                        "detail_url": item.detail_url,
                    },
                    "policies": None,
                    "success": False,
                    "error": str(e)
                }
                
                all_results.append(result_item)
        
        # ================================================================
        # Phase 4: 결과 요약 및 저장
        # ================================================================
        print("\n" + "="*80)
        print("📊 통합 테스트 결과 요약")
        print("="*80)
        
        success_count = sum(1 for r in all_results if r["success"])
        fail_count = len(all_results) - success_count
        total_policies = sum(
            sum(len(p.policies) for p in r["policies"].products) 
            for r in all_results 
            if r["success"] and r["policies"]
        )
        
        print(f"사이트: {site_name}")
        print(f"처리된 상품: {len(all_results)}개")
        print(f"  성공: {success_count}개")
        print(f"  실패: {fail_count}개")
        print(f"총 수집된 정책: {total_policies}개")
        
        # JSON 저장
        output_dir = Path("output/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"pipeline_{site_name}_{timestamp}.json"
        
        # JSON 직렬화 가능한 형태로 변환
        json_data = {
            "site_name": site_name,
            "listing_url": listing_url,
            "captured_at": datetime.datetime.now().isoformat(),
            "summary": {
                "total_items": len(all_results),
                "success_count": success_count,
                "fail_count": fail_count,
                "total_policies": total_policies
            },
            "results": [
                {
                    "index": r["index"],
                    "listing_info": r["listing_info"],
                    "policies": r["policies"].model_dump(mode='json') if r["success"] and r["policies"] else None,
                    "success": r["success"],
                    "error": r["error"]
                }
                for r in all_results
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 JSON 저장: {output_file}")
        
        # LLM 사용량 통계
        stats = llm_client.get_usage_stats()
        print("\n" + "="*80)
        print("💰 LLM 사용량")
        print("="*80)
        print(f"Provider: {stats['provider']}")
        print(f"Model: {stats['model']}")
        print(f"총 요청: {stats['request_count']}회")
        print(f"총 토큰: {stats['total_tokens']:,} tokens")
        print(f"총 비용: ${stats['total_cost_usd']:.4f} USD")
        if success_count > 0:
            print(f"평균 비용/상품: ${stats['total_cost_usd'] / success_count:.4f} USD")
        
        print("\n" + "="*80)
        print(f"✅ {site_name} 통합 테스트 완료!")
        print("="*80 + "\n")
        
        # 검증
        assert len(all_results) > 0, "결과가 수집되지 않음"
        assert success_count > 0, "모든 상품에서 오류 발생"
        
        # 최종 결과 반환
        return all_results


# 단일 사이트 빠른 테스트용
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI API 키 없음"
)
async def test_single_site_quick():
    """
    단일 사이트 빠른 테스트 (개발/디버깅용)
    """
    result = await test_full_pipeline(
        site_name="하이폰-삼성",
        listing_url="https://hi-phone.kr/index.php?channel=list&cate=103001000000",
        max_detail_pages=1  # 1개만 테스트
    )
    
    assert result is not None
    assert len(result) > 0
    print(f"\n✅ 빠른 테스트 완료: {len(result)}개 상품 처리")


if __name__ == "__main__":
    import sys
    
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print("⚠️  API 키가 설정되지 않았습니다")
        sys.exit(1)
    
    # 빠른 테스트 실행
    asyncio.run(test_single_site_quick())

