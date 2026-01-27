import { Page } from 'playwright';
import { BrowserManager } from '../core/browser.js';
import { LLMClient } from '../core/llm-client.js';
import { ListPageAnalyzer, ListingAnalysisResult } from '../utils/list-page-analyzer.js';
import { PhoneListingItem, PhoneListingItemSchema } from '../models/schemas.js';
import { getLogger } from '../utils/logger.js';
import { randomDelay } from '../utils/delay.js';
import { getSelectorCache, SelectorCacheEntry } from '../utils/selector-cache.js';

const logger = getLogger('ListingCrawler');

export interface ListingCrawlerOptions {
  maxPages?: number;
  useScreenshot?: boolean;
}

export class ListingCrawler {
  private browser: BrowserManager;
  private llmClient: LLMClient;
  private analyzer: ListPageAnalyzer;
  private options: Required<ListingCrawlerOptions>;

  constructor(browser: BrowserManager, llmClient: LLMClient, options: ListingCrawlerOptions = {}) {
    this.browser = browser;
    this.llmClient = llmClient;
    this.analyzer = new ListPageAnalyzer(llmClient);
    this.options = {
      maxPages: options.maxPages ?? 100,
      useScreenshot: options.useScreenshot ?? true,
    };
  }

  // Generic product card selectors to try as fallback (not site-specific)
  private static readonly FALLBACK_CARD_SELECTORS = [
    '.product-card',
    '.product-item',
    '.goods-item',
    '.phone-item',
    '.item-box',
    'li.default',  // 일반적인 리스트 아이템
    '[class*="product"]',
    '[class*="goods"]',
    '[class*="item"]',
  ];

  /**
   * Crawl listing page and extract all product items
   */
  async crawl(listingUrl: string): Promise<PhoneListingItem[]> {
    logger.info({ url: listingUrl }, 'Starting listing page crawl');

    // Navigate to listing page
    await this.browser.goto(listingUrl);
    await randomDelay(1, 2);

    const selectorCache = getSelectorCache();
    const page = this.browser.getPage();
    let pageStructure: ListingAnalysisResult;

    // Step 1: Try cached selectors first
    const cachedEntry = selectorCache.get(listingUrl);
    if (cachedEntry) {
      logger.info({ url: listingUrl }, 'Trying cached selectors');
      const workingSelector = await this.trySelectorsFromCache(page, cachedEntry);

      if (workingSelector) {
        logger.info({ selector: workingSelector }, 'Cache hit - using cached selector');
        // Promote working selector and build page structure
        selectorCache.promoteSelector(listingUrl, 'product_card_selectors', workingSelector);
        pageStructure = this.buildPageStructureFromCache(cachedEntry, workingSelector);
      } else {
        logger.warn('Cached selectors failed, falling back to LLM inference');
        selectorCache.recordFailure(listingUrl);
        pageStructure = await this.analyzWithLLMAndCache(listingUrl, selectorCache);
      }
    } else {
      // Step 2: Cache miss - use LLM inference
      logger.info({ url: listingUrl }, 'Cache miss - using LLM inference');
      pageStructure = await this.analyzWithLLMAndCache(listingUrl, selectorCache);
    }

    // Validate and fix product card selector if needed
    pageStructure = await this.validateAndFixSelectors(pageStructure);

    logger.info(
      {
        productCardSelector: pageStructure.product_card_selector,
        paginationType: pageStructure.pagination_type,
      },
      'Page structure analyzed'
    );

    // Extract products from all pages
    const allItems: PhoneListingItem[] = [];
    let currentPage = 1;

    while (currentPage <= this.options.maxPages) {
      logger.info({ page: currentPage }, 'Processing page');

      // Extract products from current page
      const items = await this.extractProductsFromPage(pageStructure);
      logger.info({ count: items.length, page: currentPage }, 'Products extracted from page');

      allItems.push(...items);

      // Handle pagination
      if (pageStructure.pagination_type === 'none') {
        break;
      }

      const hasNextPage = await this.goToNextPage(pageStructure);
      if (!hasNextPage) {
        logger.info('No more pages');
        break;
      }

      currentPage++;
      await randomDelay(1, 3);
    }

    // Deduplicate by detail URL
    const uniqueItems = this.deduplicateItems(allItems);

    // Record success if we extracted items
    if (uniqueItems.length > 0) {
      const selectorCache = getSelectorCache();
      const qualityScore = Math.min(100, Math.round((uniqueItems.length / Math.max(1, allItems.length)) * 100));
      selectorCache.recordSuccess(listingUrl, qualityScore);
    }

    logger.info(
      {
        totalExtracted: allItems.length,
        uniqueItems: uniqueItems.length,
        pages: currentPage,
      },
      'Listing crawl complete'
    );

    return uniqueItems;
  }

