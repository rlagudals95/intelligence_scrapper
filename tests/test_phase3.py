"""
Phase 3 테스트: 상세페이지 옵션 정책 수집
Step 1: API 모니터링 기본 테스트
"""
import pytest
import asyncio
import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.api_monitor import APIMonitor
from src.crawlers.screen_extractor import ScreenExtractor
from src.models.phase3_schemas import ScrapingResult


# 테스트 URL
TEST_URL_HIPHONE = "https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337"
TEST_URL_DDINGPHONE = "https://ddingphone.com/view/138?tid=SKT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=2&code=S1714617302"

# 기본 테스트 URL (띵폰 - API가 명확한 사이트)
TEST_URL = TEST_URL_DDINGPHONE


@pytest.mark.asyncio
async def test_api_monitor_basic():
    """
    Step 1: API 모니터링 기본 테스트
    
    목적:
    - 브라우저가 제대로 뜨는지 확인
    - 페이지 로드 시 API 호출이 캡처되는지 확인
    - API 모니터 기본 기능 검증
    """
    print("\n" + "="*70)
    print("🚀 Phase 3 Step 1: API 모니터링 기본 테스트")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    # 브라우저 설정 (headless=False로 브라우저 보이게)
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,  # 브라우저 보이기
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        print("[1/5] 브라우저 시작 완료 ✅\n")
        
        # 페이지 가져오기
        page = await browser_manager.get_page()
        print("[2/5] 페이지 객체 획득 ✅\n")
        
        # API 모니터 시작
        monitor = APIMonitor()
        monitor.start_monitoring(page)
        print("[3/5] API 모니터 시작 완료 ✅\n")
        
        # 페이지 이동
        print(f"[4/5] 페이지 이동 중...")
        print(f"       URL: {TEST_URL}")
        print(f"       브라우저를 확인하세요 👀\n")
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        
        print(f"✅ 페이지 로드 완료")
        print(f"   Title: {await page.title()}\n")
        
        # API 호출 대기
        print("⏳ API 호출 대기 중... (5초)")
        await asyncio.sleep(5)
        
        # API 통계 확인
        print("[5/5] API 호출 분석\n")
        stats = monitor.get_stats()
        
        print(f"📊 캡처된 API 통계:")
        print(f"   • 총 호출: {stats['total_calls']}개")
        print(f"   • 고유 URL: {stats['unique_urls']}개")
        print(f"   • GET: {stats['methods']['GET']}개")
        print(f"   • POST: {stats['methods']['POST']}개\n")
        
        # 캡처된 API 목록 출력
        apis = monitor.get_captured_apis()
        if apis:
            print(f"📡 캡처된 API 목록 (전체 {len(apis)}개):")
            for idx, api in enumerate(apis, 1):
                print(f"   [{idx}] {api['method']} {api['url']}")
                print(f"       상태: {api['status']}, 크기: {len(str(api['data']))} bytes")
        else:
            print("⚠️  캡처된 API 없음")
            print("   → 이 사이트는 API를 사용하지 않거나")
            print("   → 서버 사이드 렌더링 방식일 수 있습니다")
        
        print("\n" + "="*70)
        
        # 상세 요약 출력
        monitor.print_summary()
        
        # 브라우저 확인 시간
        print("⏸️  브라우저를 5초간 확인하세요...")
        await asyncio.sleep(5)
        
        print("\n" + "="*70)
        print("✅ Step 1 테스트 완료!")
        print("="*70 + "\n")
        
        # 검증
        assert monitor.is_monitoring, "모니터링이 활성화되지 않음"
        print("✅ 모든 검증 통과\n")


