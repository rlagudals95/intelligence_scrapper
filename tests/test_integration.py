"""
통합 테스트: 리스트 페이지 → 상세 페이지 → 정책 수집 → 슬랙 알림
"""
import pytest
import asyncio
import os
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.utils.list_page_analyzer import ListPageAnalyzer
from src.utils.detail_page_analyzer import DetailPageAnalyzer
from src.utils.slack_notifier import SlackNotifier
from src.utils.logger import get_logger

logger = get_logger()


# 테스트 대상 사이트 (띵폰 제외)
TEST_SITES = {
    "하이폰_삼성": "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
    "딜리버리폰_삼성": "https://www.deliveryphone.co.kr/phone/list/2",
    # "성지폰_삼성": "https://sungjiphone.com/phone/list/2",
    # "투게더몰_삼성": "https://uplustogethermall.com/section/samsung",
}


def get_llm_client():
    """LLM Client 생성"""
    if os.getenv("GEMINI_API_KEY"):
        provider = LLMProvider.GEMINI
        model = "gemini-2.5-flash"
    elif os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
        model = None
    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = LLMProvider.ANTHROPIC
        model = None
    else:
        pytest.skip("API 키 없음")
        return None
    
    return LLMClient(provider=provider, model=model) if model else LLMClient(provider=provider)


