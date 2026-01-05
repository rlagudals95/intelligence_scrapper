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
from src.utils.detail_page_analyzer import DetailPageAnalyzer

# ============================================================================
# 테스트 URL
# ============================================================================
TEST_URLS = {
    "띵폰_갤럭시S25": "https://ddingphone.com/view/116?tid=KT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=K1596089921",
    "띵폰_아이폰17": "https://ddingphone.com/view/143?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1738389813",
    "하이폰_갤럭시S25": "https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337",
    "하이폰_아이폰17": "https://hi-phone.kr/index.php?channel=view&cate=103002000000&uid=10381",
}


test_name_and_url = ("하이폰_갤럭시S25", TEST_URLS["하이폰_갤럭시S25"])

# ============================================================================
# 공통 설정
# ============================================================================
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


# ============================================================================
# Step 1: 기본 정보 추출 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step1_extract_basic_info(site_name: str, test_url: str):
    """Step 1: 페이지 로드 및 기본 정보 추출"""
    print("\n" + "="*70)
    print(f"🧪 [Step 1] 기본 정보 추출 테스트: {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        result = await analyzer._step1_extract_basic_info(page, test_url)
        
        print("\n[Step 1 결과]")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step1_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장: {output_file}")
        
        assert result.get("product_name"), "제품명이 추출되지 않음"
        assert result.get("current_url"), "URL이 추출되지 않음"


# ============================================================================
# Step 2: 옵션 UI 분석 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step2_analyze_option_ui(site_name: str, test_url: str):
    """Step 2: Vision + HTML로 옵션 UI 분석"""
    print("\n" + "="*70)
    print(f"🧪 [Step 2] 옵션 UI 분석 테스트: {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        result = await analyzer._step2_analyze_option_ui(page)
        
        print("\n[Step 2 결과]")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step2_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장: {output_file}")
        
        # 검증
        print("\n[검증]")
        
    
        print(f"result 전체 확인: {result}")
        options = result.get('options', {})
        structure = result.get('structure', {})
        
        print(f"  [옵션 값]")
        print(f"    storage: {options.get('storage', 'N/A')}")
        print(f"    carrier: {options.get('carrier', 'N/A')}")
        print(f"    join_type: {options.get('join_type', 'N/A')}")
        print(f"    plan: {len(options.get('plan', []))}개" if isinstance(options.get('plan'), list) else f"    plan: {options.get('plan', 'N/A')}")
        
        print(f"  [선택자 구조]")
        structure_options = structure.get('options', {})
        print(f"    storage 선택자: {structure_options.get('storage', {}).get('selector', 'N/A')}")
        print(f"    carrier 선택자: {structure_options.get('carrier', {}).get('selector', 'N/A')}")
        print(f"    join_type 선택자: {structure_options.get('join_type', {}).get('selector', 'N/A')}")
        print(f"    plan 선택자: {structure_options.get('plan', {}).get('item_selector', 'N/A')}")


# ============================================================================
# Step 3: 옵션 값 추출 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step3_extract_option_values(site_name: str, test_url: str):
    """Step 3: 옵션 값 추출 및 검증"""
    print("\n" + "="*70)
    print(f"🧪 [Step 3] 옵션 값 추출 테스트: {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # Step 2 결과 먼저 가져오기
        step2_result = await analyzer._step2_analyze_option_ui(page)
        print("\n[Step 2 결과 (참고)]")
        print(json.dumps(step2_result, ensure_ascii=False, indent=2))
        
        # Step 3 실행
        result = await analyzer._step3_extract_option_values(page, step2_result)
        
        print("\n[Step 3 결과]")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step3_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장: {output_file}")


# ============================================================================
# Step 4: 옵션 조합 생성 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step4_generate_combinations(site_name: str, test_url: str):
    """Step 4: 옵션 조합 생성"""
    print("\n" + "="*70)
    print(f"🧪 [Step 4] 옵션 조합 생성 테스트: {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # Step 2, 3 결과 가져오기
        step2_result = await analyzer._step2_analyze_option_ui(page)
        step3_result = await analyzer._step3_extract_option_values(page, step2_result)
        
        print("\n[Step 3 결과 (입력)]")
        print(json.dumps(step3_result, ensure_ascii=False, indent=2))
        
        # Step 4 실행 (structure는 step2_result에서 가져옴)
        structure = step2_result.get("structure", {})
        result = await analyzer._step4_generate_combinations(step3_result, structure)
        
        print("\n[Step 4 결과]")
        print(f"  총 조합 수: {len(result)}개")
        
        for i, combo in enumerate(result):
            print(f"    [{i}] {combo}")
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step4_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장: {output_file}")
        
        assert len(result) > 0, "조합이 생성되지 않음"


# ============================================================================
# Step 5: 정책 추출 테스트 (첫 번째 조합만)
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step5_extract_policies_sample(site_name: str, test_url: str):
    """Step 5: 정책 추출 테스트 (샘플 조합 1개만)"""
    print("\n" + "="*70)
    print(f"🧪 [Step 5] 정책 추출 테스트 (샘플): {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # Step 1-4 결과 가져오기
        step1_result = await analyzer._step1_extract_basic_info(page, test_url)
        step2_result = await analyzer._step2_analyze_option_ui(page)
        step3_result = await analyzer._step3_extract_option_values(page, step2_result)
        
        # Step 4 실행 (structure는 step2_result에서 가져옴)
        structure = step2_result.get("structure", {})
        step4_result = await analyzer._step4_generate_combinations(step3_result, structure)
        
        print(f"\n[입력] 조합 수: {len(step4_result)}개")
        print(f"  샘플 조합 (첫 번째만 테스트): {step4_result[0]}")
        
        # 모든 조합 테스트
        sample_combinations = step4_result
        
        # Step 5 실행 (structure도 전달)
        result = await analyzer._step5_extract_policies(page, sample_combinations, step1_result, structure)
        
        print("\n[Step 5 결과]")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step5_sample_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 결과 저장: {output_file}")
        
        if result:
            print(f"\n[검증]")
            print(f"  성공: {result[0].get('success', False)}")
            if result[0].get('success'):
                print(f"  가격 정보: {result[0].get('pricing', {})}")


# ============================================================================
# Step 6: 결과 변환 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    test_name_and_url,
])
async def test_step6_convert_to_schema(site_name: str, test_url: str):
    """Step 6: 결과를 ScrapingResult 스키마로 변환"""
    print("\n" + "="*70)
    print(f"🧪 [Step 6] 결과 변환 테스트: {site_name}")
    print("="*70)
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # Step 1-5 결과 가져오기
        step1_result = await analyzer._step1_extract_basic_info(page, test_url)
        step2_result = await analyzer._step2_analyze_option_ui(page)
        step3_result = await analyzer._step3_extract_option_values(page, step2_result)
        step4_result = await analyzer._step4_generate_combinations(step3_result)
        
        # 첫 번째 조합만 테스트
        sample_combinations = [step4_result[0]]
        step5_result = await analyzer._step5_extract_policies(page, sample_combinations, step1_result)
        
        print(f"\n[입력] Step 5 결과: {len(step5_result)}개")
        
        # Step 6 실행
        site_domain = test_url.split("//")[-1].split("/")[0]
        result = await analyzer._step6_convert_to_schema(
            step5_result,
            test_url,
            site_domain,
            step1_result
        )
        
        print("\n[Step 6 결과]")
        print(f"  제품 수: {len(result.products)}")
        for product in result.products:
            print(f"    - {product.sku_code} ({product.sku_storage.value if product.sku_storage else 'N/A'})")
            print(f"      정책 수: {len(product.policies)}")
            if product.policies:
                for policy in product.policies[:2]:
                    print(f"        • {policy.carrier} / {policy.mno_join_type.value} / {policy.mobile_plan.name}")
        
        # 결과 저장
        output_dir = Path("output/detail_analyzer/steps")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"step6_{site_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 결과 저장: {output_file}")


# ============================================================================
# 전체 통합 테스트
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    # ("띵폰_갤럭시S25", TEST_URLS["띵폰_갤럭시S25"]),
    # ("띵폰_아이폰17", TEST_URLS["띵폰_아이폰17"]),
    ("하이폰_갤럭시S25", TEST_URLS["하이폰_갤럭시S25"]),
    # ("하이폰_아이폰17", TEST_URLS["하이폰_아이폰17"]),
])
async def test_detail_page_analyzer_full(site_name: str, test_url: str):
    """
    DetailPageAnalyzer 전체 통합 테스트
    
    모든 단계를 순차적으로 실행
    """
    print("\n" + "="*70)
    print(f"🧪 [전체 통합] DetailPageAnalyzer 테스트: {site_name}")
    print("="*70)
    print(f"URL: {test_url}")
    print("="*70 + "\n")
    
    llm_client = get_llm_client()
    analyzer = DetailPageAnalyzer(llm_client)
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        site_domain = test_url.split("//")[-1].split("/")[0]
        
        # 전체 분석 실행
        result = await analyzer.analyze_detail_page(
            page=page,
            url=test_url,
            site_name=site_domain
        )
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 최종 결과")
        print("="*70)
        print(f"사이트: {result.source.site}")
        print(f"캡처 시각: {result.captured_at}")
        print(f"제품 수: {len(result.products)}")
        
        for product in result.products:
            print(f"\n[제품]")
            print(f"  SKU: {product.sku_code}")
            print(f"  용량: {product.sku_storage.value if product.sku_storage else 'N/A'}")
            print(f"  정책 수: {len(product.policies)}")
            
            if product.policies:
                print(f"\n  정책 샘플 (최대 3개):")
                for i, policy in enumerate(product.policies[:3], 1):
                    print(f"    [{i}] {policy.carrier} / {policy.mno_join_type.value}")
                    if policy.pricing.mno_retail_price:
                        print(f"        출고가: {policy.pricing.mno_retail_price:,}원")
                    if policy.pricing.public_subsidy:
                        print(f"        공시지원금: {policy.pricing.public_subsidy:,}원")
                    if policy.pricing.discount:
                        print(f"        추가할인: {policy.pricing.discount:,}원")
                    if policy.mobile_plan.name:
                        print(f"        요금제: {policy.mobile_plan.name} ({policy.mobile_plan.monthly_fee:,}원/월)")
        
        # JSON 저장
        output_dir = Path("output/detail_analyzer")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{site_name}_{timestamp}.json"
        
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 JSON 저장: {output_file}")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"Provider: {stats['provider']}")
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        
        print("\n" + "="*70)
        print(f"✅ {site_name} 테스트 완료!")
        print("="*70 + "\n")
        
        # 검증
        assert len(result.products) > 0, f"{site_name}: 제품이 수집되지 않음"
        assert all(len(p.policies) > 0 for p in result.products), f"{site_name}: 정책이 없는 제품 존재"


if __name__ == "__main__":
    import sys
    
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print("⚠️  API 키가 설정되지 않았습니다")
        sys.exit(1)
    
    # 개별 테스트 실행 예시
    # asyncio.run(test_step1_extract_basic_info("띵폰_갤럭시S25", TEST_URLS["띵폰_갤럭시S25"]))
    # asyncio.run(test_step2_analyze_option_ui("띵폰_갤럭시S25", TEST_URLS["띵폰_갤럭시S25"]))