@pytest.mark.asyncio
async def test_api_monitor_with_manual_interaction():
    """
    Step 1-2: 수동 인터랙션 후 API 모니터링
    
    목적:
    - 옵션 선택 시 API 호출이 발생하는지 확인
    - 사용자가 직접 옵션을 클릭하고 API 호출 관찰
    """
    print("\n" + "="*70)
    print("🚀 Phase 3 Step 1-2: 인터랙션 후 API 모니터링")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        # API 모니터 시작
        monitor = APIMonitor()
        monitor.start_monitoring(page)
        
        # 페이지 이동
        print(f"페이지 이동 중: {TEST_URL}\n")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료")
        print(f"   초기 API 호출: {len(monitor.get_captured_apis())}개\n")
        
        # 인터랙션 전 API 개수 기록
        initial_count = len(monitor.get_captured_apis())
        
        # 사용자 인터랙션 대기
        print("="*70)
        print("🎮 사용자 인터랙션 시간")
        print("="*70)
        print("다음 작업을 수행하세요:")
        print("  1. 용량 선택 (예: 256GB → 512GB)")
        print("  2. 색상 선택")
        print("  3. 통신사 선택")
        print("  4. 요금제 선택")
        print("\n⏰ 10초 대기 중... 옵션을 변경해보세요!\n")
        
        await asyncio.sleep(10)
        
        # 인터랙션 후 API 확인
        final_count = len(monitor.get_captured_apis())
        new_apis = final_count - initial_count
        
        print("="*70)
        print("📊 인터랙션 결과")
        print("="*70)
        print(f"초기 API: {initial_count}개")
        print(f"최종 API: {final_count}개")
        print(f"새 호출: {new_apis}개\n")
        
        # 최근 API 출력
        recent_apis = monitor.get_captured_apis(within_seconds=12)
        if recent_apis:
            print(f"📡 최근 API 호출 ({len(recent_apis)}개):")
            for api in recent_apis:
                print(f"   • {api['method']} {api['url'][:70]}")
        else:
            print("⚠️  새로운 API 호출 없음")
            print("   → API 없이 동작하는 사이트일 수 있습니다")
        
        print("\n" + "="*70)
        monitor.print_summary()
        
        print("✅ Step 1-2 테스트 완료!\n")


@pytest.mark.asyncio
async def test_api_data_structure():
    """
    Step 1-3: API 응답 데이터 구조 분석
    
    목적:
    - 캡처된 API의 실제 응답 데이터 확인
    - 어떤 필드가 있는지 분석
    """
    print("\n" + "="*70)
    print("🚀 Phase 3 Step 1-3: API 데이터 구조 분석")
    print("="*70 + "\n")
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        monitor = APIMonitor()
        monitor.start_monitoring(page)
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        print(f"✅ 페이지 로드 완료\n")
        
        apis = monitor.get_captured_apis()
        
        if not apis:
            print("⚠️  캡처된 API 없음")
            print("   이 사이트는 API가 아닌 HTML 렌더링 방식을 사용합니다\n")
            return
        
        print(f"📊 API 데이터 구조 분석 (총 {len(apis)}개)\n")
        print("="*70)
        
        for idx, api in enumerate(apis, 1):
            print(f"\n[{idx}] {api['method']} {api['url']}")
            print(f"    상태: {api['status']}")
            print(f"    타입: {api['content_type']}")
            
            # 데이터 구조 출력 (상위 레벨만)
            data = api['data']
            if isinstance(data, dict):
                print(f"    키: {list(data.keys())}")
                
                # 데이터 미리보기 (처음 200자)
                import json
                data_str = json.dumps(data, ensure_ascii=False)[:200]
                print(f"    데이터: {data_str}...")
            elif isinstance(data, list):
                print(f"    리스트 길이: {len(data)}")
            else:
                print(f"    타입: {type(data)}")
        
        print("\n" + "="*70)
        print("✅ Step 1-3 테스트 완료!\n")


