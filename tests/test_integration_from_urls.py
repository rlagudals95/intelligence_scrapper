"""
통합 테스트: collect_detail_urls.py에서 수집한 URL들로 정책 수집
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
from src.crawlers.llm_agent_extractor import LLMAgentExtractor


def load_detail_urls(json_file: str) -> list:
    """수집된 상세 URL JSON 파일 로드"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 모든 사이트의 상품 URL을 하나의 배열로 변환
    all_urls = []
    for site_name, site_data in data['sites'].items():
        if site_data['count'] > 0:
            for product in site_data['products']:
                all_urls.append({
                    "site_name": site_name,
                    "model_name": product['model_name'],
                    "detail_url": product['detail_url'],
                    "listing_url": site_data['listing_url']
                })
    
    return all_urls


def detect_model_name(title: str, model_name_from_listing: str) -> str:
    """페이지 타이틀과 리스팅 정보로 기종명 판단"""
    title_upper = title.upper()
    model_upper = model_name_from_listing.upper()
    
    # 갤럭시 체크 (우선)
    if "갤럭시" in title or "GALAXY" in title_upper or "S25" in title_upper or "S25" in model_upper:
        if "S25" in title_upper or "S 25" in title_upper or "S25" in model_upper:
            return "GALAXY_S25"
        elif "S24" in title_upper:
            return "GALAXY_S24"
        else:
            return "GALAXY_S25"  # 기본값
    # 아이폰 체크
    elif "아이폰" in title or "IPHONE" in title_upper or "IPHONE" in model_upper or "17" in model_name_from_listing:
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
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI API 키 없음"
)
async def test_collect_all_from_urls():
    """
    수집된 17개 상세 URL에서 모든 정책 수집
    """
    print("\n" + "="*80)
    print("🌐 Phase 2에서 수집한 URL로 전체 정책 수집")
    print("="*80 + "\n")
    
    # 가장 최근 detail_urls JSON 파일 찾기
    integration_dir = Path("output/integration")
    detail_url_files = sorted(integration_dir.glob("detail_urls_*.json"), reverse=True)
    
    if not detail_url_files:
        print("❌ detail_urls JSON 파일을 찾을 수 없습니다.")
        print("먼저 'make collect-urls'를 실행하세요.")
        pytest.skip("detail_urls 파일 없음")
        return
    
    latest_file = detail_url_files[0]
    print(f"📂 로드할 파일: {latest_file}")
    
    # URL 로드
    all_urls = load_detail_urls(latest_file)
    print(f"✅ 총 {len(all_urls)}개 상세 URL 로드\n")
    
    # LLM Client 초기화
    llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
    print(f"✅ LLM: Gemini\n")
    
    # 전체 정책 수집
    collected_policies = []
    success_count = 0
    fail_count = 0
    
    for idx, url_info in enumerate(all_urls, 1):
        site_name = url_info['site_name']
        model_name = url_info['model_name']
        detail_url = url_info['detail_url']
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(all_urls)}] {site_name} - {model_name}")
        print(f"{'='*80}")
        print(f"URL: {detail_url}\n")
        
        try:
            config = SiteConfig(
                target_url=detail_url,
                headless=True,
                timeout=60000
            )
            
            async with BrowserManager(config) as browser_manager:
                page = await browser_manager.get_page()
                
                # 페이지 이동
                await page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(2)
                
                page_title = await page.title()
                print(f"✅ 페이지 로드: {page_title}\n")
                
                # 기종명 감지
                detected_model = detect_model_name(page_title, model_name)
                print(f"   기종 감지: {detected_model}\n")
                
                # LLM Agent로 정책 수집
                print("[정책 수집 시작...]")
                
                extractor = LLMAgentExtractor(llm_client, model_name=detected_model)
                
                # 최대 30개 조합 수집
                policies_result = await extractor.collect_all_policies(
                    page=page,
                    url=detail_url,
                    site_name=site_name,
                    max_combinations=30
                )
                
                # 결과 변환
                policy_data = {
                    "captured_at": policies_result.captured_at,
                    "source": {
                        "site": policies_result.source.site,
                        "url": policies_result.source.url,
                        "model_name_from_listing": model_name
                    },
                    "products": []
                }
                
                total_policies_count = 0
                for product in policies_result.products:
                    product_dict = {
                        "product_id": product.product_id,
                        "sku_code": product.sku_code,
                        "sku_storage": product.sku_storage.value if product.sku_storage else None,
                        "policies": [],
                        "product_name": product.product_name,
                        "product_color": product.product_color
                    }
                    
                    for policy in product.policies:
                        policy_dict = {
                            "policy_id": policy.policy_id,
                            "carrier": policy.carrier,
                            "mno_join_type": policy.mno_join_type.value,
                            "mobile_plan": {
                                "name": policy.mobile_plan.name,
                                "monthly_fee": policy.mobile_plan.monthly_fee
                            },
                            "discount_type": policy.discount_type.value if policy.discount_type else None,
                            "pricing": {
                                "mno_retail_price": policy.pricing.mno_retail_price,
                                "public_subsidy": policy.pricing.public_subsidy,
                                "discount": policy.pricing.discount,
                                "sku_installment_fee": policy.pricing.sku_installment_fee,
                                "monthly_payment": policy.pricing.monthly_payment
                            },
                            "addons": policy.addons,
                            "policy_text": policy.policy_text
                        }
                        product_dict["policies"].append(policy_dict)
                        total_policies_count += 1
                    
                    policy_data["products"].append(product_dict)
                
                collected_policies.append(policy_data)
                success_count += 1
                
                print(f"\n✅ 수집 완료:")
                print(f"   제품: {len(policy_data['products'])}개")
                print(f"   정책: {total_policies_count}개")
                
        except Exception as e:
            fail_count += 1
            print(f"\n❌ 실패: {str(e)}")
    
    # 최종 요약
    print("\n" + "="*80)
    print("📊 전체 수집 결과")
    print("="*80)
    print(f"총 URL: {len(all_urls)}개")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")
    
    total_products = sum(len(p["products"]) for p in collected_policies)
    total_policies = sum(
        len(prod["policies"]) 
        for p in collected_policies 
        for prod in p["products"]
    )
    print(f"\n수집된 데이터:")
    print(f"  총 사이트: {len(collected_policies)}개")
    print(f"  총 제품: {total_products}개")
    print(f"  총 정책: {total_policies}개")
    
    # 통합 JSON 저장
    if collected_policies:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = integration_dir / f"all_policies_from_urls_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collected_policies, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 통합 JSON 저장: {output_file}")
    
    # LLM 사용량
    stats = llm_client.get_usage_stats()
    print("\n" + "="*80)
    print("💰 LLM 사용량")
    print("="*80)
    print(f"Provider: {stats['provider']}")
    print(f"요청: {stats['request_count']}회")
    print(f"토큰: {stats['total_tokens']:,} tokens")
    print(f"비용: ${stats['total_cost_usd']:.4f} USD")
    if success_count > 0:
        print(f"평균/제품: ${stats['total_cost_usd'] / success_count:.4f} USD")
    
    print("\n" + "="*80)
    print(f"✅ 전체 수집 완료!")
    print("="*80 + "\n")
    
    # 검증
    assert len(collected_policies) > 0, "정책이 수집되지 않음"
    assert success_count > 0, "모든 URL에서 실패"
    
    return collected_policies


if __name__ == "__main__":
    import sys
    
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY가 설정되지 않았습니다")
        sys.exit(1)
    
    results = asyncio.run(test_collect_all_from_urls())
    print(f"\n✅ 최종 수집: {len(results)}개 사이트")