  /**
   * Extract products from current page
   */
  private async extractProductsFromPage(
    pageStructure: ListingAnalysisResult
  ): Promise<PhoneListingItem[]> {
    const page = this.browser.getPage();

    const items = await page.evaluate(
      (selectors) => {
        const results: Array<{
          modelName: string;
          signupType?: string;
          retailPrice?: string;
          discountPrice?: string;
          planName?: string;
          detailUrl: string;
          imageUrl?: string;
          subsidy?: string;
        }> = [];

        const cards = document.querySelectorAll(selectors.productCardSelector);

        cards.forEach((card) => {
          try {
            // Extract model name - use robust multi-strategy approach
            let modelName: string | null = null;

            // Strategy 1: Common product name selectors
            const nameSelectors = [
              '.product-name a',
              '.product-name',
              '.model-name',
              '.phone-name',
              '.txt .name',    // 딜리버리폰
              '.name',         // Generic
              'h3 a',
              'h4 a',
              '.title a',
              '.title',
              '.name a',
              '.goods-name',   // 폰슐랭
              '.goodsName',    // 엘지티샵
              'p.name',        // 딜리버리폰 specific
            ];
            for (const nameSel of nameSelectors) {
              const el = card.querySelector(nameSel);
              const text = el?.textContent?.trim();
              if (text && text.length > 2) {
                modelName = text;
                break;
              }
            }

            // Strategy 2: Find any link with meaningful text
            if (!modelName) {
              const links = card.querySelectorAll('a');
              for (const link of links) {
                const text = link.textContent?.trim() || '';
                // Skip empty, too short, or "view" type links
                if (text.length > 2 && text.indexOf('보기') === -1 && text.indexOf('조건') === -1) {
                  modelName = text;
                  break;
                }
              }
            }

            // Strategy 3: Try image alt attribute
            if (!modelName) {
              const img = card.querySelector('img[alt]') as HTMLImageElement;
              if (img?.alt && img.alt.length > 2) {
                modelName = img.alt;
              }
            }

            if (!modelName) return;

            // Extract detail URL
            let detailUrl = '';

            // Strategy 1: Find link with href containing view/detail/product
            const viewLink = card.querySelector('a[href*="view"], a[href*="detail"], a[href*="product"], a[href*="uid"]') as HTMLAnchorElement;
            if (viewLink) {
              detailUrl = viewLink.href || viewLink.getAttribute('href') || '';
            }

            // Strategy 2: First link with href
            if (!detailUrl) {
              const anyLink = card.querySelector('a[href]') as HTMLAnchorElement;
              detailUrl = anyLink?.href || anyLink?.getAttribute('href') || '';
            }

            if (!detailUrl) return;

            // Make URL absolute if relative
            if (detailUrl.startsWith('/')) {
              detailUrl = window.location.origin + detailUrl;
            } else if (!detailUrl.startsWith('http')) {
              detailUrl = window.location.origin + '/' + detailUrl;
            }

            // Extract optional fields (inlined to avoid __name transpilation issue)
            let signupType: string | undefined;
            let retailPrice: string | undefined;
            let discountPrice: string | undefined;
            let planName: string | undefined;
            let imageUrl: string | undefined;
            let subsidy: string | undefined;

            if (selectors.signupTypeSelector) {
              const el = card.querySelector(selectors.signupTypeSelector);
              signupType = el?.textContent?.trim() || undefined;
            }
            if (selectors.retailPriceSelector) {
              const el = card.querySelector(selectors.retailPriceSelector);
              retailPrice = el?.textContent?.trim() || undefined;
            }
            if (selectors.discountPriceSelector) {
              const el = card.querySelector(selectors.discountPriceSelector);
              discountPrice = el?.textContent?.trim() || undefined;
            }
            if (selectors.planNameSelector) {
              const el = card.querySelector(selectors.planNameSelector);
              planName = el?.textContent?.trim() || undefined;
            }
            if (selectors.imageSelector) {
              const imgEl = card.querySelector(selectors.imageSelector) as HTMLImageElement;
              imageUrl = imgEl?.src || undefined;
            }
            if (selectors.publicSubsidySelector) {
              const el = card.querySelector(selectors.publicSubsidySelector);
              subsidy = el?.textContent?.trim() || undefined;
            }

            results.push({
              modelName,
              signupType,
              retailPrice,
              discountPrice,
              planName,
              detailUrl,
              imageUrl,
              subsidy,
            });
          } catch {
            // Skip invalid cards
          }
        });

        return results;
      },
      {
        productCardSelector: pageStructure.product_card_selector,
        productNameSelector: pageStructure.product_name_selector,
        detailLinkSelector: pageStructure.detail_link_selector,
        signupTypeSelector: pageStructure.signup_type_selector,
        retailPriceSelector: pageStructure.retail_price_selector,
        discountPriceSelector: pageStructure.discount_price_selector,
        planNameSelector: pageStructure.plan_name_selector,
        imageSelector: pageStructure.image_selector,
        publicSubsidySelector: pageStructure.public_subsidy_selector,
      }
    );

    // Validate and parse each item
    return items
      .map((item) => {
        try {
          return PhoneListingItemSchema.parse(item);
        } catch {
          logger.warn({ item }, 'Invalid listing item, skipping');
          return null;
        }
      })
      .filter((item): item is PhoneListingItem => item !== null);
  }