@pytest.mark.asyncio
async def test_llm_api_analysis():
    """
    Step 2: LLM 기반 API 분석
    
    목적:
    - LLM을 사용하여 캡처된 API 중 정책 관련 API 식별
    - API 응답에서 가격/지원금/요금제 정보 포함 여부 판단
    """
    print("\n" + "="*70)
    print("🚀 Phase 3 Step 2: LLM 기반 API 분석")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않아 테스트를 건너뜁니다")
        pytest.skip("API 키 없음")
        return
    
    # LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    print(f"[1/5] LLM Client 초기화 완료 ({provider.value}) ✅\n")
    
    # 브라우저 설정
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        print("[2/5] 브라우저 시작 완료 ✅\n")
        
        page = await browser_manager.get_page()
        
        # API 모니터 시작 (LLM Client 주입)
        monitor = APIMonitor(llm_client=llm_client)
        monitor.start_monitoring(page)
        print("[3/5] API 모니터 시작 완료 (LLM 분석 활성화) ✅\n")
        
        # 페이지 이동
        print(f"[4/5] 페이지 이동 중...")
        print(f"       URL: {TEST_URL}\n")
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        print(f"✅ 페이지 로드 완료")
        print(f"   Title: {await page.title()}")
        print(f"   캡처된 API: {len(monitor.get_captured_apis())}개\n")
        
        # LLM으로 API 분석
        print("[5/5] LLM으로 API 분석 시작...\n")
        relevant_apis = await monitor.find_relevant_apis_with_llm()
        
        # 결과 출력
        print("\n" + "="*70)
        print("🎯 LLM 분석 결과")
        print("="*70)
        
        if relevant_apis:
            print(f"\n✅ 정책 관련 API 발견: {len(relevant_apis)}개\n")
            
            for idx, api in enumerate(relevant_apis, 1):
                analysis = api.get('llm_analysis', {})
                
                print(f"\n[{idx}] {api['url']}")
                print(f"    메서드: {api['method']}")
                print(f"    상태: {api['status']}")
                print(f"    📊 분석 결과:")
                print(f"       • 포함 정보: {', '.join(analysis.get('contains', []))}")
                print(f"       • 확신도: {analysis.get('confidence', 0):.2f}")
                print(f"       • 이유: {analysis.get('reason', 'N/A')}")
                
                # 데이터 미리보기
                import json
                data_preview = json.dumps(api['data'], ensure_ascii=False, indent=2)[:300]
                print(f"\n    📄 데이터 미리보기:")
                print(f"       {data_preview}...")
        else:
            print("\n⚠️  정책 관련 API를 찾지 못했습니다")
            print("   → 이 사이트는 API가 아닌 HTML 렌더링 방식일 수 있습니다")
            print("   → 또는 LLM 분석 기준을 조정해야 할 수 있습니다")
        
        # LLM 사용량 출력
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"Provider: {stats['provider']}")
        print(f"Model: {stats['model']}")
        print(f"요청 횟수: {stats['request_count']}회")
        print(f"총 토큰: {stats['total_tokens']:,} tokens")
        print(f"총 비용: ${stats['total_cost_usd']:.4f} USD")
        if stats['request_count'] > 0:
            print(f"평균 비용/요청: ${stats['total_cost_usd'] / stats['request_count']:.4f} USD")
        
        print("\n" + "="*70)
        print("✅ Step 2 테스트 완료!")
        print("="*70 + "\n")
        
        # 검증
        assert monitor.is_monitoring, "모니터링이 활성화되지 않음"
        print("✅ 모든 검증 통과\n")


@pytest.mark.asyncio
async def test_screen_page_structure_analysis():
    """
    Phase 3B Step 1: 페이지 구조 분석
    
    목적:
    - LLM으로 페이지의 옵션 UI 식별
    - 가격 표시 영역 식별
    - CSS 셀렉터 추출
    """
    print("\n" + "="*70)
    print("🚀 Phase 3B Step 1: 페이지 구조 분석")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않아 테스트를 건너뜁니다")
        pytest.skip("API 키 없음")
        return
    
    # LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    print(f"[1/4] LLM Client 초기화 완료 ({provider.value}) ✅\n")
    
    # 브라우저 설정
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        print("[2/4] 브라우저 시작 완료 ✅\n")
        
        page = await browser_manager.get_page()
        
        # 페이지 이동
        print(f"[3/4] 페이지 이동 중...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료")
        print(f"   Title: {await page.title()}\n")
        
        # ScreenExtractor 초기화
        extractor = ScreenExtractor(llm_client)
        
        # 페이지 구조 분석
        print("[4/4] 페이지 구조 분석 시작...\n")
        structure = await extractor.analyze_page_structure(page)
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 분석 결과")
        print("="*70)
        
        # 옵션 UI
        options = structure.get("options", {})
        if options:
            print(f"\n✅ 옵션 UI ({len(options)}개):")
            for option_name, option_info in options.items():
                print(f"\n  [{option_name}]")
                print(f"    타입: {option_info.get('type', 'N/A')}")
                print(f"    셀렉터: {option_info.get('selector', 'N/A')}")
        else:
            print("\n⚠️  옵션 UI를 찾지 못했습니다")
        
        # 가격 영역
        pricing = structure.get("pricing", {})
        if pricing:
            print(f"\n✅ 가격 영역 ({len(pricing)}개):")
            for price_name, selector in pricing.items():
                if selector:
                    print(f"  • {price_name}: {selector}")
        else:
            print("\n⚠️  가격 영역을 찾지 못했습니다")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        
        print("\n" + "="*70)
        print("✅ Phase 3B Step 1 완료!")
        print("="*70 + "\n")


