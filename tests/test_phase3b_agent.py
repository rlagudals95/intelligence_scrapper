"""
Phase 3B: LLM Agent 기반 정책 수집 테스트
범용적으로 모든 사이트 지원
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
from src.crawlers.simple_detail_extractor import SimpleDetailExtractor


# 다양한 사이트 테스트 URL
TEST_URLS = {
    "띵폰_갤럭시S25": "https://ddingphone.com/view/116?tid=KT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=K1596089921",
    "띵폰_아이폰17": "https://ddingphone.com/view/143?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1738389813",
   
    "하이폰_갤럭시S25": "https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337",
    "하이폰_아이폰17": "https://hi-phone.kr/index.php?channel=view&cate=103002000000&uid=10381",
    
    "폰슐랭_갤럭시S25": "https://phonechelin.shop/mshop/view/53?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    "폰슐랭_아이폰17": "https://phonechelin.shop/mshop/view/74?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100686",
    
    "배달의폰_갤럭시S25": "https://www.deliveryphone.co.kr/phone/detail/136/0000412381",
    "배달의폰_아이폰17": "https://www.deliveryphone.co.kr/phone/detail/146/0000412381",
    
    "성지폰_갤럭시S25": "https://sungjiphone.com/phone/detail/166/0000700659",
    "성지폰_아이폰17": "https://sungjiphone.com/pㅔhone/detail/186/0000700659",

    "엘지티샵_갤럭시S25" : "https://lgtshop.co.kr/mshop/view/47?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    "엘지티샵_아이폰17" : "https://lgtshop.co.kr/mshop/view/64?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100686",

    "투게더몰_갤럭시S25" : "https://uplustogethermall.com/mshop/view/60?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    "투게더몰_아이폰17" : "https://uplustogethermall.com/mshop/view/84?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1594100804",
    

    "케이티마트_갤럭시S25" : "https://ktmarket.co.kr/phone/sm-s931nk", # 이거 페이지 구조 조금 별나네
    "케이티마트_아이폰17" : "https://ktmarket.co.kr/phone/aip17-256", # 이거 페이지 구조 조금 별나네
}


@pytest.mark.asyncio
@pytest.mark.parametrize("site_name,test_url", [
    # ("띵폰_갤럭시S25", TEST_URLS["띵폰_갤럭시S25"]),
    # ("띵폰_아이폰17", TEST_URLS["띵폰_아이폰17"]),
    # ("배달의폰_갤럭시S25", TEST_URLS["배달의폰_갤럭시S25"]),
    # ("배달의폰_아이폰17", TEST_URLS["배달의폰_아이폰17"]),
    # ("하이폰_갤럭시S25", TEST_URLS["하이폰_갤럭시S25"]),
    # ("하이폰_아이폰17", TEST_URLS["하이폰_아이폰17"]),
    ("폰슐랭_갤럭시S25", TEST_URLS["폰슐랭_갤럭시S25"]),
    # ("폰슐랭_아이폰17", TEST_URLS["폰슐랭_아이폰17"]),
    # ("성지폰_갤럭시S25", TEST_URLS["성지폰_갤럭시S25"]),
    # ("성지폰_아이폰17", TEST_URLS["성지폰_아이폰17"]),
    # ("엘지티샵_갤럭시S25", TEST_URLS["엘지티샵_갤럭시S25"]),
    # ("엘지티샵_아이폰17", TEST_URLS["엘지티샵_아이폰17"]),
    # ("투게더몰_갤럭시S25", TEST_URLS["투게더몰_갤럭시S25"]),
    # ("투게더몰_아이폰17", TEST_URLS["투게더몰_아이폰17"]),
    # ("케이티마트_갤럭시S25", TEST_URLS["케이티마트_갤럭시S25"]),
    # ("케이티마트_아이폰17", TEST_URLS["케이티마트_아이폰17"]),
])
async def test_llm_agent_collect_policies(site_name: str, test_url: str):
    """
    LLM Agent 기반 정책 수집 (범용)
    
    특징:
    - 사이트별 특수 셀렉터 불필요
    - LLM이 화면을 보고 옵션 추론
    - 텍스트 기반 요소 클릭
    """
    print("\n" + "="*70)
    print(f"🤖 LLM Agent 정책 수집: {site_name}")
    print("="*70)
    print(f"URL: {test_url}")
    print("="*70 + "\n")
    
    # API 키 확인
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
        return
    
    llm_client = LLMClient(provider=provider, model=model) if model else LLMClient(provider=provider)
    print(f"[1/3] LLM Client: {provider.value} ✅\n")
    
    config = SiteConfig(target_url=test_url, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        print("[2/3] 브라우저 시작 ✅\n")
        
        page = await browser_manager.get_page()
        
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료: {await page.title()}\n")
        
        # LLM Agent로 정책 수집
        print("[3/3] 정책 수집 시작...\n")
        
        # 기종명 판단 (URL 또는 페이지 타이틀에서)
        title = await page.title()
        title_upper = title.upper()
        
        # 갤럭시 체크 (우선)
        if "갤럭시" in title or "GALAXY" in title_upper or "S25" in title_upper or "S24" in title_upper:
            if "S25" in title_upper or "S 25" in title_upper:
                model_name = "GALAXY_S25"
            elif "S24" in title_upper or "S 24" in title_upper:
                model_name = "GALAXY_S24"
            else:
                model_name = "GALAXY_S25"  # 기본값
        # 아이폰 체크
        elif "아이폰" in title or "IPHONE" in title_upper:
            if "17" in title:
                model_name = "IPHONE17"
            elif "16" in title:
                model_name = "IPHONE16"
            else:
                model_name = "IPHONE17"  # 기본값
        else:
            model_name = "UNKNOWN_MODEL"
        
        print(f"   기종 감지: {model_name}\n")
        
        # SimpleDetailExtractor + VisionPlanAgent 사용
        extractor = SimpleDetailExtractor(llm_client, model_name=model_name)
        
        # 정책 수집 (모든 조합 시도)
        result = await extractor.collect_all_policies(
            page=page,
            url=test_url,
            site_name=site_name
        )
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 수집 결과")
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
                print(f"\n  정책 샘플:")
                for i, policy in enumerate(product.policies[:2], 1):
                    print(f"    [{i}] {policy.carrier} / {policy.mno_join_type.value}")
                    print(f"        출고가: {policy.pricing.mno_retail_price:,}원" if policy.pricing.mno_retail_price else "        출고가: N/A")
                    print(f"        할부원금: {policy.pricing.sku_installment_fee:,}원" if policy.pricing.sku_installment_fee else "        할부원금: N/A")
                    print(f"        월납부: {policy.pricing.monthly_payment:,}원" if policy.pricing.monthly_payment else "        월납부: N/A")
                    print(f"        요금제: {policy.mobile_plan.name} ({policy.mobile_plan.monthly_fee:,}원/월)")
        
        # JSON 저장
        output_dir = Path("output/phase3")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"policies_{site_name}_{timestamp}.json"
        
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 JSON 저장: {output_file}")
        
        # JSON 미리보기
        json_str = json.dumps(json_data, ensure_ascii=False, indent=2, default=str)
    
        print(json_str)
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"Provider: {stats['provider']}")
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        if stats['request_count'] > 0:
            print(f"평균/조합: ${stats['total_cost_usd'] / len(result.products[0].policies if result.products else [1]):.4f} USD")
        
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
    
    # 띵폰 테스트
    asyncio.run(test_llm_agent_collect_policies("띵폰", TEST_URLS["띵폰"]))

