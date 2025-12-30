"""
Phase 3 띵폰 사이트 API 분석
특정 사이트에 대한 상세 분석
"""
import pytest
import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.crawlers.api_monitor import APIMonitor


TEST_URL = "https://ddingphone.com/view/138?tid=SKT&oid=%EB%B2%88%ED%98%B8%EC%9D%B4%EB%8F%99&sales=2&code=S1714617302"


@pytest.mark.asyncio
async def test_ddingphone_api_detailed_analysis():
    """
    띵폰 사이트 API 상세 분석
    
    목적:
    - 모든 API 응답을 파일로 저장
    - 각 API의 상세 데이터 구조 파악
    - 정책 정보가 어디에 있는지 확인
    """
    print("\n" + "="*70)
    print("🔬 띵폰 사이트 API 상세 분석")
    print("="*70)
    print(f"URL: {TEST_URL}")
    print("="*70 + "\n")
    
    config = SiteConfig(
        target_url=TEST_URL,
        headless=False,
        timeout=60000
    )
    
    # 출력 디렉토리 생성
    output_dir = Path("output/api_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with BrowserManager(config) as browser_manager:
        page = await browser_manager.get_page()
        
        monitor = APIMonitor()
        monitor.start_monitoring(page)
        
        print("[1/3] 페이지 로딩 중...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        print(f"✅ 페이지 로드 완료\n")
        
        apis = monitor.get_captured_apis()
        
        if not apis:
            print("⚠️  캡처된 API 없음")
            return
        
        print(f"[2/3] API 응답 저장 중... (총 {len(apis)}개)\n")
        
        # 각 API를 파일로 저장
        for idx, api in enumerate(apis, 1):
            filename = f"ddingphone_api_{idx}.json"
            filepath = output_dir / filename
            
            # 저장할 데이터
            api_data = {
                "index": idx,
                "url": api['url'],
                "method": api['method'],
                "status": api['status'],
                "content_type": api['content_type'],
                "timestamp": api['timestamp'],
                "data": api['data']
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(api_data, f, ensure_ascii=False, indent=2)
            
            print(f"  [{idx}] 저장 완료: {filename}")
            print(f"      URL: {api['url']}")
            print(f"      메서드: {api['method']}")
            
            # 데이터 구조 간단히 출력
            data = api['data']
            if isinstance(data, dict):
                keys = list(data.keys())
                print(f"      키: {keys}")
                
                # 특별히 관심 있는 키 확인
                interesting_keys = ['best', 'use', 'list', 'template', 'content']
                for key in interesting_keys:
                    if key in data:
                        value = data[key]
                        if isinstance(value, list):
                            print(f"      → {key}: 리스트 ({len(value)}개 항목)")
                            if value:
                                # 첫 번째 항목의 키 출력
                                if isinstance(value[0], dict):
                                    print(f"         첫 항목 키: {list(value[0].keys())[:5]}...")
                        elif isinstance(value, str):
                            print(f"      → {key}: 문자열 ({len(value)}자)")
                        else:
                            print(f"      → {key}: {type(value).__name__}")
            
            print()
        
        print(f"[3/3] 분석 결과")
        print("="*70)
        print(f"✅ 모든 API 응답이 저장되었습니다")
        print(f"   저장 위치: {output_dir.absolute()}")
        print(f"\n💡 다음 단계:")
        print(f"   1. output/api_analysis/ 폴더의 JSON 파일 확인")
        print(f"   2. 정책 정보가 포함된 API 식별")
        print(f"   3. LLM 프롬프트 개선")
        print("="*70 + "\n")


@pytest.mark.asyncio
async def test_ddingphone_api3_deep_analysis():
    """
    띵폰 API #3 심층 분석
    
    API #3이 가장 유망해 보이므로 (best, use, list 포함) 상세 분석
    """
    print("\n" + "="*70)
    print("🔬 띵폰 API #3 심층 분석")
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
        
        monitor = APIMonitor(llm_client=llm_client)
        monitor.start_monitoring(page)
        
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        apis = monitor.get_captured_apis()
        
        if len(apis) < 3:
            print(f"⚠️  API가 충분히 캡처되지 않음 (현재: {len(apis)}개)")
            return
        
        # 3번째 API 분석
        api3 = apis[2]  # 0-based index
        
        print(f"📡 API #3: {api3['url']}")
        print(f"   메서드: {api3['method']}")
        print(f"   상태: {api3['status']}\n")
        
        # 데이터 구조 출력
        data = api3['data']
        print(f"📊 데이터 구조:")
        print(f"   키: {list(data.keys())}\n")
        
        # use 배열 분석 (가장 유망)
        if 'use' in data and isinstance(data['use'], list) and data['use']:
            print(f"🎯 'use' 배열 분석 (정책 정보 후보)")
            print(f"   항목 수: {len(data['use'])}개\n")
            
            # 첫 번째 항목 상세 출력
            first_item = data['use'][0]
            print(f"   첫 번째 항목:")
            print(json.dumps(first_item, ensure_ascii=False, indent=4))
            print()
            
            # LLM으로 이 항목이 정책 정보인지 분석
            print(f"\n🤖 LLM 분석 시작...")
            
            # 단일 항목에 대한 프롬프트
            prompt = f"""
다음 데이터가 휴대폰 구매 정책 정보를 포함하는지 분석하세요.

# 데이터
{json.dumps(first_item, ensure_ascii=False, indent=2)}

# 질문
1. 이 데이터에 다음 정보가 포함되어 있나요?
   - 가격 (출고가, 할인가)
   - 지원금 (공시지원금, 추가지원금)
   - 요금제 정보
   - 할부 정보
   - 통신사 정보
   - 가입 유형 정보

2. 어떤 필드가 어떤 정보를 담고 있나요?

# 응답 형식 (JSON)
{{
  "is_policy_data": true,
  "identified_fields": {{
    "price": ["필드명1", "필드명2"],
    "subsidy": ["필드명3"],
    "plan": ["필드명4"],
    "carrier": ["필드명5"],
    "join_type": ["필드명6"]
  }},
  "confidence": 0.95,
  "explanation": "상세 설명"
}}

**JSON만 출력하세요.**
"""
            
            response = await llm_client.complete(
                prompt=prompt,
                system_message="당신은 API 응답 데이터 분석 전문가입니다.",
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            analysis = json.loads(response)
            
            print(f"\n✅ LLM 분석 결과:")
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        
        print("\n" + "="*70)
        print("✅ 심층 분석 완료!")
        print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_ddingphone_api_detailed_analysis())

