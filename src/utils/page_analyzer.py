"""
Page Analyzer (Phase 2)
LLM을 활용한 페이지 구조 분석
"""
import json
import base64
from typing import Dict, Any, Optional
from playwright.async_api import Page

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


class PageAnalyzer:
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
        
        logger.info("PageAnalyzer 초기화", provider=provider.value)
    
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
    
    def get_llm_stats(self) -> Dict[str, Any]:
        """LLM 사용량 통계"""
        return self.llm.get_usage_stats()