@pytest.mark.asyncio
async def test_integration_single_site():
    """단일 사이트 통합 테스트 (빠른 검증)"""
    print("\n" + "="*70)
    print("🧪 단일 사이트 통합 테스트")
    print("="*70 + "\n")
    
    site_name = "하이폰_삼성"
    list_url = TEST_SITES[site_name]
    
    start_time = time.time()
    
    # LLM 클라이언트
    llm_client = get_llm_client()
    
    # 1단계: URL 추출
    print(f"\n📋 [1단계] {site_name} 제품 URL 추출")
    print(f"   URL: {list_url}")
    
    list_analyzer = ListPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=list_url, headless=True, timeout=60000)
    
    async with BrowserManager(config) as browser:
        await browser.goto(list_url, wait_until="domcontentloaded")
        page = await browser.get_page()
        await asyncio.sleep(3)
        
        products = await list_analyzer.extract_product_urls(page, base_url=list_url)
        print(f"   ✅ {len(products)}개 제품 URL 추출 완료")
    
    # 2단계: 첫 번째 제품만 상세 분석
    if not products:
        print("   ⚠️  추출된 URL이 없어 테스트를 종료합니다.")
        return
    
    test_product = products[0]
    print(f"\n🔍 [2단계] 상세 페이지 분석")
    print(f"   제품: {test_product['name']}")
    print(f"   URL: {test_product['url']}")
    
    detail_analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_product['url'], headless=True, timeout=60000)
    
    async with BrowserManager(config) as browser:
        await browser.goto(test_product['url'], wait_until="domcontentloaded")
        page = await browser.get_page()
        await asyncio.sleep(3)
        
        result = await detail_analyzer.analyze_detail_page(
            page=page,
            url=test_product['url'],
            site_name=site_name
        )
        
        # 정책 수 계산
        total_policies = sum(len(p.policies) for p in result.products)
        print(f"   ✅ 제품 {len(result.products)}개, 정책 {total_policies}개 추출 완료")
    
    # 3단계: 결과 저장
    output_dir = Path("output/integration")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{site_name}_single_{timestamp}.json"
    
    json_data = result.model_dump(mode='json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 결과 저장: {output_file}")
    
    # 4단계: LLM 사용량
    duration = time.time() - start_time
    stats = llm_client.get_usage_stats()
    
    print("\n" + "="*70)
    print("📊 최종 결과")
    print("="*70)
    print(f"사이트: {site_name}")
    print(f"제품 URL: {len(products)}개")
    print(f"분석한 제품: 1개 (테스트)")
    print(f"추출 정책: {total_policies}개")
    print(f"소요 시간: {duration:.1f}초")
    print(f"LLM 요청: {stats['request_count']}회")
    print(f"LLM 토큰: {stats['total_tokens']:,} tokens")
    print(f"LLM 비용: ${stats['total_cost_usd']:.4f} USD")
    
    # 5단계: 슬랙 알림
    slack = SlackNotifier()
    await slack.send_scraping_result(
        site_name=site_name,
        success=True,
        product_count=1,
        policy_count=total_policies,
        duration_seconds=duration,
        details={
            "전체 제품 URL": f"{len(products)}개",
            "분석한 제품": "1개 (테스트)",
            "LLM 요청": f"{stats['request_count']}회"
        }
    )
    
    print("\n✅ 단일 사이트 통합 테스트 완료!")
    print("="*70 + "\n")


@pytest.mark.asyncio
async def test_integration_multi_sites():
    """다중 사이트 통합 테스트 (전체 파이프라인)"""
    print("\n" + "="*70)
    print("🚀 다중 사이트 통합 테스트")
    print("="*70 + "\n")
    
    overall_start = time.time()
    
    # LLM 클라이언트
    llm_client = get_llm_client()
    list_analyzer = ListPageAnalyzer(llm_client)
    detail_analyzer = DetailPageAnalyzer(llm_client)
    
    results = []
    
    for site_name, list_url in TEST_SITES.items():
        print(f"\n{'='*70}")
        print(f"🏢 [{site_name}] 처리 시작")
        print(f"{'='*70}")
        
        site_start = time.time()
        
        try:
            # 1단계: URL 추출
            print(f"\n📋 [1단계] 제품 URL 추출")
            print(f"   URL: {list_url}")
            
            config = SiteConfig(target_url=list_url, headless=True, timeout=60000)
            
            async with BrowserManager(config) as browser:
                await browser.goto(list_url, wait_until="domcontentloaded")
                page = await browser.get_page()
                await asyncio.sleep(3)
                
                products = await list_analyzer.extract_product_urls(page, base_url=list_url)
                print(f"   ✅ {len(products)}개 제품 URL 추출")
            
            if not products:
                print(f"   ⚠️  URL이 없어 건너뜀")
                results.append({
                    "site_name": site_name,
                    "success": False,
                    "product_count": 0,
                    "policy_count": 0,
                    "duration": time.time() - site_start,
                    "error": "제품 URL을 찾을 수 없음"
                })
                continue
            
            # 2단계: 첫 2개 제품만 분석 (테스트)
            test_products = products[:2]
            print(f"\n🔍 [2단계] 상세 페이지 분석 ({len(test_products)}개 제품)")
            
            all_policies = []
            
            for idx, product in enumerate(test_products, 1):
                print(f"\n   [{idx}/{len(test_products)}] {product['name']}")
                print(f"      {product['url']}")
                
                try:
                    config = SiteConfig(target_url=product['url'], headless=True, timeout=60000)
                    
                    async with BrowserManager(config) as browser:
                        await browser.goto(product['url'], wait_until="domcontentloaded")
                        page = await browser.get_page()
                        await asyncio.sleep(3)
                        
                        result = await detail_analyzer.analyze_detail_page(
                            page=page,
                            url=product['url'],
                            site_name=site_name
                        )
                        
                        policy_count = sum(len(p.policies) for p in result.products)
                        all_policies.append(result)
                        
                        print(f"      ✅ 정책 {policy_count}개 추출")
                        
                except Exception as e:
                    print(f"      ❌ 오류: {e}")
                    continue
            
            # 3단계: 결과 저장
            total_policies = sum(sum(len(p.policies) for p in r.products) for r in all_policies)
            
            output_dir = Path("output/integration")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"{site_name}_{timestamp}.json"
            
            # 모든 결과 통합
            combined_products = []
            for r in all_policies:
                combined_products.extend([p.model_dump(mode='json') for p in r.products])
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "site": site_name,
                    "url": list_url,
                    "captured_at": datetime.now().isoformat(),
                    "total_product_urls": len(products),
                    "analyzed_products": len(test_products),
                    "total_policies": total_policies,
                    "products": combined_products
                }, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"\n💾 결과 저장: {output_file}")
            
            # 슬랙 알림
            slack = SlackNotifier()
            await slack.send_scraping_result(
                site_name=site_name,
                success=True,
                product_count=len(test_products),
                policy_count=total_policies,
                duration_seconds=time.time() - site_start,
                details={
                    "전체 제품 URL": f"{len(products)}개",
                    "분석한 제품": f"{len(test_products)}개"
                }
            )
            
            results.append({
                "site_name": site_name,
                "success": True,
                "product_count": len(test_products),
                "policy_count": total_policies,
                "duration": time.time() - site_start,
                "total_urls": len(products)
            })
            
            print(f"\n✅ [{site_name}] 완료 ({time.time() - site_start:.1f}초)")
            
        except Exception as e:
            print(f"\n❌ [{site_name}] 실패: {e}")
            
            # 슬랙 알림
            slack = SlackNotifier()
            await slack.send_scraping_result(
                site_name=site_name,
                success=False,
                duration_seconds=time.time() - site_start,
                error_message=str(e)
            )
            
            results.append({
                "site_name": site_name,
                "success": False,
                "product_count": 0,
                "policy_count": 0,
                "duration": time.time() - site_start,
                "error": str(e)
            })
    
    # 전체 결과 요약
    overall_duration = time.time() - overall_start
    
    print("\n" + "="*70)
    print("📊 전체 결과 요약")
    print("="*70)
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['site_name']}: {result['product_count']}개 제품, {result['policy_count']}개 정책")
    
    total_products = sum(r['product_count'] for r in results)
    total_policies = sum(r['policy_count'] for r in results)
    success_count = sum(1 for r in results if r['success'])
    
    print(f"\n총 {success_count}/{len(results)} 사이트 성공")
    print(f"총 {total_products}개 제품 분석")
    print(f"총 {total_policies:,}개 정책 추출")
    print(f"전체 소요 시간: {overall_duration:.1f}초")
    
    # LLM 사용량
    stats = llm_client.get_usage_stats()
    print(f"\nLLM 요청: {stats['request_count']}회")
    print(f"LLM 토큰: {stats['total_tokens']:,} tokens")
    print(f"LLM 비용: ${stats['total_cost_usd']:.4f} USD")
    
    # 슬랙 통합 요약
    slack = SlackNotifier()
    await slack.send_integration_summary(
        results=results,
        total_duration=overall_duration,
        llm_stats=stats
    )
    
    print("\n✅ 다중 사이트 통합 테스트 완료!")
    print("="*70 + "\n")


if __name__ == "__main__":
    import sys
    
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print("⚠️  API 키가 설정되지 않았습니다")
        sys.exit(1)
    
    # 단일 사이트 테스트
    asyncio.run(test_integration_single_site())
    
    # 다중 사이트 테스트 (선택적)
    if "--multi" in sys.argv:
        asyncio.run(test_integration_multi_sites())

