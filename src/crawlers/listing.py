"""
리스팅 페이지 크롤러 (Phase 2)
LLM 기반 휴대폰 기종 정보 수집
"""
import asyncio
from typing import List, Optional
from urllib.parse import urljoin
from playwright.async_api import Page

from ..core.browser import BrowserManager
from ..core.llm_client import LLMClient
from ..models.schemas import PhoneListingItem
from ..utils.page_analyzer import PageAnalyzer
from ..utils.logger import get_logger
from ..utils.delay import random_delay

logger = get_logger()


class ListingCrawler:
    """
    LLM 기반 리스팅 페이지 크롤러
    
    휴대폰 기종명, 변경유형, 가격, 요금제 등을 수집
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        browser_manager: BrowserManager
    ):
        self.llm = llm_client
        self.browser = browser_manager
        self.page_analyzer = PageAnalyzer(llm_client)
    
    async def crawl(self, listing_url: str) -> List[PhoneListingItem]:
        """
        리스팅 페이지에서 휴대폰 정보 수집
        
        Args:
            listing_url: 리스팅 페이지 URL
            
        Returns:
            List[PhoneListingItem]: 수집된 휴대폰 정보 목록
        """
        logger.info("리스팅 크롤링 시작", url=listing_url)
        
        page = await self.browser.get_page()
        await self.browser.goto(listing_url)
        
        # 페이지 렌더링 대기
        await asyncio.sleep(2)
        
        # 1. LLM으로 페이지 구조 1회 분석
        logger.info("LLM으로 페이지 구조 분석 중...")
        page_structure = await self.page_analyzer.analyze_listing_page(
            page,
            use_screenshot=True
        )
        
        logger.info(
            "페이지 구조 분석 완료",
            product_card_selector=page_structure.get("product_card_selector"),
            pagination_type=page_structure.get("pagination_type")
        )
        
        # 2. 모든 페이지 순회하며 데이터 수집
        all_items = []
        current_page = 1
        
        while True:
            logger.info(f"페이지 {current_page} 수집 중...")
            
            # 현재 페이지에서 데이터 추출
            items = await self._extract_items_from_page(
                page,
                page_structure,
                listing_url
            )
            
            all_items.extend(items)
            logger.info(f"페이지 {current_page}에서 {len(items)}개 상품 수집")
            
            # 페이지네이션 처리
            pagination_type = page_structure.get("pagination_type", "none")
            
            if pagination_type == "pagination":
                has_next = await self._click_next_button(
                    page,
                    page_structure.get("next_button_selector")
                )
                if not has_next:
                    break
            elif pagination_type == "infinite_scroll":
                has_more = await self._scroll_and_wait(page)
                if not has_more:
                    break
            else:
                # 단일 페이지
                break
            
            current_page += 1
            await random_delay(1.0, 2.0)
        
        # 3. 중복 제거 (detail_url 기준)
        unique_items = self._deduplicate_items(all_items)
        
        logger.info(
            "리스팅 크롤링 완료",
            total_collected=len(all_items),
            unique_items=len(unique_items),
            pages=current_page
        )
        
        return unique_items
    
    async def _extract_items_from_page(
        self,
        page: Page,
        page_structure: dict,
        base_url: str
    ) -> List[PhoneListingItem]:
        """
        현재 페이지에서 PhoneListingItem 추출
        
        Args:
            page: Playwright Page
            page_structure: LLM이 분석한 페이지 구조
            base_url: 기준 URL (상대 경로 변환용)
            
        Returns:
            List[PhoneListingItem]: 추출된 아이템 목록
        """
        items = []
        
        product_card_selector = page_structure.get("product_card_selector")
        if not product_card_selector:
            logger.error("상품 카드 셀렉터가 없습니다")
            return items
        
        # 상품 카드 선택
        cards = await page.query_selector_all(product_card_selector)
        logger.debug(f"발견된 상품 카드: {len(cards)}개")
        
        for idx, card in enumerate(cards, 1):
            try:
                item = await self._extract_single_item(
                    card,
                    page_structure,
                    base_url
                )
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"상품 {idx} 추출 실패", error=str(e))
                continue
        
        return items
    
    async def _extract_single_item(
        self,
        card,
        page_structure: dict,
        base_url: str
    ) -> Optional[PhoneListingItem]:
        """
        단일 상품 카드에서 PhoneListingItem 추출
        """
        try:
            # 필수: 기종명
            model_name = await self._extract_text(
                card,
                page_structure.get("product_name_selector", "")
            )
            if not model_name:
                return None
            
            # 필수: 상세 URL
            detail_url = await self._extract_link(
                card,
                page_structure.get("detail_link_selector", "a")
            )
            if not detail_url:
                return None
            
            # 절대 URL 변환
            detail_url = urljoin(base_url, detail_url)
            
            # 선택: 변경유형
            signup_type = await self._extract_text(
                card,
                page_structure.get("signup_type_selector", "")
            )
            
            # 선택: 출고가
            retail_price = await self._extract_text(
                card,
                page_structure.get("retail_price_selector", "")
            )
            
            # 선택: 할인가/최종가
            discount_price = await self._extract_text(
                card,
                page_structure.get("discount_price_selector", "")
            )
            
            # 선택: 요금제
            plan_name = await self._extract_text(
                card,
                page_structure.get("plan_name_selector", "")
            )
            
            # 선택: 이미지
            image_url = await self._extract_image(
                card,
                page_structure.get("image_selector", "img")
            )
            if image_url:
                image_url = urljoin(base_url, image_url)
            
            return PhoneListingItem(
                model_name=model_name.strip(),
                signup_type=signup_type.strip() if signup_type else None,
                retail_price=retail_price.strip() if retail_price else None,
                discount_price=discount_price.strip() if discount_price else None,
                plan_name=plan_name.strip() if plan_name else None,
                detail_url=detail_url,
                image_url=image_url,
                list_url=base_url
            )
        
        except Exception as e:
            logger.debug(f"아이템 추출 실패: {e}")
            return None
    
    async def _extract_text(self, element, selector: str) -> Optional[str]:
        """요소에서 텍스트 추출"""
        if not selector:
            # 셀렉터가 없으면 요소 자체의 텍스트
            try:
                return await element.inner_text()
            except:
                return None
        
        try:
            target = await element.query_selector(selector)
            if target:
                return await target.inner_text()
        except:
            pass
        return None
    
    async def _extract_link(self, element, selector: str) -> Optional[str]:
        """요소에서 링크(href) 추출"""
        try:
            target = await element.query_selector(selector)
            if target:
                return await target.get_attribute("href")
        except:
            pass
        return None
    
    async def _extract_image(self, element, selector: str) -> Optional[str]:
        """요소에서 이미지(src) 추출"""
        try:
            target = await element.query_selector(selector)
            if target:
                return await target.get_attribute("src")
        except:
            pass
        return None
    
    async def _click_next_button(
        self,
        page: Page,
        next_button_selector: Optional[str]
    ) -> bool:
        """
        다음 페이지 버튼 클릭
        
        Returns:
            bool: 성공 여부
        """
        if not next_button_selector:
            return False
        
        try:
            button = await page.query_selector(next_button_selector)
            if not button:
                return False
            
            # 버튼이 비활성화되어 있는지 확인
            is_disabled = await button.is_disabled()
            if is_disabled:
                return False
            
            # 클릭
            await button.click()
            await asyncio.sleep(2)  # 페이지 로딩 대기
            
            return True
        except Exception as e:
            logger.debug(f"다음 버튼 클릭 실패: {e}")
            return False
    
    async def _scroll_and_wait(self, page: Page) -> bool:
        """
        스크롤 후 새 컨텐츠 로딩 대기
        
        Returns:
            bool: 새 컨텐츠가 로드되었는지
        """
        try:
            previous_height = await page.evaluate("document.body.scrollHeight")
            
            # 스크롤 다운
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
            # 새 높이 확인
            current_height = await page.evaluate("document.body.scrollHeight")
            
            return current_height > previous_height
        except Exception as e:
            logger.debug(f"스크롤 실패: {e}")
            return False
    
    def _deduplicate_items(
        self,
        items: List[PhoneListingItem]
    ) -> List[PhoneListingItem]:
        """
        detail_url 기준으로 중복 제거
        """
        seen_urls = set()
        unique_items = []
        
        for item in items:
            if item.detail_url not in seen_urls:
                seen_urls.add(item.detail_url)
                unique_items.append(item)
        
        return unique_items
