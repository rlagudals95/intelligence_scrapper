"""
브라우저 관리 (Playwright Browser Manager)
"""
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import SiteConfig
from ..utils.logger import get_logger

logger = get_logger()


class BrowserManager:
    """Playwright 브라우저 관리"""
    
    def __init__(self, config: SiteConfig):
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()
    
    async def start(self):
        """브라우저 시작"""
        logger.info("브라우저 시작")
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self._context = await self._browser.new_context(
            user_agent=self.config.user_agent,
            viewport={
                'width': self.config.viewport_width,
                'height': self.config.viewport_height
            },
            # 자동화 감지 방지
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        )
        
        # 타임아웃 설정
        self._context.set_default_timeout(self.config.timeout)
        self._context.set_default_navigation_timeout(self.config.timeout)
        
        self._page = await self._context.new_page()
        
        logger.info("브라우저 시작 완료")
    
    async def close(self):
        """브라우저 종료"""
        logger.info("브라우저 종료")
        
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        
        logger.info("브라우저 종료 완료")
    
    async def get_page(self) -> Page:
        """현재 페이지 반환"""
        if not self._page:
            raise RuntimeError("브라우저가 시작되지 않았습니다. start()를 먼저 호출하세요.")
        return self._page
    
    async def new_page(self) -> Page:
        """새 페이지 생성"""
        if not self._context:
            raise RuntimeError("브라우저가 시작되지 않았습니다. start()를 먼저 호출하세요.")
        
        page = await self._context.new_page()
        logger.info("새 페이지 생성")
        return page
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def goto(self, url: str, wait_until: str = "networkidle") -> Page:
        """URL로 이동 (재시도 포함)"""
        page = await self.get_page()
        
        logger.info(f"페이지 이동: {url}")
        
        try:
            await page.goto(url, wait_until=wait_until, timeout=self.config.timeout)
            logger.info(f"페이지 로딩 완료: {url}")
            return page
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url}", error=str(e))
            raise
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible"
    ):
        """셀렉터 대기"""
        page = await self.get_page()
        timeout = timeout or self.config.timeout
        
        try:
            await page.wait_for_selector(selector, timeout=timeout, state=state)
        except Exception as e:
            logger.warning(f"셀렉터 대기 실패: {selector}", error=str(e))
            raise
    
    async def wait_for_load_state(self, state: str = "networkidle"):
        """페이지 로드 상태 대기"""
        page = await self.get_page()
        await page.wait_for_load_state(state, timeout=self.config.timeout)
    
    async def scroll_to_bottom(self, step: int = 500, delay: float = 0.5):
        """페이지 끝까지 스크롤"""
        page = await self.get_page()
        
        previous_height = await page.evaluate("document.body.scrollHeight")
        
        while True:
            # 스크롤 다운
            await page.evaluate(f"window.scrollBy(0, {step})")
            await asyncio.sleep(delay)
            
            # 새 높이 확인
            current_height = await page.evaluate("window.scrollHeight")
            current_scroll = await page.evaluate("window.pageYOffset + window.innerHeight")
            
            # 끝에 도달했는지 확인
            if current_scroll >= current_height:
                # 추가 컨텐츠 로딩 대기
                await asyncio.sleep(delay * 2)
                new_height = await page.evaluate("document.body.scrollHeight")
                
                # 더 이상 새 컨텐츠가 없으면 종료
                if new_height == previous_height:
                    break
                
                previous_height = new_height
    
    async def screenshot(self, path: str, full_page: bool = False):
        """스크린샷 저장"""
        page = await self.get_page()
        await page.screenshot(path=path, full_page=full_page)
        logger.info(f"스크린샷 저장: {path}")

