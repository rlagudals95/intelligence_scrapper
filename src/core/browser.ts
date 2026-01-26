import { chromium, Browser, BrowserContext, Page } from 'playwright';
import pRetry from 'p-retry';
import { SiteConfig, defaultConfigValues } from './config.js';
import { getLogger } from '../utils/logger.js';
import { randomDelay } from '../utils/delay.js';

const logger = getLogger('BrowserManager');

export class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private config: SiteConfig;

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

}
