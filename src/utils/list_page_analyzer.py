"""
Page Analyzer (Phase 2)
LLM을 활용한 페이지 구조 분석
"""
import json
import base64
from typing import Dict, Any, Optional, List
from playwright.async_api import Page
from urllib.parse import urljoin

from ..core.llm_client import LLMClient, LLMProvider
from ..utils.logger import get_logger
from .prompts import (
    LISTING_PAGE_ANALYSIS_SYSTEM,
    format_listing_analysis_prompt,
    DETAIL_PAGE_OPTIONS_SYSTEM,
    format_detail_options_prompt,
    PRICING_AREA_SYSTEM,
    format_pricing_area_prompt
)

logger = get_logger()


class ListPageAnalyzer:
    """LLM 기반 페이지 분석기"""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        provider: LLMProvider = LLMProvider.OPENAI
    ):
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMClient(provider=provider)
        
        logger.info("ListPageAnalyzer 초기화", provider=provider.value)
    
    async def analyze_listing_page(
        self,
        page: Page,
        use_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        리스팅 페이지 분석
        
        Args:
            page: Playwright Page 객체
            use_screenshot: 스크린샷 사용 여부
            
        Returns:
            Dict: 분석 결과
            {
                "product_card_selector": str,
                "product_name_selector": str,
                "detail_link_selector": str,
                "pagination_type": str,
                "next_button_selector": str | null
            }
        """
        logger.info("리스팅 페이지 분석 시작")
        
        # HTML 추출 (간소화 - body만)
        html_content = await self._extract_simplified_html(page)
        
        # 프롬프트 생성
        prompt = format_listing_analysis_prompt(html_content)
        
        # LLM 호출
        if use_screenshot:
            screenshot_base64 = await self._capture_screenshot_base64(page)
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=f"data:image/png;base64,{screenshot_base64}",
                system_message=LISTING_PAGE_ANALYSIS_SYSTEM
            )
        else:
            response = await self.llm.complete(
                prompt=prompt,
                system_message=LISTING_PAGE_ANALYSIS_SYSTEM,
                response_format={"type": "json_object"} if self.llm.provider == LLMProvider.OPENAI else None
            )
        
        # JSON 파싱
        try:
            result = self._extract_json_from_response(response)
            logger.info("리스팅 페이지 분석 완료", selectors=list(result.keys()))
            return result
        except json.JSONDecodeError as e:
            logger.error("JSON 파싱 실패", error=str(e), response=response)
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {response}")
    
    async def analyze_detail_page_options(
        self,
        page: Page,
        use_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        상세 페이지 옵션 분석
        
        Returns:
            Dict: 옵션별 셀렉터 정보
            {
                "carrier": {"selector": str, "type": str, "exists": bool},
                "signup_type": {...},
                ...
            }
        """
        logger.info("상세 페이지 옵션 분석 시작")
        
        html_content = await self._extract_simplified_html(page)
        prompt = format_detail_options_prompt(html_content)
        
        if use_screenshot:
            screenshot_base64 = await self._capture_screenshot_base64(page)
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=f"data:image/png;base64,{screenshot_base64}",
                system_message=DETAIL_PAGE_OPTIONS_SYSTEM
            )
        else:
            response = await self.llm.complete(
                prompt=prompt,
                system_message=DETAIL_PAGE_OPTIONS_SYSTEM,
                response_format={"type": "json_object"} if self.llm.provider == LLMProvider.OPENAI else None
            )
        
        try:
            result = self._extract_json_from_response(response)
            logger.info("상세 페이지 옵션 분석 완료", option_count=len(result))
            return result
        except json.JSONDecodeError as e:
            logger.error("JSON 파싱 실패", error=str(e))
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {response}")
    
    async def analyze_pricing_area(
        self,
        page: Page,
        use_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        가격/정책 영역 분석
        
        Returns:
            Dict: 가격 정보별 셀렉터
            {
                "final_price": {"selector": str, "exists": bool},
                "installment_principal": {...},
                ...
            }
        """
        logger.info("가격 영역 분석 시작")
        
        html_content = await self._extract_simplified_html(page)
        prompt = format_pricing_area_prompt(html_content)
        
        if use_screenshot:
            screenshot_base64 = await self._capture_screenshot_base64(page)
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=f"data:image/png;base64,{screenshot_base64}",
                system_message=PRICING_AREA_SYSTEM
            )
        else:
            response = await self.llm.complete(
                prompt=prompt,
                system_message=PRICING_AREA_SYSTEM,
                response_format={"type": "json_object"} if self.llm.provider == LLMProvider.OPENAI else None
            )
        
        try:
            result = self._extract_json_from_response(response)
            logger.info("가격 영역 분석 완료")
            return result
        except json.JSONDecodeError as e:
            logger.error("JSON 파싱 실패", error=str(e))
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {response}")
    
    async def _extract_simplified_html(self, page: Page, max_length: int = 50000) -> str:
        """
        HTML 추출 (간소화)
        
        Args:
            page: Playwright Page
            max_length: 최대 길이 (토큰 제한)
            
        Returns:
            str: 간소화된 HTML
        """
        # body 내용만 추출
        html = await page.content()
        
        # 너무 길면 잘라내기
        if len(html) > max_length:
            html = html[:max_length] + "...(truncated)"
        
        return html
    
    async def _capture_screenshot_base64(self, page: Page) -> str:
        """스크린샷을 base64로 캡처"""
        screenshot_bytes = await page.screenshot(full_page=False)
        return base64.b64encode(screenshot_bytes).decode('utf-8')
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """
        LLM 응답에서 JSON 추출
        
        Markdown 코드 블록이나 추가 텍스트가 있을 수 있으므로 파싱
        """
        # Markdown 코드 블록 제거
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()
        
        # JSON 파싱
        return json.loads(response.strip())
    
    async def extract_product_urls(
        self,
        page: Page,
        base_url: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        리스트 페이지에서 제품 상세 URL 추출
        
        Args:
            page: Playwright Page 객체
            base_url: 기본 URL (상대경로 처리용)
            
        Returns:
            List[Dict]: 제품 URL 리스트
            [
                {"name": "갤럭시S25", "url": "https://..."},
                ...
            ]
        """
        logger.info("제품 URL 추출 시작")
        
        # 1단계: LLM으로 페이지 구조 분석
        structure = await self.analyze_listing_page(page)
        
        logger.info("페이지 구조 분석 완료", structure=structure)
        
        # 2단계: 선택자로 실제 요소 추출
        product_card_selector = structure.get("product_card_selector", "")
        detail_link_selector = structure.get("detail_link_selector", "")
        product_name_selector = structure.get("product_name_selector", "")
        
        if not product_card_selector or not detail_link_selector:
            logger.error("필수 선택자를 찾지 못함", structure=structure)
            raise ValueError("제품 카드 또는 상세 링크 선택자를 찾을 수 없습니다")
        
        # 3단계: 페이지에서 제품 URL 추출
        products = []
        
        try:
            # Playwright의 query_selector_all로 모든 제품 카드 찾기
            cards = await page.query_selector_all(product_card_selector)
            logger.info(f"제품 카드 {len(cards)}개 발견")
            
            for idx, card in enumerate(cards):
                try:
                    # 상세 링크 추출
                    link_element = await card.query_selector(detail_link_selector)
                    if not link_element:
                        # 카드 자체가 링크일 수도 있음
                        link_element = card
                    
                    href = await link_element.get_attribute("href")
                    if not href:
                        logger.warning(f"제품 카드 {idx}: href 속성 없음")
                        continue
                    
                    # 절대 URL로 변환
                    if base_url:
                        absolute_url = urljoin(base_url, href)
                    else:
                        current_url = page.url
                        absolute_url = urljoin(current_url, href)
                    
                    # 제품명 추출 (선택적)
                    product_name = "N/A"
                    if product_name_selector:
                        try:
                            name_element = await card.query_selector(product_name_selector)
                            if name_element:
                                product_name = await name_element.inner_text()
                                product_name = product_name.strip()
                        except Exception as e:
                            logger.debug(f"제품명 추출 실패 (카드 {idx}): {e}")
                    
                    products.append({
                        "name": product_name,
                        "url": absolute_url
                    })
                    
                except Exception as e:
                    logger.warning(f"제품 카드 {idx} 처리 중 오류", error=str(e))
                    continue
            
            logger.info(f"제품 URL 추출 완료: {len(products)}개")
            return products
            
        except Exception as e:
            logger.error("제품 URL 추출 실패", error=str(e))
            raise
    
    def get_llm_stats(self) -> Dict[str, Any]:
        """LLM 사용량 통계"""
        return self.llm.get_usage_stats()

