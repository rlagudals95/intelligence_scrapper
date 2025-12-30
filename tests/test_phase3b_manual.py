"""
Phase 3B: 수동 셀렉터로 정책 수집 테스트
실제 HTML 구조를 파악한 정확한 셀렉터 사용
"""
import pytest
import asyncio
import os
import json
import datetime
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.screen_extractor import ScreenExtractor
from src.models.phase3_schemas import (
    ScrapingResult, Product, Policy, MobilePlan, PricingDetails,
    SourceInfo, JoinType, DiscountType, parse_storage
)


TEST_URL = "https://ddingphone.com/view/138?tid=SKT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=2&code=S1714617302"


@pytest.mark.asyncio
async def test_ddingphone_manual_extraction():
    """
    띵폰 사이트 수동 셀렉터 기반 정책 수집
    
    실제 HTML 구조 기반 정확한 셀렉터 사용:
    - 용량: input[name="opt_giga"]
    - 색상: a.circle_color
    - 가입유형: input[name="item_ordtype"]
    - 요금제: .bill-box li
    """
    print("\n" + "="*70)
    print("🚀 띵폰 수동 셀렉터 기반 정책 수집")
    print("="*70)
    print(f"URL: {TEST_URL}")
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
    print(f"[1/6] LLM Client 초기화 완료 ({provider.value}) ✅\n")
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        print("[2/6] 브라우저 시작 완료 ✅\n")
        
        page = await browser_manager.get_page()
        
        print("[3/6] 페이지 이동 중...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        print(f"✅ 페이지 로드 완료\n")
        
        # Step 1: 선택 가능한 옵션 추출 (수동 셀렉터)
        print("[4/6] 옵션 추출 중... (수동 셀렉터)\n")
        
        # 용량
        storage_radios = await page.locator('input[name="opt_giga"]').all()
        storages = []
        for radio in storage_radios:
            data_name = await radio.get_attribute("data-name")
            if data_name:
                storages.append(data_name)
        print(f"  ✅ 용량: {storages}")
        
        # 색상  
        color_links = await page.locator('a.circle_color').all()
        colors = []
        for link in color_links:
            data_color = await link.get_attribute("data-color")
            if data_color:
                colors.append(data_color)
        print(f"  ✅ 색상: {colors}")
        
        # 가입유형
        join_radios = await page.locator('input[name="item_ordtype"]').all()
        join_types = []
        for radio in join_radios:
            value = await radio.get_attribute("value")
            if value:
                join_types.append(value)
        print(f"  ✅ 가입유형: {join_types}")
        
        # 통신사 (사용하실 통신사)
        carrier_radios = await page.locator('input[name="item_telecom"]').all()
        carriers = []
        for radio in carrier_radios:
            value = await radio.get_attribute("value")
            if value:
                carriers.append(value)
        print(f"  ✅ 통신사: {carriers}")
        
        # Step 2: 조합 생성 (간단히)
        print(f"\n[5/6] 조합 생성 중...\n")
        
        # 첫 용량, 첫 색상, 모든 가입유형 (2개 조합만)
        combinations = []
        if storages and colors and join_types:
            for join_type in join_types[:2]:  # 2개만
                combo = {
                    "storage": storages[0],
                    "color": colors[0],
                    "join_type": join_type,
                    "carrier": "SKT"  # 고정
                }
                combinations.append(combo)
        
        print(f"  ✅ 생성된 조합: {len(combinations)}개")
        for idx, combo in enumerate(combinations, 1):
            print(f"     [{idx}] {combo}")
        
        # Step 3: 각 조합별 정책 수집
        print(f"\n[6/6] 정책 수집 중...\n")
        
        extractor = ScreenExtractor(llm_client)
        collected_policies = []
        
        for idx, combo in enumerate(combinations, 1):
            print(f"  [{idx}/{len(combinations)}] 조합 처리: {combo['join_type']}")
            
            try:
                # 옵션 선택
                # 가입유형만 변경 (용량, 색상은 이미 선택됨)
                # label을 클릭 (radio는 label에 가려서 클릭 안 됨)
                label = page.locator(f'label[for="item_ordtype_{2 if combo["join_type"]=="번호이동" else 3}"]')
                await label.click(force=True, timeout=5000)
                await asyncio.sleep(2)
                
                # 가격 추출 (Vision API)
                pricing = await extractor.extract_pricing(page, use_vision=True)
                
                # Policy 생성
                policy_id = hashlib.md5(str(combo).encode()).hexdigest()[:16]
                
                # JoinType 파싱
                if combo["join_type"] == "번호이동":
                    join_type = JoinType.NUMBER_TRANSFER
                elif combo["join_type"] == "기기변경":
                    join_type = JoinType.DEVICE_CHANGE
                else:
                    join_type = JoinType.DEVICE_CHANGE
                
                policy = Policy(
                    policy_id=policy_id,
                    carrier=combo["carrier"],
                    mno_join_type=join_type,
                    mobile_plan=MobilePlan(
                        name=pricing.get("plan_name", "알 수 없음"),
                        monthly_fee=pricing.get("plan_monthly_fee", 0) or 0
                    ),
                    discount_type=DiscountType.PUBLIC_SUBSIDY,
                    pricing=PricingDetails(
                        mno_retail_price=pricing.get("retail_price"),
                        public_subsidy=pricing.get("public_subsidy"),
                        discount=pricing.get("additional_subsidy"),
                        sku_installment_fee=pricing.get("installment_principal"),
                        monthly_payment=pricing.get("monthly_payment")
                    )
                )
                
                collected_policies.append({
                    "combo": combo,
                    "policy": policy
                })
                
                print(f"    ✅ 정책 수집 완료")
                print(f"       출고가: {pricing.get('retail_price'):,}원" if pricing.get('retail_price') else "       출고가: N/A")
                print(f"       할부원금: {pricing.get('installment_principal'):,}원" if pricing.get('installment_principal') else "       할부원금: N/A")
                print(f"       월납부: {pricing.get('final_price'):,}원" if pricing.get('final_price') else "       월납부: N/A")
                
            except Exception as e:
                print(f"    ❌ 실패: {e}")
                import traceback
                traceback.print_exc()
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 수집 결과")
        print("="*70)
        print(f"수집된 정책: {len(collected_policies)}개\n")
        
        if collected_policies:
            # Product 생성
            product = Product(
                product_id=hashlib.md5(f"띵폰_{storages[0]}".encode()).hexdigest()[:16],
                sku_code="아이폰 17 Pro Max",
                sku_storage=parse_storage(storages[0]),
                policies=[p["policy"] for p in collected_policies]
            )
            
            # ScrapingResult 생성
            result = ScrapingResult(
                captured_at=datetime.datetime.now(),
                source=SourceInfo(site="띵폰", url=TEST_URL),
                products=[product]
            )
            
            # JSON 저장
            output_dir = Path("output/phase3")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"policies_manual_{timestamp}.json"
            
            json_data = result.model_dump(mode='json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"💾 JSON 저장: {output_file}\n")
            
            # JSON 미리보기
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2, default=str)
            print("📄 JSON 미리보기:")
            print(json_str[:800] + "...")
            
            # 검증
            assert len(result.products) > 0, "제품이 수집되지 않음"
            assert len(result.products[0].policies) > 0, "정책이 수집되지 않음"
            
            print(f"\n✅ 검증 통과: {len(result.products)}개 제품, {len(result.products[0].policies)}개 정책")
        
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
        print("✅ 수동 셀렉터 기반 정책 수집 완료!")
        print("="*70 + "\n")


@pytest.mark.asyncio
async def test_gemini_vision_simple():
    """
    Gemini Vision API 간단한 테스트
    """
    print("\n" + "="*70)
    print("🧪 Gemini Vision API 테스트")
    print("="*70 + "\n")
    
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY 없음")
        return
    
    llm_client = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # 스크린샷
        import base64
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
        image_url = f"data:image/png;base64,{screenshot_base64}"
        
        print("스크린샷 캡처 완료")
        print(f"크기: {len(screenshot_base64)} bytes\n")
        
        # Vision API 호출
        try:
            prompt = """
이 이미지에서 다음 정보를 찾으세요:
1. 출고가 (숫자)
2. 할부원금 (숫자)
3. 월 납부금액 (숫자)
4. 요금제 이름

JSON 형식으로 반환하세요:
{
  "retail_price": 숫자,
  "installment_principal": 숫자,
  "final_price": 숫자,
  "plan_name": "이름"
}
"""
            
            print("Vision API 호출 중...")
            response = await llm_client.complete_with_vision(
                prompt=prompt,
                image_url=image_url,
                system_message="이미지에서 가격 정보를 추출하세요."
            )
            
            print(f"\n✅ Vision API 응답:")
            print(response)
            
        except Exception as e:
            print(f"\n❌ Vision API 실패: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ddingphone_manual_extraction())

