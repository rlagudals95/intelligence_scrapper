"""
Phase 2 테스트: LLM 통합
- 2-1. LLM Client: OpenAI/Anthropic API, 재시도, 토큰 추적, 비용 모니터링
- 2-2. Page Analyzer: LLM 활용 페이지 구조 분석
- 2-3. Prompt Templates: 리스팅/상세/가격 페이지 프롬프트
"""
import pytest
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from src.core.llm_client import LLMClient, LLMProvider
from src.utils.page_analyzer import PageAnalyzer
from src.utils.prompts import (
    format_listing_analysis_prompt,
    format_detail_options_prompt,
    format_pricing_area_prompt,
    LISTING_PAGE_ANALYSIS_SYSTEM,
    DETAIL_PAGE_OPTIONS_SYSTEM,
    PRICING_AREA_SYSTEM
)


# ============================================================================
# 2-1. LLM Client 테스트
# ============================================================================

def test_llm_client_initialization():
    """LLM Client 초기화 테스트"""
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("API 키가 설정되지 않았습니다")
    
    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        client = LLMClient(provider=LLMProvider.OPENAI)
        assert client.provider == LLMProvider.OPENAI
        assert client.model == "gpt-4o"
        print("✅ OpenAI LLM Client 초기화 성공")
    
    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        client = LLMClient(provider=LLMProvider.ANTHROPIC)
        assert client.provider == LLMProvider.ANTHROPIC
        assert "claude" in client.model.lower()
        print("✅ Anthropic LLM Client 초기화 성공")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_client_complete():
    """LLM 완성 요청 테스트"""
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    
    response = await client.complete(
        prompt="2 + 2는 무엇인가요? 숫자만 답하세요.",
        system_message="당신은 수학 도우미입니다.",
        max_tokens=10
    )
    
    assert response is not None
    assert len(response) > 0
    assert "4" in response
    
    print(f"✅ LLM 완성 요청 테스트 통과")
    print(f"   응답: {response}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_token_tracking():
    """LLM 토큰 사용량 추적 테스트"""
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    
    # 초기 상태
    stats = client.get_usage_stats()
    assert stats["request_count"] == 0
    assert stats["total_tokens"] == 0
    
    # 첫 번째 요청
    await client.complete(prompt="안녕", max_tokens=10)
    stats1 = client.get_usage_stats()
    assert stats1["request_count"] == 1
    assert stats1["total_tokens"] > 0
    
    # 두 번째 요청
    await client.complete(prompt="반가워", max_tokens=10)
    stats2 = client.get_usage_stats()
    assert stats2["request_count"] == 2
    assert stats2["total_tokens"] > stats1["total_tokens"]
    
    print("✅ 토큰 추적 테스트 통과")
    print(f"   총 요청: {stats2['request_count']}")
    print(f"   총 토큰: {stats2['total_tokens']}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_cost_monitoring():
    """LLM 비용 모니터링 테스트"""
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    
    # 요청 실행
    await client.complete(prompt="테스트", max_tokens=10)
    
    # 통계 확인
    stats = client.get_usage_stats()
    assert "provider" in stats
    assert "model" in stats
    assert "request_count" in stats
    assert "total_tokens" in stats
    assert "total_cost_usd" in stats
    
    # 비용이 0 이상인지 확인
    assert stats["total_cost_usd"] >= 0
    assert stats["request_count"] == 1
    assert stats["total_tokens"] > 0
    
    print("✅ 비용 모니터링 테스트 통과")
    print(f"   Provider: {stats['provider']}")
    print(f"   Model: {stats['model']}")
    print(f"   요청 수: {stats['request_count']}")
    print(f"   총 토큰: {stats['total_tokens']}")
    print(f"   총 비용: ${stats['total_cost_usd']:.6f}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_client_json_mode():
    """LLM JSON 모드 테스트"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API 키 없음 (JSON mode는 OpenAI 전용)")
    
    client = LLMClient(provider=LLMProvider.OPENAI)
    
    response = await client.complete(
        prompt='다음 정보를 JSON으로 반환하세요: 이름은 "홍길동", 나이는 30',
        system_message="당신은 JSON 생성기입니다.",
        response_format={"type": "json_object"}
    )
    
    # JSON 파싱 가능한지 확인
    data = json.loads(response)
    assert "이름" in data or "name" in data
    
    print(f"✅ JSON 모드 테스트 통과")
    print(f"   응답: {response}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_vision_api():
    """LLM Vision API 테스트 (스크린샷 분석)"""
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    
    # 간단한 1x1 빨간색 PNG (base64)
    red_pixel_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    
    response = await client.complete_with_vision(
        prompt="이 이미지의 색상은 무엇인가요?",
        image_url=f"data:image/png;base64,{red_pixel_base64}"
    )
    
    assert response is not None
    assert len(response) > 0
    
    print("✅ Vision API 테스트 통과")
    print(f"   응답: {response}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_llm_retry_logic():
    """LLM 재시도 로직 테스트"""
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    
    # 정상 요청 (재시도 없이 성공해야 함)
    response = await client.complete(
        prompt="안녕",
        max_tokens=10
    )
    
    assert response is not None
    print("✅ 재시도 로직 테스트 통과 (정상 요청 성공)")
    
    # 참고: 실제 실패 시나리오 테스트는 mock이 필요하므로 생략


# ============================================================================
# 2-3. Prompt Templates 테스트
# ============================================================================

def test_prompt_template_listing():
    """리스팅 페이지 분석 프롬프트 테스트"""
    html = "<div class='product-card'><a href='/product/1'>갤럭시 S24</a></div>"
    prompt = format_listing_analysis_prompt(html)
    
    # 프롬프트에 필수 요소 포함 확인
    assert "product-card" in prompt
    assert "CSS 셀렉터" in prompt or "selector" in prompt.lower()
    assert len(prompt) > 100  # 충분한 지시사항이 있어야 함
    
    # 시스템 메시지 확인
    assert "리스팅 페이지" in LISTING_PAGE_ANALYSIS_SYSTEM or "listing" in LISTING_PAGE_ANALYSIS_SYSTEM.lower()
    
    print("✅ 리스팅 페이지 프롬프트 테스트 통과")


def test_prompt_template_detail_options():
    """상세 페이지 옵션 추출 프롬프트 테스트"""
    html = "<select id='carrier'><option>SKT</option><option>KT</option></select>"
    prompt = format_detail_options_prompt(html)
    
    # 필수 옵션 키워드 확인
    assert "통신사" in prompt
    assert "가입유형" in prompt
    assert "용량" in prompt or "저장용량" in prompt
    
    # 시스템 메시지 확인
    assert len(DETAIL_PAGE_OPTIONS_SYSTEM) > 0
    
    print("✅ 상세 페이지 옵션 프롬프트 테스트 통과")


def test_prompt_template_pricing():
    """가격/정책 영역 식별 프롬프트 테스트"""
    html = "<div class='price'>1,200,000원</div><div class='discount'>100,000원 할인</div>"
    prompt = format_pricing_area_prompt(html)
    
    # 가격 관련 키워드 확인
    assert "가격" in prompt or "최종가" in prompt or "price" in prompt.lower()
    assert len(prompt) > 50
    
    # 시스템 메시지 확인
    assert len(PRICING_AREA_SYSTEM) > 0
    
    print("✅ 가격/정책 영역 프롬프트 테스트 통과")


# ============================================================================
# 2-2. Page Analyzer 테스트
# ============================================================================

def test_page_analyzer_initialization():
    """PageAnalyzer 초기화 테스트"""
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("API 키 없음")
    
    analyzer = PageAnalyzer()
    assert analyzer.llm is not None
    assert analyzer.llm.provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC]
    
    print("✅ PageAnalyzer 초기화 테스트 통과")
    print(f"   LLM Provider: {analyzer.llm.provider.value}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_page_analyzer_json_extraction():
    """PageAnalyzer JSON 추출 테스트"""
    analyzer = PageAnalyzer()
    
    # 1. Markdown 코드 블록 포함 (```json)
    response1 = '''```json
    {"key": "value"}
    ```'''
    result1 = analyzer._extract_json_from_response(response1)
    assert result1 == {"key": "value"}
    print("✅ Markdown 코드 블록 (```json) 추출 성공")
    
    # 2. Markdown 코드 블록 (```)
    response2 = '''```
    {"key": "value"}
    ```'''
    result2 = analyzer._extract_json_from_response(response2)
    assert result2 == {"key": "value"}
    print("✅ Markdown 코드 블록 (```) 추출 성공")
    
    # 3. 순수 JSON
    response3 = '{"key": "value"}'
    result3 = analyzer._extract_json_from_response(response3)
    assert result3 == {"key": "value"}
    print("✅ 순수 JSON 추출 성공")
    
    print("✅ JSON 추출 테스트 모두 통과")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_page_analyzer_llm_stats():
    """PageAnalyzer LLM 통계 조회 테스트"""
    analyzer = PageAnalyzer()
    
    # 초기 통계
    stats = analyzer.get_llm_stats()
    assert "request_count" in stats
    assert stats["request_count"] == 0
    
    print("✅ PageAnalyzer LLM 통계 조회 테스트 통과")


# ============================================================================
# 통합 테스트
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
async def test_phase2_integration():
    """Phase 2 통합 테스트: LLM Client + Prompt Templates + Page Analyzer"""
    print("\n" + "="*60)
    print("Phase 2 통합 테스트 시작")
    print("="*60)
    
    # 1. LLM Client 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    client = LLMClient(provider=provider)
    print(f"✅ 1. LLM Client 초기화 ({provider.value})")
    
    # 2. Prompt Template 생성
    test_html = "<div class='product'><h2>갤럭시 S24</h2></div>"
    prompt = format_listing_analysis_prompt(test_html)
    assert len(prompt) > 0
    print("✅ 2. Prompt Template 생성")
    
    # 3. LLM 호출 (간단한 테스트)
    response = await client.complete(
        prompt="1 + 1은?",
        max_tokens=10
    )
    assert response is not None
    print(f"✅ 3. LLM 호출 성공")
    
    # 4. PageAnalyzer 초기화
    analyzer = PageAnalyzer(llm_client=client)
    print("✅ 4. PageAnalyzer 초기화")
    
    # 5. JSON 추출 테스트
    json_response = '{"test": "value"}'
    extracted = analyzer._extract_json_from_response(json_response)
    assert extracted == {"test": "value"}
    print("✅ 5. JSON 추출 기능 확인")
    
    # 6. 통계 확인
    stats = analyzer.get_llm_stats()
    assert stats["request_count"] >= 1
    assert stats["total_tokens"] > 0
    print(f"✅ 6. LLM 통계 확인")
    print(f"   - 요청 수: {stats['request_count']}")
    print(f"   - 총 토큰: {stats['total_tokens']}")
    
    print("="*60)
    print("✅ Phase 2 통합 테스트 성공!")
    print("="*60)


# ============================================================================
# 실제 리스팅 페이지 데이터 수집 테스트
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="API 키 없음"
)
@pytest.mark.parametrize("site_name,target_url,min_items", [
    (
        "하이폰",
        "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
        8
    ),
    (
        "띵폰",
        "https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
        25
    ),
    (
        "딜리버리폰",
        "https://www.deliveryphone.co.kr/phone/list/2",
        13
    )
])
async def test_listing_collection(site_name: str, target_url: str, min_items: int):
    """리스팅 페이지 데이터 수집 테스트 (파라미터화)"""
    from src.core.config import SiteConfig
    from src.core.browser import BrowserManager
    from src.crawlers.listing import ListingCrawler
    from src.models.schemas import PhoneListingItem
    
    print("\n" + "="*70)
    print(f"{site_name} 리스팅 페이지 데이터 수집 테스트")
    print("="*70)
    
    config = SiteConfig(
        target_url=target_url,
        headless=True,
        timeout=60000
    )
    
    # LLM Client 및 Browser 초기화
    if os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
    else:
        provider = LLMProvider.ANTHROPIC
    
    llm_client = LLMClient(provider=provider)
    
    async with BrowserManager(config) as browser:
        # ListingCrawler로 데이터 수집
        crawler = ListingCrawler(llm_client, browser)
        items = await crawler.crawl(target_url)
        
        print(f"\n✅ 수집된 상품 수: {len(items)}")
        
        # LLM 사용량 및 비용 출력
        stats = llm_client.get_usage_stats()
        print(f"\n💰 LLM 사용량 및 비용:")
        print(f"   Provider: {stats['provider']}")
        print(f"   Model: {stats['model']}")
        print(f"   요청 횟수: {stats['request_count']}회")
        print(f"   총 토큰 수: {stats['total_tokens']:,} tokens")
        print(f"   총 비용: ${stats['total_cost_usd']:.4f} USD")
        if stats['request_count'] > 0 and stats['total_tokens'] > 0:
            print(f"   평균 토큰/요청: {stats['total_tokens'] / stats['request_count']:.0f} tokens")
            print(f"   평균 비용/요청: ${stats['total_cost_usd'] / stats['request_count']:.4f} USD")
        
        # 검증: 최소 개수 이상
        assert len(items) >= min_items, f"최소 {min_items}개 이상의 상품이 필요합니다 (현재: {len(items)}개)"
        
        # 검증: 모든 아이템이 PhoneListingItem 타입
        assert all(isinstance(item, PhoneListingItem) for item in items)
        
        # 검증: 필수 필드 존재
        for item in items:
            assert item.model_name, "기종명이 있어야 함"
            assert item.detail_url, "상세 URL이 있어야 함"
            assert "http" in item.detail_url, "절대 URL이어야 함"
        
        # 검증: 가격 정보가 있는 경우 숫자로 변환 가능한지
        for item in items:
            if item.discount_price:
                price_num = item.discount_price.replace(",", "").replace("원", "").strip()
                # 빈 문자열이거나 숫자여야 함
                if price_num:
                    assert price_num.isdigit(), f"가격 형식 오류: {item.discount_price}"
        
        # 상품 출력 (처음 3개)
        print("\n📊 수집된 상품 샘플 (처음 3개):")
        for i, item in enumerate(items[:1], 1):
            print(f"\n  {i}. {item.model_name}")
            print(f"     통신사: {item.carrier or 'N/A'}")
            print(f"     변경유형: {item.signup_type or 'N/A'}")
            print(f"     출고가: {item.retail_price or 'N/A'}")
            print(f"     할인가: {item.discount_price or 'N/A'}")
            print(f"     지원금타입: {item.subsidy_type or 'N/A'}")
            print(f"     공시지원금: {item.public_subsidy or 'N/A'}")
            print(f"     추가지원금: {item.additional_subsidy or 'N/A'}")
            print(f"     요금제: {item.plan_name or 'N/A'}")
            print(f"     혜택: {item.benefits or 'N/A'}")
            print(f"     상세 URL: {item.detail_url[:60]}...")
        
        print("\n" + "="*70)
        print(f"✅ {site_name} 리스팅 테스트 통과!")
        print("="*70)


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("\n🧪 Phase 2 테스트 실행\n")
    
    # 동기 테스트
    test_llm_client_initialization()
    test_prompt_template_listing()
    test_prompt_template_detail_options()
    test_prompt_template_pricing()
    test_page_analyzer_initialization()
    
    # 비동기 테스트
    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        asyncio.run(test_llm_client_complete())
        asyncio.run(test_llm_token_tracking())
        asyncio.run(test_llm_cost_monitoring())
        asyncio.run(test_llm_client_json_mode())
        asyncio.run(test_llm_vision_api())
        asyncio.run(test_llm_retry_logic())
        asyncio.run(test_page_analyzer_json_extraction())
        asyncio.run(test_page_analyzer_llm_stats())
        asyncio.run(test_phase2_integration())
    else:
        print("\n⚠️  API 키가 설정되지 않아 일부 테스트를 건너뜁니다")
        print("   OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 환경변수를 설정하세요")
    
    print("\n✅ Phase 2 테스트 완료!\n")

