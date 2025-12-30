"""
통합 휴대폰 정책 스크래핑 서비스
Phase 1 (카테고리 탐색) -> Phase 2 (상세 URL 탐색) -> Phase 3 (정책 추출) 통합
"""
import asyncio
import json
import base64
from typing import Dict, List, Any, Optional
from playwright.async_api import Page

from ..core.llm_client import LLMClient, LLMProvider
from ..core.browser import BrowserManager
from ..core.config import SiteConfig
from ..crawlers.simple_detail_extractor import SimpleDetailExtractor
from ..models.phase3_schemas import ScrapingResult
from ..utils.logger import get_logger

logger = get_logger()

class PhoneScraperService:
    def __init__(self):
        # 모든 단계에서 gemini-2.5-flash 사용
        self.llm = LLMClient(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")
        
    async def run_discovery_phase(self, page: Page, site_url: str) -> Dict[str, str]:
        """
        Phase 1 & 2 통합: 메인 페이지에서 목표 모델의 상세 URL들을 찾음
        """
        # URL 클리닝 (백슬래시 제거)
        clean_url = site_url.replace("\\", "")
        
        print(f"\n[Step 1/3] 🌍 사이트 접속 중: {clean_url}")
        logger.info(f"🔍 [Discovery] URL 탐색 시작: {clean_url}")
        
        # 1. 사이트 접속
        await page.goto(clean_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        print(f"   ✅ 페이지 로드 완료: {await page.title()}")
        
        detail_urls = {}
        
        # 2. 현재 페이지에서 바로 모델들을 찾아봄 (이미 리스트 페이지일 수 있음)
        print("   🔍 현재 페이지에서 모델 상세 페이지 탐색 중...")
        found_on_current = await self._find_models_on_page(page)
        detail_urls.update(found_on_current)
        
        # 3. 만약 모델을 다 찾지 못했다면 카테고리 탐색 시도
        if len(detail_urls) < 2:
            print("   📂 모델 부족, 카테고리(갤럭시/아이폰) 메뉴 탐색 시도...")
            screenshot = await page.screenshot(full_page=False, quality=50, type='jpeg')
            screenshot_b64 = base64.b64encode(screenshot).decode()
            
            category_prompt = """
    화면에서 '갤럭시'와 '아이폰' 카테고리 메뉴/링크를 찾으세요.
    각 카테고리로 이동하기 위해 클릭하거나 이동해야 할 텍스트 또는 URL을 알려주세요.

    응답 형식 (JSON):
    {
      "GALAXY": "갤럭시",
      "IPHONE": "아이폰"
    }
    """
            resp = await self.llm.complete_with_vision(prompt=category_prompt, image_url=f"data:image/jpeg;base64,{screenshot_b64}")
            category_info = self._parse_json_response(resp)
            print(f"   🤖 발견된 카테고리: {list(category_info.values())}")
            
            # 각 카테고리 방문하여 상세 URL 찾기
            for model_type, category_text in category_info.items():
                model_key = "GALAXY_S25" if model_type == "GALAXY" else "IPHONE17"
                if model_key in detail_urls: continue # 이미 찾았으면 스킵
                
                try:
                    print(f"\n[Step 2/3] 📍 카테고리 '{category_text}' 이동 중...")
                    await page.get_by_text(category_text, exact=False).first.click(force=True, timeout=5000)
                    await asyncio.sleep(2)
                    
                    found_urls = await self._find_models_on_page(page)
                    if model_key in found_urls:
                        detail_urls[model_key] = found_urls[model_key]
                        print(f"   ✅ '{category_text}'에서 {model_key} 발견")
                except Exception as e:
                    logger.error(f"   ❌ {category_text} 탐색 실패: {e}")
                
        return detail_urls

    async def _find_models_on_page(self, page: Page) -> Dict[str, str]:
        """현재 페이지 내에서 S25와 아이폰17 상세 링크 찾기"""
        screenshot = await page.screenshot(full_page=False, quality=50, type='jpeg')
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        detail_prompt = """
현재 목록에서 '갤럭시 S25'와 '아이폰 17' 모델의 상세 페이지로 가는 링크나 클릭할 텍스트를 찾으세요.

응답 형식 (JSON):
{
  "GALAXY_S25": {"found": true, "click_text": "갤럭시 S25"},
  "IPHONE17": {"found": true, "click_text": "아이폰 17"}
}
"""
        resp = await self.llm.complete_with_vision(prompt=detail_prompt, image_url=f"data:image/jpeg;base64,{screenshot_b64}")
        discovery_info = self._parse_json_response(resp)
        
        found_urls = {}
        for model_key, info in discovery_info.items():
            if info.get("found"):
                try:
                    # 클릭 시도 및 URL 확보
                    target_text = info.get("click_text")
                    # href 속성이 있는 상위 요소를 찾아서 URL 직접 가져오기 시도
                    href = await page.evaluate(f"""
                        (text) => {{
                            const elements = Array.from(document.querySelectorAll('a'));
                            const match = elements.find(el => el.textContent.includes(text));
                            return match ? match.href : null;
                        }}
                    """, target_text)
                    
                    if href:
                        found_urls[model_key] = href
                    else:
                        # href가 없으면 클릭해서 페이지 이동 후 URL 확보
                        await page.get_by_text(target_text, exact=False).first.click(force=True, timeout=5000)
                        await asyncio.sleep(1)
                        found_urls[model_key] = page.url
                        await page.go_back() # 다시 목록으로
                        await asyncio.sleep(1)
                except:
                    pass
        return found_urls

    async def scrape_site(self, site_url: str) -> List[ScrapingResult]:
        """
        [Full Pipeline] 메인 URL -> 상세 URL -> 정책 추출 통합 실행
        """
        print(f"\n" + "="*70)
        print(f"🚀 [ 통합 스크래핑 프로세스 시작 ]")
        print(f"   사이트: {site_url}")
        print("="*70)
        
        config = SiteConfig(target_url=site_url, headless=True, timeout=60000)
        
        async with BrowserManager(config) as browser_manager:
            page = await browser_manager.get_page()
            
            # 1. URL Discovery
            target_detail_urls = await self.run_discovery_phase(page, site_url)
            
            if not target_detail_urls:
                print("\n❌ 수집할 수 있는 상세 페이지를 찾지 못했습니다.")
                return []

            results = []
            
            # 2. 각 상세 페이지에서 정책 추출 (Phase 3)
            print(f"\n[Step 3/3] 📊 정책 데이터 추출 시작 (대상: {len(target_detail_urls)}개 모델)")
            
            for model_name, detail_url in target_detail_urls.items():
                print(f"\n----------------------------------------------------------------------")
                print(f"📱 모델: {model_name}")
                print(f"🔗 접속: {detail_url}")
                print(f"----------------------------------------------------------------------")
                
                try:
                    # 페이지 이동
                    await page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(2)
                    
                    # SimpleDetailExtractor 사용
                    site_domain = site_url.split("//")[-1].split("/")[0]
                    extractor = SimpleDetailExtractor(self.llm, model_name=model_name)
                    
                    print(f"   🤖 {model_name} 정책 분석 및 옵션 조합 시도 중...")
                    result = await extractor.collect_all_policies(
                        page=page,
                        url=detail_url,
                        site_name=site_domain
                    )
                    
                    policy_count = sum(len(p.policies) for p in result.products)
                    print(f"\n   ✅ {model_name} 추출 완료! (수집된 정책: {policy_count}개)")
                    results.append(result)
                except Exception as e:
                    print(f"   ❌ {model_name} 추출 오류: {str(e)}")
                    logger.error(f"   ❌ {model_name} 추출 실패: {e}")
                
            print(f"\n" + "="*70)
            print(f"🎉 모든 수집 프로세스 종료 (총 {len(results)}개 모델 완료)")
            print("="*70 + "\n")
            return results

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출 및 파싱"""
        try:
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except Exception as e:
            logger.error(f"JSON 파싱 실패: {e} | 응답: {response}")
            return {}

