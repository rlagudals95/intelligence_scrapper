import pRetry from 'p-retry';
import { Browser, BrowserContext, Page, chromium } from 'playwright';
import { randomDelay } from '../utils/delay.js';
import { getLogger } from '../utils/logger.js';
import { SiteConfig, defaultConfigValues } from './config.js';

const logger = getLogger('BrowserManager');

export class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private config: SiteConfig;

  // 병렬 처리용 추가 페이지들
  private extraPages: Page[] = [];

  constructor(config: Partial<SiteConfig> & { targetUrl: string }) {
    this.config = {
      ...defaultConfigValues,
      ...config,
    } as SiteConfig;
  }

  async start(): Promise<void> {
    logger.info('Starting browser...');

    this.browser = await chromium.launch({
      headless: this.config.headless,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
      ],
    });

    this.context = await this.browser.newContext({
      viewport: {
        width: this.config.viewportWidth,
        height: this.config.viewportHeight,
      },
      userAgent: this.config.userAgent,
      locale: 'ko-KR',
      extraHTTPHeaders: {
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
      },
    });

    await this.context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
      });
    });

    this.page = await this.context.newPage();

    logger.info({ headless: this.config.headless }, 'Browser started successfully');
  }

  async close(): Promise<void> {
    logger.info('Closing browser...');

    if (this.page) {
      await this.page.close().catch(() => {});
      this.page = null;
    }

    if (this.context) {
      await this.context.close().catch(() => {});
      this.context = null;
    }

    if (this.browser) {
      await this.browser.close().catch(() => {});
      this.browser = null;
    }

    logger.info('Browser closed');
  }

  getPage(): Page {
    if (!this.page) {
      throw new Error('Browser not started. Call start() first.');
    }
    return this.page;
  }

  getContext(): BrowserContext {
    if (!this.context) {
      throw new Error('Browser not started. Call start() first.');
    }
    return this.context;
  }

  async goto(url: string, options?: { waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' }): Promise<void> {
    const page = this.getPage();
    // TODO: 다른 사이트도 통신사 선택 페이지 redirect 처리가 필요하다면 로직 변경 필요
    // 하이폰 특수 처리: 통신사 선택 세션이 필요함
    if (url.includes('hi-phone.kr') && !this.hiPhoneCarrierSelected) {
      await this.setupHiPhoneCarrier();
    }

    await pRetry(
      async () => {
        logger.debug({ url }, 'Navigating to URL');
        await page.goto(url, {
          waitUntil: options?.waitUntil || 'networkidle',
          timeout: this.config.timeout,
        });
        logger.debug({ url }, 'Navigation complete');
      },
      {
        retries: this.config.maxRetries,
        minTimeout: this.config.retryDelay * 1000,
        onFailedAttempt: (error) => {
          logger.warn(
            { url, attempt: error.attemptNumber, retriesLeft: error.retriesLeft },
            'Navigation failed, retrying...'
          );
        },
      }
    );
  }

  /**
   * 하이폰 통신사 선택 세션 설정
   * 하이폰은 통신사를 먼저 선택해야 리스팅/상세 페이지에 접근 가능
   * 쿠키 기반으로 세션 설정
   */
  private hiPhoneCarrierSelected = false;

  private async setupHiPhoneCarrier(): Promise<void> {
    const context = this.getContext();

    try {
      logger.info('Setting up hi-phone carrier cookies...');

      // 필수 쿠키 설정 (통신사 선택 세션용)
      // 핵심: my_agency 쿠키가 통신사 선택 상태를 결정함
      const now = Date.now();
      await context.addCookies([
        {
          name: 'my_agency',
          value: 'SKT',  // 기본 통신사로 SKT 선택
          domain: 'hi-phone.kr',
          path: '/',
          expires: Math.floor(Date.now() / 1000) + 86400 * 365, // 1년
        },
        {
          name: 'cartId',
          value: `scraper_cart_${now}`,
          domain: 'hi-phone.kr',
          path: '/',
        },
        {
          name: 'smipUserToken',
          value: `${now.toString(16)}-scraper-token`,
          domain: 'hi-phone.kr',
          path: '/',
          expires: Math.floor(Date.now() / 1000) + 86400 * 365, // 1년
        },
        {
          name: 'smtg_cKey',
          value: now.toString(),
          domain: '.hi-phone.kr',
          path: '/',
          expires: Math.floor(Date.now() / 1000) + 86400,
        },
        {
          name: 'smtg_fsID',
          value: '1',
          domain: '.hi-phone.kr',
          path: '/',
        },
        {
          name: 'smtg_sAd',
          value: '0',
          domain: '.hi-phone.kr',
          path: '/',
        },
        {
          name: 'smtg_sKey',
          value: now.toString(),
          domain: '.hi-phone.kr',
          path: '/',
        },
        {
          name: 'smtg_vTime',
          value: Math.floor(now / 1000).toString(),
          domain: '.hi-phone.kr',
          path: '/',
          expires: Math.floor(Date.now() / 1000) + 86400 * 90,
        },
      ]);

      this.hiPhoneCarrierSelected = true;
      logger.info('Hi-phone cookies set successfully');

    } catch (error) {
      logger.warn({ error }, 'Hi-phone cookie setup failed, trying page-based selection');

      // 쿠키 설정 실패 시 페이지 기반 선택 시도
      await this.setupHiPhoneCarrierViaPage();
    }
  }

  /**
   * 페이지 기반 통신사 선택 (쿠키 방식 실패 시 fallback)
   */
  private async setupHiPhoneCarrierViaPage(): Promise<void> {
    const page = this.getPage();

    try {
      await page.goto('https://hi-phone.kr/index.php', {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
      });

      await randomDelay(1, 2);

      // SKT 클릭 시도
      try {
        await page.click('text=SKT', { timeout: 5000 });
        await randomDelay(1, 2);
        logger.info('Clicked SKT via page');
      } catch {
        logger.warn('Could not click SKT on hi-phone');
      }

      this.hiPhoneCarrierSelected = true;
    } catch (error) {
      logger.warn({ error }, 'Hi-phone page-based setup failed');
      this.hiPhoneCarrierSelected = true;
    }
  }

  async screenshot(options?: { fullPage?: boolean }): Promise<Buffer> {
    const page = this.getPage();
    return await page.screenshot({
      fullPage: options?.fullPage ?? false,
      type: 'png',
    });
  }

  async screenshotBase64(options?: { fullPage?: boolean }): Promise<string> {
    const buffer = await this.screenshot(options);
    return buffer.toString('base64');
  }

  async getHtml(): Promise<string> {
    const page = this.getPage();
    return await page.content();
  }

  async getSimplifiedHtml(): Promise<string> {
    const page = this.getPage();

    return await page.evaluate(() => {
      const clone = document.body.cloneNode(true) as HTMLElement;

      const removeElements = ['script', 'style', 'noscript', 'iframe', 'svg', 'path'];
      removeElements.forEach((tag) => {
        clone.querySelectorAll(tag).forEach((el) => el.remove());
      });

      const removeAttrs = [
        'style',
        'onclick',
        'onload',
        'onerror',
        'onmouseover',
        'onmouseout',
        'onfocus',
        'onblur',
      ];
      clone.querySelectorAll('*').forEach((el) => {
        removeAttrs.forEach((attr) => el.removeAttribute(attr));
      });

      return clone.innerHTML
        .replace(/\s+/g, ' ')
        .replace(/>\s+</g, '><')
        .trim();
    });
  }

  async waitForSelector(selector: string, timeout?: number): Promise<void> {
    const page = this.getPage();
    await page.waitForSelector(selector, { timeout: timeout || this.config.timeout });
  }

  async click(selector: string): Promise<void> {
    const page = this.getPage();
    await page.click(selector);
  }

  async applyRandomDelay(): Promise<void> {
    await randomDelay(this.config.delayMin, this.config.delayMax);
  }

  async evaluate<T>(fn: () => T | Promise<T>): Promise<T> {
    const page = this.getPage();
    return await page.evaluate(fn);
  }

  /**
   * 병렬 처리용 새 페이지 생성
   */
  async createExtraPage(): Promise<Page> {
    const context = this.getContext();
    const newPage = await context.newPage();
    this.extraPages.push(newPage);
    logger.debug({ totalPages: this.extraPages.length + 1 }, 'Created extra page for parallel processing');
    return newPage;
  }

  /**
   * 여러 개의 추가 페이지 생성
   */
  async createExtraPages(count: number): Promise<Page[]> {
    const pages: Page[] = [];
    for (let i = 0; i < count; i++) {
      const page = await this.createExtraPage();
      pages.push(page);
    }
    return pages;
  }

  /**
   * 추가 페이지들 정리
   */
  async closeExtraPages(): Promise<void> {
    for (const page of this.extraPages) {
      try {
        await page.close();
      } catch {
        // Ignore close errors
      }
    }
    this.extraPages = [];
    logger.debug('Closed all extra pages');
  }

  /**
   * 특정 페이지로 URL 이동 (병렬 처리용)
   */
  async gotoWithPage(targetPage: Page, url: string, options?: { waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' }): Promise<void> {
    // 하이폰 특수 처리
    if (url.includes('hi-phone.kr') && !this.hiPhoneCarrierSelected) {
      await this.setupHiPhoneCarrier();
    }

    await pRetry(
      async () => {
        logger.debug({ url }, 'Navigating to URL (parallel)');
        await targetPage.goto(url, {
          waitUntil: options?.waitUntil || 'networkidle',
          timeout: this.config.timeout,
        });
        logger.debug({ url }, 'Navigation complete (parallel)');
      },
      {
        retries: this.config.maxRetries,
        minTimeout: this.config.retryDelay * 1000,
        onFailedAttempt: (error) => {
          logger.warn(
            { url, attempt: error.attemptNumber, retriesLeft: error.retriesLeft },
            'Navigation failed, retrying...'
          );
        },
      }
    );
  }

}
