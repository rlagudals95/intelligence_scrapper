import { BrowserManager } from '../core/browser.js';
import { LLMClient } from '../core/llm-client.js';
import { StateManager } from '../core/state.js';
import { SiteConfig, defaultConfigValues } from '../core/config.js';
import { ListingCrawler } from '../crawlers/listing.js';
import { DetailPageAnalyzer } from '../utils/detail-page-analyzer.js';
import { SlackNotifier } from '../utils/slack-notifier.js';
import { PhoneListingItem } from '../models/schemas.js';
import { ScrapingResult, ProductResult, Product } from '../models/phase3-schemas.js';
import { getLogger } from '../utils/logger.js';
import { randomDelay } from '../utils/delay.js';

const logger = getLogger('PhoneScraperService');

export interface ScraperOptions {
  siteName: string;
  listingUrl: string;
  targetModels?: string[];
  headless?: boolean;
  noSlack?: boolean;
  maxProducts?: number;
  parallelCount?: number;  // 병렬 처리 개수 (기본: 3)
}

export class PhoneScraperService {
  private browser: BrowserManager;
  private llmClient: LLMClient;
  private stateManager: StateManager;
  private listingCrawler: ListingCrawler;
  private detailAnalyzer: DetailPageAnalyzer;
  private slackNotifier: SlackNotifier;
  private config: SiteConfig;
  private options: ScraperOptions;

  constructor(options: ScraperOptions) {
    this.options = options;

    this.config = {
      ...defaultConfigValues,
      targetUrl: options.listingUrl,
      listingUrl: options.listingUrl,
      headless: options.headless ?? true,
    };

    this.browser = new BrowserManager(this.config);
    this.llmClient = new LLMClient();
    this.stateManager = new StateManager();
    this.listingCrawler = new ListingCrawler(this.browser, this.llmClient);
    this.detailAnalyzer = new DetailPageAnalyzer(this.llmClient);
    this.slackNotifier = new SlackNotifier();
  }