@pytest.mark.asyncio
async def test_screen_extract_pricing():
    """
    Phase 3B Step 2: 화면에서 가격 추출
    
    목적:
    - 현재 화면에 표시된 가격 정보 추출
    - LLM으로 HTML 파싱
    """
    print("\n" + "="*70)
    print("🚀 Phase 3B Step 2: 화면 가격 추출")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않아 테스트를 건너뜁니다")
        pytest.skip("API 키 없음")
        return
    
    # LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        print("페이지 이동 중...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # ScreenExtractor로 가격 추출
        extractor = ScreenExtractor(llm_client)
        pricing = await extractor.extract_pricing(page)
        
        # 결과 출력
        print("\n" + "="*70)
        print("💰 추출된 가격 정보")
        print("="*70)
        
        if pricing:
            import json
            print(json.dumps(pricing, ensure_ascii=False, indent=2))
        else:
            print("⚠️  가격 정보를 추출하지 못했습니다")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        
        print("\n" + "="*70)
        print("✅ Phase 3B Step 2 완료!")
        print("="*70 + "\n")


@pytest.mark.asyncio
async def test_screen_collect_all_policies():
    """
    Phase 3B Step 3: 전체 플로우 테스트
    
    목적:
    - 모든 옵션 조합 자동 수집
    - Phase 3 스키마로 변환
    - 최종 JSON 출력
    """
    print("\n" + "="*70)
    print("🚀 Phase 3B Step 3: 전체 플로우 테스트")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print("="*70 + "\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않아 테스트를 건너뜁니다")
        pytest.skip("API 키 없음")
        return
    
    # LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    print(f"[1/4] LLM Client 초기화 완료 ({provider.value}) ✅\n")
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        print("[2/4] 브라우저 시작 완료 ✅\n")
        
        page = await browser_manager.get_page()
        
        print("[3/4] 페이지 이동 중...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # ScreenExtractor로 전체 정책 수집
        extractor = ScreenExtractor(llm_client)
        
        print("[4/4] 전체 정책 수집 시작...\n")
        
        # 최대 5개 조합만 테스트 (빠른 테스트)
        result = await extractor.collect_all_policies(
            page=page,
            url=TEST_URL,
            site_name="띵폰",
            max_combinations=5
        )
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 수집 결과")
        print("="*70)
        print(f"캡처 시각: {result.captured_at}")
        print(f"사이트: {result.source.site}")
        print(f"URL: {result.source.url}")
        print(f"\n제품 수: {len(result.products)}")
        
        for idx, product in enumerate(result.products, 1):
            print(f"\n[제품 {idx}]")
            print(f"  ID: {product.product_id}")
            print(f"  SKU: {product.sku_code}")
            print(f"  용량: {product.sku_storage.value if product.sku_storage else 'N/A'}")
            print(f"  정책 수: {len(product.policies)}")
            
            if product.policies:
                print(f"\n  정책 샘플 (첫 번째):")
                policy = product.policies[0]
                print(f"    • 통신사: {policy.carrier}")
                print(f"    • 가입유형: {policy.mno_join_type.value}")
                print(f"    • 요금제: {policy.mobile_plan.name} ({policy.mobile_plan.monthly_fee:,}원/월)")
                print(f"    • 출고가: {policy.pricing.mno_retail_price:,}원" if policy.pricing.mno_retail_price else "    • 출고가: N/A")
                print(f"    • 공시지원금: {policy.pricing.public_subsidy:,}원" if policy.pricing.public_subsidy else "    • 공시지원금: N/A")
                print(f"    • 최종가: {policy.pricing.sku_installment_fee:,}원" if policy.pricing.sku_installment_fee else "    • 최종가: N/A")
        
        # JSON 출력 (파일로 저장)
        import json
        from pathlib import Path
        
        output_dir = Path("output/phase3")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"policies_{timestamp}.json"
        
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 JSON 파일 저장 완료: {output_file}")
        
        # JSON 미리보기 (처음 500자)
        json_str = json.dumps(json_data, ensure_ascii=False, indent=2, default=str)
        print(f"\n📄 JSON 미리보기:")
        print(json_str[:500] + "...")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        
        print("\n" + "="*70)
        print("✅ Phase 3B Step 3 완료!")
        print("="*70 + "\n")
        
        # 검증
        assert len(result.products) > 0, "제품이 수집되지 않았습니다"
        assert all(len(p.policies) > 0 for p in result.products), "정책이 없는 제품이 있습니다"


@pytest.mark.asyncio
async def test_screen_full_collection():
    """
    Phase 3B Full: 전체 조합 수집 (더 많은 조합)
    
    목적:
    - 더 많은 옵션 조합 테스트 (최대 20개)
    - 실제 운영 시나리오 시뮬레이션
    """
    print("\n" + "="*70)
    print("🚀 Phase 3B Full: 전체 조합 수집")
    print("="*70)
    print(f"테스트 URL: {TEST_URL}")
    print(f"최대 조합: 20개")
    print("="*70 + "\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않아 테스트를 건너뜁니다")
        pytest.skip("API 키 없음")
        return
    
    # LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # ScreenExtractor로 전체 정책 수집
        extractor = ScreenExtractor(llm_client)
        
        # 최대 20개 조합 테스트
        result = await extractor.collect_all_policies(
            page=page,
            url=TEST_URL,
            site_name="띵폰",
            max_combinations=20
        )
        
        # 결과 요약
        print("\n" + "="*70)
        print("📊 수집 결과 요약")
        print("="*70)
        print(f"제품 수: {len(result.products)}")
        print(f"총 정책 수: {sum(len(p.policies) for p in result.products)}")
        
        # 통계
        carriers = set()
        join_types = set()
        for product in result.products:
            for policy in product.policies:
                carriers.add(policy.carrier)
                join_types.add(policy.mno_join_type.value)
        
        print(f"\n통신사: {', '.join(carriers)}")
        print(f"가입유형: {', '.join(join_types)}")
        
        # 파일 저장
        from pathlib import Path
        import json
        
        output_dir = Path("output/phase3")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"policies_full_{timestamp}.json"
        
        json_data = result.model_dump(mode='json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 전체 결과 저장: {output_file}")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print("\n" + "="*70)
        print("💰 LLM 사용량")
        print("="*70)
        print(f"요청: {stats['request_count']}회")
        print(f"토큰: {stats['total_tokens']:,} tokens")
        print(f"비용: ${stats['total_cost_usd']:.4f} USD")
        print(f"평균 비용/요청: ${stats['total_cost_usd'] / stats['request_count']:.4f} USD" if stats['request_count'] > 0 else "")
        
        print("\n" + "="*70)
        print("✅ Phase 3B Full 완료!")
        print("="*70 + "\n")


if __name__ == "__main__":
    # 직접 실행 시
    import sys
    
    print("\n🧪 Phase 3 테스트 실행\n")
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  API 키가 설정되지 않았습니다")
        print("   .env 파일에 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY를 설정하세요\n")
        sys.exit(1)
    
    # 테스트 실행
    asyncio.run(test_api_monitor_basic())

