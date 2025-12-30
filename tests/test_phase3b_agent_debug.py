"""
LLM Agent 디버그: 옵션 분석 및 조합 생성 확인
"""
import pytest
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.llm_agent_extractor import LLMAgentExtractor


TEST_URL = "https://ddingphone.com/view/143?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1738389813"

# 띵폰
# https://ddingphone.com/view/143?tid=LGU&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=1&code=L1738389813
# 하이폰
# https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337

@pytest.mark.asyncio
async def test_debug_option_analysis():
    """
    디버그: LLM이 어떤 옵션을 추출하는지 확인
    """
    print("\n" + "="*70)
    print("🐛 디버그: LLM 옵션 분석")
    print("="*70 + "\n")
    
    if os.getenv("GEMINI_API_KEY"):
        provider = LLMProvider.GEMINI
        model = "gemini-2.5-flash"
    elif os.getenv("OPENAI_API_KEY"):
        provider = LLMProvider.OPENAI
        model = None
    else:
        pytest.skip("API 키 없음")
        return
    
    llm_client = LLMClient(provider=provider, model=model) if model else LLMClient(provider=provider)
    
    config = SiteConfig(target_url=TEST_URL, headless=False, timeout=60000)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"✅ 페이지 로드 완료\n")
        
        # LLM Agent 초기화
        extractor = LLMAgentExtractor(llm_client)
        
        # Step 1: 옵션 분석
        print("[Step 1] LLM 옵션 분석")
        print("-" * 70)
        available_options = await extractor.analyze_available_options(page)
        
        print("\n📊 LLM이 추출한 옵션:")
        import json
        print(json.dumps(available_options, ensure_ascii=False, indent=2))
        
        # Step 2: 가지치기 전략 적용
        print("\n[Step 2] 가지치기 전략 적용")
        print("-" * 70)
        pruned = extractor._apply_pruning_strategy(available_options)
        
        print("\n✂️  가지치기 결과:")
        print(json.dumps(pruned, ensure_ascii=False, indent=2))
        
        # Step 3: 조합 생성
        print("\n[Step 3] 조합 생성")
        print("-" * 70)
        
        from itertools import product as itertools_product
        
        keys = list(pruned.keys())
        values = [pruned[k] for k in keys if pruned[k]]
        keys = [k for k in keys if pruned[k]]
        
        combinations = []
        if keys:
            for combo_values in itertools_product(*values):
                combo = dict(zip(keys, combo_values))
                combinations.append(combo)
                
                if len(combinations) >= 12:
                    break
        
        print(f"\n✅ 생성된 조합: {len(combinations)}개\n")
        
        for idx, combo in enumerate(combinations, 1):
            print(f"  [{idx}] {combo}")
        
        # 검증
        assert len(available_options) > 0, "옵션이 추출되지 않음"
        assert len(combinations) > 0, "조합이 생성되지 않음"
        
        print("\n" + "="*70)
        print(f"✅ 디버그 완료: {len(combinations)}개 조합 생성됨")
        print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_debug_option_analysis())