  /**
   * Run the complete scraping pipeline (Python 호환 출력)
   */
  async run(): Promise<ScrapingResult> {
    const startTime = Date.now();
    logger.info({ siteName: this.options.siteName, url: this.options.listingUrl }, 'Starting scrape');

    try {
      // Start browser
      await this.browser.start();

      // Load previous state
      this.stateManager.load();

      // Phase 1: Discover products from listing page
      logger.info('Phase 1: Discovering products from listing page...');
      let products = await this.listingCrawler.crawl(this.options.listingUrl);
      logger.info({ count: products.length }, 'Products discovered');

      // Filter by target models if specified
      if (this.options.targetModels && this.options.targetModels.length > 0) {
        products = this.filterByModels(products, this.options.targetModels);
        logger.info({ count: products.length, models: this.options.targetModels }, 'Filtered by models');
      }

      // Limit products if specified
      if (this.options.maxProducts && products.length > this.options.maxProducts) {
        products = products.slice(0, this.options.maxProducts);
        logger.info({ count: products.length }, 'Limited products');
      }

      // Phase 2: Analyze detail pages (병렬 처리)
      const parallelCount = this.options.parallelCount ?? 3;
      logger.info({ parallelCount }, 'Phase 2: Analyzing detail pages with parallel processing...');
      const allResults: ProductResult[] = [];
      const csvPaths: string[] = [];

      // Filter out already visited URLs
      const pendingProducts = products.filter(p => !this.stateManager.isUrlVisited(p.detailUrl));
      logger.info({ pending: pendingProducts.length, skipped: products.length - pendingProducts.length }, 'Filtered pending products');

      // Process in parallel batches
      for (let batchStart = 0; batchStart < pendingProducts.length; batchStart += parallelCount) {
        const batch = pendingProducts.slice(batchStart, batchStart + parallelCount);
        logger.info({
          batch: Math.floor(batchStart / parallelCount) + 1,
          totalBatches: Math.ceil(pendingProducts.length / parallelCount),
          products: batch.map(p => p.modelName)
        }, 'Processing batch');

        // Create extra pages for parallel processing (reuse main page for first item)
        const extraPages = batch.length > 1 ? await this.browser.createExtraPages(batch.length - 1) : [];
        const pages = [this.browser.getPage(), ...extraPages];

        try {
          // Navigate all pages in parallel
          await Promise.all(batch.map(async (product, idx) => {
            const page = pages[idx];
            if (idx === 0) {
              await this.browser.goto(product.detailUrl);
            } else {
              await this.browser.gotoWithPage(page, product.detailUrl);
            }
          }));

          await randomDelay(1, 2);

          // Analyze all pages in parallel
          const batchResults = await Promise.all(batch.map(async (product, idx) => {
            const page = pages[idx];
            try {
              const result = await this.detailAnalyzer.analyzeDetailPage(
                page,
                product.detailUrl,
                this.options.siteName
              );
              return { success: true, product, result };
            } catch (error) {
              logger.error({ url: product.detailUrl, error }, 'Failed to analyze detail page');
              return { success: false, product, error };
            }
          }));

          // Process results
          for (const batchResult of batchResults) {
            if (batchResult.success && batchResult.result) {
              allResults.push(batchResult.result);
              this.stateManager.markUrlVisited(batchResult.product.detailUrl);

              // Save CSV for each product
              for (const p of batchResult.result.products) {
                if (p.policies.length > 0) {
                  const csvPath = this.slackNotifier.savePoliciesToCsv(
                    p.policies,
                    this.options.siteName,
                    p.sku_code
                  );
                  csvPaths.push(csvPath);
                }
              }
            }
          }

          // Save state after each batch
          this.stateManager.save();
        } finally {
          // Clean up extra pages
          await this.browser.closeExtraPages();
        }
      }

      const totalDuration = (Date.now() - startTime) / 1000;

      // Create final result (Python 호환 형식)
      const finalResult: ScrapingResult = {
        site_name: this.options.siteName,
        list_url: this.options.listingUrl,
        target_models: this.options.targetModels || [],
        scraped_at: new Date().toISOString(),
        total_duration: totalDuration,
        results: allResults,
      };

      // Save JSON result
      this.slackNotifier.saveResultToJson(finalResult, this.options.siteName);

      // Save final state
      this.stateManager.save();

      // Send Slack notification
      if (!this.options.noSlack) {
        await this.slackNotifier.notifyScrapingComplete(finalResult, csvPaths);
      }

      const totalPolicies = allResults.reduce(
        (sum: number, r: ProductResult) =>
          sum + r.products.reduce((s: number, p: Product) => s + p.policies.length, 0),
        0
      );

      logger.info(
        {
          products: allResults.length,
          policies: totalPolicies,
          csvFiles: csvPaths.length,
          duration: totalDuration,
        },
        'Scraping complete'
      );

      return finalResult;
    } catch (error) {
      logger.error({ error }, 'Scraping failed');

      if (!this.options.noSlack) {
        await this.slackNotifier.notifyError(this.options.siteName, String(error));
      }

      throw error;
    } finally {
      await this.browser.close();
    }
  }

  /**
   * Filter products by model names
   */
  private filterByModels(products: PhoneListingItem[], targetModels: string[]): PhoneListingItem[] {
    const normalizedTargets = targetModels.map((m) =>
      m.toLowerCase().replace(/\s+/g, '')
    );

    return products.filter((product) => {
      const normalizedName = product.modelName.toLowerCase().replace(/\s+/g, '');
      return normalizedTargets.some(
        (target) => normalizedName.includes(target) || target.includes(normalizedName)
      );
    });
  }

  /**
   * Get token usage stats
   */
  getTokenUsage(): { inputTokens: number; outputTokens: number; totalTokens: number } {
    return this.llmClient.getTokenUsage();
  }

  /**
   * Get state stats
   */
  getStateStats(): { urlCount: number; stateCount: number } {
    return this.stateManager.getStats();
  }
}

export function createPhoneScraperService(options: ScraperOptions): PhoneScraperService {
  return new PhoneScraperService(options);
}