  /**
   * Go to next page based on pagination type
   */
  private async goToNextPage(pageStructure: ListingAnalysisResult): Promise<boolean> {
    const page = this.browser.getPage();

    if (pageStructure.pagination_type === 'pagination' && pageStructure.next_button_selector) {
      try {
        const nextButton = await page.$(pageStructure.next_button_selector);
        if (!nextButton) {
          return false;
        }

        // Check if button is disabled
        const isDisabled = await nextButton.evaluate((el) => {
          return (
            el.hasAttribute('disabled') ||
            el.classList.contains('disabled') ||
            el.getAttribute('aria-disabled') === 'true'
          );
        });

        if (isDisabled) {
          return false;
        }

        await nextButton.click();
        await page.waitForLoadState('networkidle');
        return true;
      } catch (error) {
        logger.warn({ error }, 'Failed to click next button');
        return false;
      }
    }

    if (pageStructure.pagination_type === 'infinite_scroll') {
      try {
        // Get current scroll height
        const previousHeight = await page.evaluate(() => document.body.scrollHeight);

        // Scroll to bottom
        await page.evaluate(() => {
          window.scrollTo(0, document.body.scrollHeight);
        });

        // Wait for new content
        await page.waitForTimeout(2000);

        // Check if new content loaded
        const newHeight = await page.evaluate(() => document.body.scrollHeight);

        return newHeight > previousHeight;
      } catch (error) {
        logger.warn({ error }, 'Failed to scroll for more content');
        return false;
      }
    }

    return false;
  }

  /**
   * Deduplicate items by detail URL
   */
  private deduplicateItems(items: PhoneListingItem[]): PhoneListingItem[] {
    const seen = new Set<string>();
    return items.filter((item) => {
      if (seen.has(item.detailUrl)) {
        return false;
      }
      seen.add(item.detailUrl);
      return true;
    });
  }

