import { BrowserManager } from '../core/browser.js';
import { LLMClient } from '../core/llm-client.js';
import { ListPageAnalyzer, ListingAnalysisResult } from '../utils/list-page-analyzer.js';
import { PhoneListingItem, PhoneListingItemSchema } from '../models/schemas.js';
import { getLogger } from '../utils/logger.js';
import { randomDelay } from '../utils/delay.js';

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

  /**
   * Crawl listing page and extract all product items
   */
  async crawl(listingUrl: string): Promise<PhoneListingItem[]> {
    logger.info({ url: listingUrl }, 'Starting listing page crawl');

    // Navigate to listing page
    await this.browser.goto(listingUrl);
    await randomDelay(1, 2);

    // Analyze page structure with LLM
    const pageStructure = await this.analyzer.analyzeListingPage(
      this.browser,
      this.options.useScreenshot
    );

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
            // Extract model name (required)
            const nameEl = card.querySelector(selectors.productNameSelector);
            const modelName = nameEl?.textContent?.trim();
            if (!modelName) return;

            // Extract detail URL (required)
            const linkEl = card.querySelector(selectors.detailLinkSelector) as HTMLAnchorElement;
            let detailUrl = linkEl?.href || '';
            if (!detailUrl && linkEl) {
              detailUrl = linkEl.getAttribute('href') || '';
            }
            if (!detailUrl) return;

            // Make URL absolute if relative
            if (detailUrl.startsWith('/')) {
              detailUrl = window.location.origin + detailUrl;
            }

            // Extract optional fields
            const getOptionalText = (selector: string | null | undefined): string | undefined => {
              if (!selector) return undefined;
              const el = card.querySelector(selector);
              return el?.textContent?.trim() || undefined;
            };

            const getOptionalImage = (selector: string | null | undefined): string | undefined => {
              if (!selector) return undefined;
              const imgEl = card.querySelector(selector) as HTMLImageElement;
              return imgEl?.src || undefined;
            };

            results.push({
              modelName,
              signupType: getOptionalText(selectors.signupTypeSelector),
              retailPrice: getOptionalText(selectors.retailPriceSelector),
              discountPrice: getOptionalText(selectors.discountPriceSelector),
              planName: getOptionalText(selectors.planNameSelector),
              detailUrl,
              imageUrl: getOptionalImage(selectors.imageSelector),
              subsidy: getOptionalText(selectors.publicSubsidySelector),
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
}

export function createListingCrawler(
  browser: BrowserManager,
  llmClient: LLMClient,
  options?: ListingCrawlerOptions
): ListingCrawler {
  return new ListingCrawler(browser, llmClient, options);
}
