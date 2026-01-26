import { BrowserManager } from '../core/browser.js';
import { LLMClient } from '../core/llm-client.js';
import { StateManager } from '../core/state.js';
import { SiteConfig, defaultConfigValues } from '../core/config.js';
import { ListingCrawler } from '../crawlers/listing.js';
import { DetailPageAnalyzer } from '../utils/detail-page-analyzer.js';
import { SlackNotifier } from '../utils/slack-notifier.js';
import { PhoneListingItem } from '../models/schemas.js';
import { Phase3ScrapingResult, Phase3Product } from '../models/phase3-schemas.js';
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
   * Run the complete scraping pipeline
   */
  async run(): Promise<Phase3ScrapingResult> {
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

      // Phase 2: Analyze each detail page
      logger.info('Phase 2: Analyzing detail pages...');
      const allProducts: Phase3Product[] = [];
      const csvPaths: string[] = [];

      for (let i = 0; i < products.length; i++) {
        const product = products[i];
        logger.info({ index: i + 1, total: products.length, name: product.modelName }, 'Processing product');

        // Skip if already visited
        if (this.stateManager.isUrlVisited(product.detailUrl)) {
          logger.info({ url: product.detailUrl }, 'Skipping visited URL');
          continue;
        }

        try {
          // Navigate to detail page
          await this.browser.goto(product.detailUrl);
          await randomDelay(1, 2);

          // Analyze detail page
          const result = await this.detailAnalyzer.analyzeDetailPage(
            this.browser.getPage(),
            product.detailUrl,
            this.options.siteName
          );

          // Add products
          allProducts.push(...result.products);

          // Mark as visited
          this.stateManager.markUrlVisited(product.detailUrl);

          // Save CSV for each product
          for (const p of result.products) {
            if (p.policies.length > 0) {
              const csvPath = this.slackNotifier.savePoliciesToCsv(
                p.policies,
                this.options.siteName,
                p.name
              );
              csvPaths.push(csvPath);
            }
          }

          // Save state periodically
          if ((i + 1) % this.config.checkpointInterval === 0) {
            this.stateManager.save();
          }
        } catch (error) {
          logger.error({ url: product.detailUrl, error }, 'Failed to analyze detail page');
        }
      }

      // Create final result
      const finalResult: Phase3ScrapingResult = {
        products: allProducts,
        capturedAt: new Date().toISOString(),
        source: {
          siteName: this.options.siteName,
          url: this.options.listingUrl,
        },
      };

      // Save JSON result
      this.slackNotifier.saveResultToJson(finalResult, this.options.siteName);

      // Save final state
      this.stateManager.save();

      // Send Slack notification
      if (!this.options.noSlack) {
        await this.slackNotifier.notifyScrapingComplete(finalResult, csvPaths);
      }

      logger.info(
        {
          products: allProducts.length,
          policies: allProducts.reduce((sum, p) => sum + p.policies.length, 0),
          csvFiles: csvPaths.length,
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
