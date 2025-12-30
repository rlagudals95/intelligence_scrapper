"""
통합 테스트 (간소화 버전): 상세 URL 직접 사용
test_phase3b_agent.py의 TEST_URLS를 사용하여 정책 수집
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


# test_phase3b_agent.py의 TEST_URLS + 아이폰17 추가
TEST_URLS = {
    # 갤럭시 S25
    "띵폰": "https://ddingphone.com/view/138?tid=SKT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=2&code=S1714617302",
    "하이폰": "https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337",
    "배달의폰": "https://www.deliveryphone.co.kr/phone/detail/136/0000412381",
    "성지폰": "https://sungjiphone.com/phone/detail/166/0000700659",
    "엘지티샵": "https://lgtshop.co.kr/mshop/view/47?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    "투게더몰": "https://uplustogethermall.com/mshop/view/84?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    "띵폰": "https://ddingphone.com/view/143?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1738389813",
    "하이폰": "https://hi-phone.kr/index.php?channel=view&cate=103002000000&uid=10400",  # 예시 URL
    "배달의폰": "https://www.deliveryphone.co.kr/phone/detail/136/0000412400",  # 예시 URL
}


def detect_model_name(title: str) -> str:
    """페이지 타이틀로 기종명 판단"""
    title_upper = title.upper()
    
    if "S25" in title_upper or "S 25" in title_upper:
        return "GALAXY_S25"
    elif "S24" in title_upper:
        return "GALAXY_S24"
    elif "17" in title:
        return "IPHONE17"
    elif "16" in title:
        return "IPHONE16"
    else:
        return "GALAXY_S25"  # 기본값


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
@pytest.mark.parametrize("site_name,detail_url", [
    # 테스트용으로 일부만 선택
    ("배달의폰_갤럭시S25", TEST_URLS["배달의폰_갤럭시S25"]),
    ("하이폰_갤럭시S25", TEST_URLS["하이폰_갤럭시S25"]),
    # 추가 사이트는 필요시 주석 해제
    # ("띵폰_갤럭시S25", TEST_URLS["띵폰_갤럭시S25"]),
    # ("성지폰_갤럭시S25", TEST_URLS["성지폰_갤럭시S25"]),
])
async def test_collect_policies_from_urls(site_name: str, detail_url: str):
    """
    상세 URL 배열에서 정책 수집
    
    리스팅 크롤링 없이 직접 상세 페이지 URL로 이동하여 정책 수집
    """
    print("\n" + "="*80)
    print(f"🎯 정책 수집: {site_name}")
    print("="*80)
    print(f"URL: {detail_url}")
    print("="*80 + "\n")
    
    # LLM Client 초기화
    if os.getenv("GEMINI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
        print(f"✅ LLM: Gemini\n")
    elif os.getenv("OPENAI_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.OPENAI)
        print(f"✅ LLM: OpenAI\n")
    elif os.getenv("ANTHROPIC_API_KEY"):
        llm_client = LLMClient(provider=LLMProvider.ANTHROPIC)
        print(f"✅ LLM: Anthropic\n")
    else:
        pytest.skip("API 키 없음")
        return
    
    # 브라우저 설정
    config = SiteConfig(
        target_url=detail_url,
        headless=False,
        timeout=60000
    )
    
    result = None
    
    async with BrowserManager(config) as browser_manager:
        print("✅ 브라우저 시작\n")
        
        page = await browser_manager.get_page()
        
        # 상세 페이지 이동
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        
        page_title = await page.title()
        print(f"✅ 페이지 로드: {page_title}\n")
        
        # 기종명 감지
        model_name = detect_model_name(page_title)
        print(f"   기종 감지: {model_name}\n")
        
        # LLM Agent로 정책 수집
        print("[정책 수집 시작...]")
        print("-" * 80)
        
        extractor = LLMAgentExtractor(llm_client, model_name=model_name)
        
        # 최대 30개 조합 수집 (용량×색상×통신사×가입유형×요금제)
        # 실제로는 더 적을 수 있음 (LLM이 대표 조합만 선택)
        policies_result = await extractor.collect_all_policies(
            page=page,
            url=detail_url,
            site_name=site_name,
            max_combinations=30
        )
        
        result = policies_result
        
        # 결과 요약
        print("\n" + "="*80)
        print("📊 수집 결과")
        print("="*80)
        print(f"사이트: {site_name}")
        print(f"제품 수: {len(result.products)}")
        
        total_policies = sum(len(p.policies) for p in result.products)
        print(f"총 정책 수: {total_policies}")
        
        if result.products:
            for product in result.products:
                print(f"\n[제품] SKU: {product.sku_code}")
                print(f"  용량: {product.sku_storage.value if product.sku_storage else 'N/A'}")
                print(f"  정책 수: {len(product.policies)}")
                
                if product.policies:
                    print(f"  정책 샘플 (처음 2개):")
                    for i, policy in enumerate(product.policies[:2], 1):
                        print(f"    [{i}] {policy.carrier} / {policy.mno_join_type.value}")
                        print(f"        요금제: {policy.mobile_plan.name} ({policy.mobile_plan.monthly_fee:,}원/월)")
                        if policy.pricing.monthly_payment:
                            print(f"        월납부: {policy.pricing.monthly_payment:,}원")
        
        # JSON 저장
        output_dir = Path("output/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{site_name}_{timestamp}.json"
        
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 JSON 저장: {output_file}")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*80)
        print("💰 LLM 사용량")
        print("="*80)
        print(f"Provider: {stats['provider']}")
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        
        print("\n" + "="*80)
        print(f"✅ {site_name} 테스트 완료!")
        print("="*80 + "\n")
        
        # 검증
        assert len(result.products) > 0, f"{site_name}: 제품이 수집되지 않음"
        assert total_policies > 0, f"{site_name}: 정책이 수집되지 않음"
        
        return result


# 여러 사이트 한번에 테스트
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI API 키 없음"
)
async def test_collect_multiple_sites():
    """
    여러 사이트에서 정책 수집하여 배열로 반환
    최종 결과를 통합 JSON 파일로 저장
    """
    print("\n" + "="*80)
    print("🚀 다중 사이트 정책 수집")
    print("="*80 + "\n")
    
    # 테스트할 사이트 목록 (각 사이트의 갤럭시 S25 + 아이폰 17)
    sites_to_test = [
        ("배달의폰_갤럭시S25", TEST_URLS["배달의폰_갤럭시S25"]),
        ("배달의폰_아이폰17", TEST_URLS["배달의폰_아이폰17"]),
        ("하이폰_갤럭시S25", TEST_URLS["하이폰_갤럭시S25"]),
        ("하이폰_아이폰17", TEST_URLS["하이폰_아이폰17"]),
    ]
    
    all_results = []
    collected_policies = []  # 통합 JSON용 배열
    
    for idx, (site_name, detail_url) in enumerate(sites_to_test, 1):
        print(f"\n[{idx}/{len(sites_to_test)}] {site_name} 처리 중...")
        
        try:
            result = await test_collect_policies_from_urls(site_name, detail_url)
            all_results.append({
                "site_name": site_name,
                "url": detail_url,
                "result": result,
                "success": True
            })
            
            # 통합 JSON용 데이터 추가 (사용자가 원하는 형태)
            if result:
                policy_data = {
                    "captured_at": result.captured_at,
                    "source": {
                        "site": result.source.site,
                        "url": result.source.url
                    },
                    "products": []
                }
                
                # products 변환
                for product in result.products:
                    product_dict = {
                        "product_id": product.product_id,
                        "sku_code": product.sku_code,
                        "sku_storage": product.sku_storage.value if product.sku_storage else None,
                        "policies": [],
                        "product_name": product.product_name,
                        "product_color": product.product_color
                    }
                    
                    # policies 변환
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
                    
                    policy_data["products"].append(product_dict)
                
                collected_policies.append(policy_data)
                
        except Exception as e:
            print(f"❌ 오류: {str(e)}")
            all_results.append({
                "site_name": site_name,
                "url": detail_url,
                "result": None,
                "success": False,
                "error": str(e)
            })
    
    # 최종 요약
    print("\n" + "="*80)
    print("📊 전체 수집 결과")
    print("="*80)
    
    success_count = sum(1 for r in all_results if r["success"])
    print(f"처리된 사이트: {len(all_results)}개")
    print(f"성공: {success_count}개")
    print(f"실패: {len(all_results) - success_count}개")
    
    for r in all_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['site_name']}")
    
    # 통합 JSON 저장
    if collected_policies:
        output_dir = Path("output/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"all_sites_policies_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collected_policies, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 통합 JSON 저장: {output_file}")
        print(f"   총 사이트: {len(collected_policies)}개")
        
        total_products = sum(len(p["products"]) for p in collected_policies)
        total_policies = sum(
            len(prod["policies"]) 
            for p in collected_policies 
            for prod in p["products"]
        )
        print(f"   총 제품: {total_products}개")
        print(f"   총 정책: {total_policies}개")
    
    print("="*80 + "\n")
    
    # 결과 반환
    return collected_policies  # 배열 반환


# 모든 사이트 테스트 (전체)
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI API 키 없음"
)
async def test_collect_all_sites():
    """
    TEST_URLS의 모든 사이트에서 정책 수집
    """
    print("\n" + "="*80)
    print("🌐 전체 사이트 정책 수집")
    print("="*80 + "\n")
    
    # 모든 사이트 테스트
    sites_to_test = list(TEST_URLS.items())
    
    collected_policies = []
    success_count = 0
    fail_count = 0
    
    for idx, (site_name, detail_url) in enumerate(sites_to_test, 1):
        print(f"\n[{idx}/{len(sites_to_test)}] {site_name} 처리 중...")
        print(f"URL: {detail_url[:80]}...")
        
        try:
            result = await test_collect_policies_from_urls(site_name, detail_url)
            
            if result:
                # 통합 JSON용 데이터 변환
                policy_data = {
                    "captured_at": result.captured_at,
                    "source": {
                        "site": result.source.site,
                        "url": result.source.url
                    },
                    "products": []
                }
                
                for product in result.products:
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
                    
                    policy_data["products"].append(product_dict)
                
                collected_policies.append(policy_data)
                success_count += 1
                print(f"✅ {site_name} 완료")
                
        except Exception as e:
            fail_count += 1
            print(f"❌ {site_name} 실패: {str(e)}")
    
    # 최종 요약
    print("\n" + "="*80)
    print("📊 전체 수집 결과")
    print("="*80)
    print(f"총 사이트: {len(sites_to_test)}개")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")
    
    # 통합 JSON 저장
    if collected_policies:
        output_dir = Path("output/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"all_sites_policies_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collected_policies, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 통합 JSON 저장: {output_file}")
        print(f"   총 사이트: {len(collected_policies)}개")
        
        total_products = sum(len(p["products"]) for p in collected_policies)
        total_policies = sum(
            len(prod["policies"]) 
            for p in collected_policies 
            for prod in p["products"]
        )
        print(f"   총 제품: {total_products}개")
        print(f"   총 정책: {total_policies}개")
        
        # JSON 미리보기
        print(f"\n📄 JSON 미리보기 (처음 100줄):")
        print("="*80)
        json_str = json.dumps(collected_policies, ensure_ascii=False, indent=2, default=str)
        lines = json_str.split('\n')
        for line in lines[:100]:
            print(line)
        if len(lines) > 100:
            print(f"... (생략: 총 {len(lines)}줄)")
    
    print("\n" + "="*80)
    print(f"✅ 전체 수집 완료!")
    print("="*80 + "\n")
    
    return collected_policies


if __name__ == "__main__":
    import sys
    
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        print("⚠️  API 키가 설정되지 않았습니다")
        sys.exit(1)
    
    # 다중 사이트 테스트 실행
    results = asyncio.run(test_collect_multiple_sites())
    print(f"\n✅ 수집 완료: {len(results)}개 사이트")