  /**
   * Validate selectors and try fallbacks if they don't find elements or extractable content
   */
  private async validateAndFixSelectors(
    pageStructure: ListingAnalysisResult
  ): Promise<ListingAnalysisResult> {
    const page = this.browser.getPage();

    // Check if product card selector finds elements with extractable content
    const cardCount = await page.locator(pageStructure.product_card_selector).count();

    if (cardCount > 0) {
      // Verify that we can actually extract product names from these cards
      const canExtract = await this.canExtractFromSelector(page, pageStructure.product_card_selector);
      if (canExtract) {
        logger.info(
          { selector: pageStructure.product_card_selector, count: cardCount },
          'Product card selector validated'
        );
        return pageStructure;
      } else {
        logger.warn(
          { selector: pageStructure.product_card_selector, count: cardCount },
          'Product card selector found elements but cannot extract products, trying fallbacks'
        );
      }
    } else {
      logger.warn(
        { selector: pageStructure.product_card_selector },
        'Product card selector found 0 elements, trying fallbacks'
      );
    }

    // Try fallback selectors
    for (const fallbackSelector of ListingCrawler.FALLBACK_CARD_SELECTORS) {
      const count = await page.locator(fallbackSelector).count();
      if (count > 0) {
        const canExtract = await this.canExtractFromSelector(page, fallbackSelector);
        if (!canExtract) continue;

        logger.info(
          { fallbackSelector, count },
          'Found working fallback selector'
        );

        // Return updated structure with working selector
        return {
          ...pageStructure,
          product_card_selector: fallbackSelector,
          // Reset name/link selectors since they were based on wrong card
          product_name_selector: 'a',
          detail_link_selector: 'a[href]',
        };
      }
    }

    logger.warn('No fallback selector found elements');
    return pageStructure;
  }

  /**
   * Check if we can extract at least one product from the given selector
   */
  private async canExtractFromSelector(page: Page, cardSelector: string): Promise<boolean> {
    const extracted = await page.evaluate((selector) => {
      const cards = document.querySelectorAll(selector);
      if (cards.length === 0) return false;

      // Check if any card has extractable name and link
      for (const card of cards) {
        // Try to find name
        const nameSelectors = [
          '.product-name a', '.product-name', '.txt .name', '.name',
          'h3 a', 'h4 a', '.title a', '.title', 'p.name'
        ];
        let hasName = false;
        for (const sel of nameSelectors) {
          const el = card.querySelector(sel);
          const text = el?.textContent?.trim();
          if (text && text.length > 2) {
            hasName = true;
            break;
          }
        }

        // Try to find link
        const link = card.querySelector('a[href*="view"], a[href*="detail"], a[href]');
        const hasLink = !!link;

        if (hasName && hasLink) {
          return true;  // Found at least one extractable card
        }
      }
      return false;
    }, cardSelector);

    return extracted;
  }

  /**
   * Try selectors from cache in priority order
   * Returns the first working selector or null
   */
  private async trySelectorsFromCache(
    page: Page,
    cachedEntry: SelectorCacheEntry
  ): Promise<string | null> {
    for (const selector of cachedEntry.product_card_selectors) {
      try {
        const count = await page.locator(selector).count();
        if (count > 0) {
          const canExtract = await this.canExtractFromSelector(page, selector);
          if (canExtract) {
            logger.debug({ selector, count }, 'Found working cached selector');
            return selector;
          }
        }
      } catch (error) {
        logger.debug({ selector, error }, 'Cached selector failed');
      }
    }
    return null;
  }

  /**
   * Build page structure from cached entry
   */
  private buildPageStructureFromCache(
    cachedEntry: SelectorCacheEntry,
    workingCardSelector: string
  ): ListingAnalysisResult {
    return {
      product_card_selector: workingCardSelector,
      product_name_selector: cachedEntry.product_name_selectors[0] || 'a',
      detail_link_selector: cachedEntry.detail_link_selectors[0] || 'a[href]',
      pagination_type: 'none',  // Will be re-analyzed if needed
    };
  }

  /**
   * Analyze page with LLM and save to cache
   */
  private async analyzWithLLMAndCache(
    listingUrl: string,
    selectorCache: ReturnType<typeof getSelectorCache>
  ): Promise<ListingAnalysisResult> {
    const pageStructure = await this.analyzer.analyzeListingPage(
      this.browser,
      this.options.useScreenshot
    );

    // Save to cache for future use
    selectorCache.set(listingUrl, {
      product_card_selectors: [pageStructure.product_card_selector],
      product_name_selectors: [pageStructure.product_name_selector],
      detail_link_selectors: [pageStructure.detail_link_selector],
    });

    return pageStructure;
  }
}

export function createListingCrawler(
  browser: BrowserManager,
  llmClient: LLMClient,
  options?: ListingCrawlerOptions
): ListingCrawler {
  return new ListingCrawler(browser, llmClient, options);
}
