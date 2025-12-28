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
            pagination_type=page_structure.get("pagination_type"),
            public_subsidy_selector=page_structure.get("public_subsidy_selector"),
            additional_subsidy_selector=page_structure.get("additional_subsidy_selector")
        )
        
        # 2. 모든 페이지 순회하며 데이터 수집
        all_items = []
        current_page = 1
        no_new_items_count = 0
        max_no_new_items = 3  # 3번 연속 새 상품이 없으면 중단
        
        while True:
            logger.info(f"페이지 {current_page} 수집 중...")
            
            previous_total = len(all_items)
            
            # 현재 페이지에서 데이터 추출
            items = await self._extract_items_from_page(
                page,
                page_structure,
                listing_url
            )
            
            all_items.extend(items)
            new_items_count = len(all_items) - previous_total
            
            logger.info(f"페이지 {current_page}에서 {len(items)}개 상품 발견, {new_items_count}개 신규")
            
            # 새 상품이 없으면 카운트 증가
            if new_items_count == 0:
                no_new_items_count += 1
                if no_new_items_count >= max_no_new_items:
                    logger.info(f"{max_no_new_items}번 연속 새 상품 없음, 수집 중단")
                    break
            else:
                no_new_items_count = 0
            
            # 페이지네이션 처리
            pagination_type = page_structure.get("pagination_type", "none")
            
            if pagination_type == "pagination":
                has_next = await self._click_next_button(
                    page,
                    page_structure.get("next_button_selector")
                )
                if not has_next:
                    logger.info("다음 버튼 없음 또는 클릭 실패, 수집 중단")
                    break
            elif pagination_type == "infinite_scroll":
                has_more = await self._scroll_and_wait(page)
                if not has_more:
                    logger.info("더 이상 스크롤할 컨텐츠 없음, 수집 중단")
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
            
            # 선택: 통신사
            carrier = await self._extract_text(
                card,
                page_structure.get("carrier_selector", "")
            )
            
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
            
            # 선택: 지원금 타입 (공시지원, 선택약정)
            subsidy_type = await self._extract_text(
                card,
                page_structure.get("subsidy_type_selector", "")
            )
            
            # 선택: 공시지원금
            public_subsidy_selector = page_structure.get("public_subsidy_selector", "")
            public_subsidy = await self._extract_text(card, public_subsidy_selector)
            
            # 지원금은 반드시 유효한 금액 형식이어야 함 (4자리 이상 숫자 또는 콤마 포함)
            if public_subsidy:
                if self._is_valid_subsidy_amount(public_subsidy):
                    # 레이블과 단위 제거, 숫자와 콤마만 추출
                    public_subsidy = self._clean_subsidy_amount(public_subsidy)
                else:
                    public_subsidy = None
            
            # 선택: 추가지원금
            additional_subsidy_selector = page_structure.get("additional_subsidy_selector", "")
            additional_subsidy = await self._extract_text(card, additional_subsidy_selector)
            
            # 지원금은 반드시 유효한 금액 형식이어야 함 (4자리 이상 숫자 또는 콤마 포함)
            if additional_subsidy:
                if self._is_valid_subsidy_amount(additional_subsidy):
                    # 레이블과 단위 제거, 숫자와 콤마만 추출
                    additional_subsidy = self._clean_subsidy_amount(additional_subsidy)
                else:
                    additional_subsidy = None
            
            # 선택: 요금제
            plan_name = await self._extract_text(
                card,
                page_structure.get("plan_name_selector", "")
            )
            
            # 선택: 혜택
            benefits = await self._extract_text(
                card,
                page_structure.get("benefits_selector", "")
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
                carrier=carrier.strip() if carrier else None,
                signup_type=signup_type.strip() if signup_type else None,
                retail_price=retail_price.strip() if retail_price else None,
                discount_price=discount_price.strip() if discount_price else None,
                subsidy_type=subsidy_type.strip() if subsidy_type else None,
                public_subsidy=public_subsidy.strip() if public_subsidy else None,
                additional_subsidy=additional_subsidy.strip() if additional_subsidy else None,
                plan_name=plan_name.strip() if plan_name else None,
                benefits=benefits.strip() if benefits else None,
                detail_url=detail_url,
                image_url=image_url,
                list_url=base_url
            )
        
        except Exception as e:
            logger.debug(f"아이템 추출 실패: {e}")
            return None
    
    def _is_valid_subsidy_amount(self, text: str) -> bool:
        """
        지원금 금액이 유효한지 확인
        - 최소 4자리 이상의 숫자가 있어야 함
        - 또는 콤마(,)가 포함되어 있어야 함 (예: "600,000")
        - "5G", "4G" 같은 것은 제외
        """
        if not text:
            return False
        
        # 콤마가 있으면 금액일 가능성이 높음
        if ',' in text:
            return True
        
        # 연속된 숫자가 4자리 이상인지 확인
        digit_count = 0
        max_consecutive_digits = 0
        
        for char in text:
            if char.isdigit():
                digit_count += 1
                max_consecutive_digits = max(max_consecutive_digits, digit_count)
            else:
                digit_count = 0
        
        # 4자리 이상 연속된 숫자가 있으면 금액으로 간주
        return max_consecutive_digits >= 4
    
    def _clean_subsidy_amount(self, text: str) -> Optional[str]:
        """
        지원금 금액에서 숫자와 콤마만 추출
        예: "공통지원금 : 600,000원" → "600,000"
        예: "배달의폰 제휴할인 : 820,000원" → "820,000"
        예: "739,300" → "739,300"
        
        Returns:
            정리된 금액 문자열, 유효하지 않으면 None
        """
        if not text:
            return None
        
        # 숫자와 콤마만 추출
        cleaned = ''.join(char for char in text if char.isdigit() or char == ',')
        
        if not cleaned:
            return None
        
        # 숫자만 추출 (콤마 제거)
        digits_only = cleaned.replace(',', '')
        
        # 너무 길면 (15자리 이상) 잘못 추출된 것으로 간주
        # 일반적인 지원금: 100,000 ~ 2,000,000 (6~7자리)
        if len(digits_only) > 10:
            return None
        
        # 너무 짧으면 (3자리 이하) 무효
        if len(digits_only) < 4:
            return None
        
        return cleaned
    
    async def _extract_text(self, element, selector: str) -> Optional[str]:
        """
        요소에서 텍스트 추출
        
        LLM이 태그명을 잘못 선택한 경우를 대비해 fallback 로직 포함:
        1. 원래 셀렉터로 시도
        2. 실패하면 태그명을 제거하고 클래스명만으로 시도
        """
        if not selector:
            # 셀렉터가 없으면 요소 자체의 텍스트
            try:
                return await element.inner_text()
            except:
                return None
        
        # 1차 시도: 원래 셀렉터
        try:
            target = await element.query_selector(selector)
            if target:
                return await target.inner_text()
        except:
            pass
        
        # 2차 시도: 태그명 제거하고 클래스명만으로 시도
        # 예: "b.icp" → ".icp", "div.list-sale > ul > li:nth-child(2) b.icp" → "div.list-sale > ul > li:nth-child(2) .icp"
        if selector and (' ' in selector or '>' in selector):
            # 복잡한 셀렉터: 마지막 부분만 태그명 제거
            parts = selector.split()
            if len(parts) > 0:
                last_part = parts[-1]
                if '.' in last_part and not last_part.startswith('.'):
                    # 태그명.클래스명 형태
                    class_only = '.' + last_part.split('.', 1)[1]
                    fallback_selector = ' '.join(parts[:-1] + [class_only])
                    try:
                        target = await element.query_selector(fallback_selector)
                        if target:
                            logger.debug(f"셀렉터 fallback 성공: {selector} → {fallback_selector}")
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
        다음 페이지 버튼 또는 "더보기" 버튼 클릭
        
        Returns:
            bool: 성공 여부 (새 컨텐츠가 로드되었는지)
        """
        if not next_button_selector:
            return False
        
        try:
            button = await page.query_selector(next_button_selector)
            if not button:
                logger.debug(f"버튼을 찾을 수 없음: {next_button_selector}")
                return False
            
            # 버튼이 보이는지 확인
            is_visible = await button.is_visible()
            if not is_visible:
                logger.debug("버튼이 보이지 않음")
                return False
            
            # 버튼이 비활성화되어 있는지 확인
            is_disabled = await button.is_disabled()
            if is_disabled:
                logger.debug("버튼이 비활성화됨")
                return False
            
            # 클릭 전 상품 수 확인
            try:
                previous_count = await page.evaluate("""
                    () => document.querySelectorAll('*').length
                """)
            except:
                previous_count = 0
            
            # 버튼 클릭
            logger.debug(f"버튼 클릭: {next_button_selector}")
            await button.click()
            
            # 새 컨텐츠 로딩 대기 (최대 5초)
            for i in range(10):
                await asyncio.sleep(0.5)
                
                try:
                    current_count = await page.evaluate("""
                        () => document.querySelectorAll('*').length
                    """)
                    
                    # DOM 요소가 증가했으면 새 컨텐츠가 로드됨
                    if current_count > previous_count:
                        logger.debug(f"새 컨텐츠 로드됨 ({previous_count} → {current_count} 요소)")
                        await asyncio.sleep(1)  # 추가 안정화 대기
                        return True
                except:
                    pass
            
            # 타임아웃: 새 컨텐츠가 로드되지 않음
            logger.debug("새 컨텐츠가 로드되지 않음 (타임아웃)")
            return False
            
        except Exception as e:
            logger.debug(f"버튼 클릭 실패: {e}")
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
