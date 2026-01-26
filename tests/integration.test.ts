import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import 'dotenv/config';
import { BrowserManager } from '../src/core/browser.js';
import { LLMClient } from '../src/core/llm-client.js';
import { ListingCrawler } from '../src/crawlers/listing.js';
import { defaultConfigValues } from '../src/core/config.js';

describe('Integration: Browser', () => {
  let browser: BrowserManager;

  beforeAll(async () => {
    browser = new BrowserManager({
      ...defaultConfigValues,
      targetUrl: 'https://example.com',
      headless: true,
    });
    await browser.start();
  });

  afterAll(async () => {
    await browser.close();
  });

  it('should navigate to URL and get HTML', async () => {
    await browser.goto('https://example.com');

    const html = await browser.getHtml();
    expect(html).toContain('Example Domain');
  });

  it('should take screenshot', async () => {
    await browser.goto('https://example.com');

    const screenshot = await browser.screenshot();
    expect(screenshot).toBeInstanceOf(Buffer);
    expect(screenshot.length).toBeGreaterThan(0);
  });

  it('should get simplified HTML', async () => {
    await browser.goto('https://example.com');

    const simplifiedHtml = await browser.getSimplifiedHtml();
    expect(simplifiedHtml).not.toContain('<script');
    expect(simplifiedHtml).not.toContain('<style');
  });
});

describe('Integration: LLM Client', () => {
  it('should initialize with detected provider', () => {
    // Skip if no API key
    if (
      !process.env.OPENAI_API_KEY &&
      !process.env.ANTHROPIC_API_KEY &&
      !process.env.GEMINI_API_KEY
    ) {
      console.log('Skipping LLM test: No API key found');
      return;
    }

    const client = new LLMClient();
    const provider = client.getProvider();

    expect(['openai', 'anthropic', 'gemini']).toContain(provider);
  });

  it('should complete simple prompt', async () => {
    // Skip if no API key
    if (
      !process.env.OPENAI_API_KEY &&
      !process.env.ANTHROPIC_API_KEY &&
      !process.env.GEMINI_API_KEY
    ) {
      console.log('Skipping LLM test: No API key found');
      return;
    }

    const client = new LLMClient();
    const response = await client.complete(
      'You are a helpful assistant.',
      'Respond with only: {"status": "ok"}'
    );

    expect(response.content).toContain('ok');
  }, 30000);
});

describe('Integration: Listing Page Analysis', () => {
  let browser: BrowserManager;
  let llmClient: LLMClient;

  beforeAll(async () => {
    // Skip if no API key
    if (
      !process.env.OPENAI_API_KEY &&
      !process.env.ANTHROPIC_API_KEY &&
      !process.env.GEMINI_API_KEY
    ) {
      return;
    }

    browser = new BrowserManager({
      ...defaultConfigValues,
      targetUrl: 'https://hi-phone.kr/index.php?channel=list&cate=103001000000',
      headless: true,
    });
    llmClient = new LLMClient();
    await browser.start();
  });

  afterAll(async () => {
    if (browser) {
      await browser.close();
    }
  });

  it('should extract products from 하이폰 listing page', async () => {
    // Skip if no API key
    if (
      !process.env.OPENAI_API_KEY &&
      !process.env.ANTHROPIC_API_KEY &&
      !process.env.GEMINI_API_KEY
    ) {
      console.log('Skipping integration test: No API key found');
      return;
    }

    const crawler = new ListingCrawler(browser, llmClient, { maxPages: 1 });
    const url = 'https://hi-phone.kr/index.php?channel=list&cate=103001000000';

    const items = await crawler.crawl(url);

    console.log(`\n📱 추출된 상품 수: ${items.length}`);
    items.slice(0, 3).forEach((item, i) => {
      console.log(`  ${i + 1}. ${item.modelName}`);
      console.log(`     URL: ${item.detailUrl.slice(0, 50)}...`);
    });

    expect(items.length).toBeGreaterThan(0);
    expect(items[0].modelName).toBeTruthy();
    expect(items[0].detailUrl).toContain('http');
  }, 120000);
});
