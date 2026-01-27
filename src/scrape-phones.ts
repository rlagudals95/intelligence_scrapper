#!/usr/bin/env node

import 'dotenv/config';
import { Command } from 'commander';
import { PhoneScraperService } from './services/phone-scraper-service.js';
import { ProductResult, Product } from './models/phase3-schemas.js';
import { getLogger } from './utils/logger.js';

const logger = getLogger('scrape-phones');

const program = new Command();

program
  .name('scrape-phones')
  .description('LLM-based intelligent phone scraper')
  .version('0.1.0')
  .requiredOption('-u, --url <url>', 'Listing page URL')
  .option('-m, --models <models>', 'Target models (comma-separated)')
  .option('-s, --site <name>', 'Site name', 'Unknown')
  .option('--headless', 'Run in headless mode', true)
  .option('--no-headless', 'Run with browser visible')
  .option('--no-slack', 'Disable Slack notifications')
  .option('--max <number>', 'Maximum number of products to process', parseInt)
  .parse(process.argv);

const options = program.opts();

async function main() {
  logger.info('Starting phone scraper...');
  logger.info({ options }, 'Options');

  const targetModels = options.models
    ? options.models.split(',').map((m: string) => m.trim())
    : undefined;

  const service = new PhoneScraperService({
    siteName: options.site,
    listingUrl: options.url,
    targetModels,
    headless: options.headless,
    noSlack: options.noSlack || false,
    maxProducts: options.max,
  });

  try {
    const result = await service.run();

    const totalPolicies = result.results.reduce(
      (sum: number, r: ProductResult) =>
        sum + r.products.reduce((s: number, p: Product) => s + p.policies.length, 0),
      0
    );

    console.log('\n' + '='.repeat(70));
    console.log('📱 스크래핑 완료!');
    console.log('='.repeat(70));
    console.log(`사이트: ${result.siteName}`);
    console.log(`URL: ${result.listUrl}`);
    console.log(`제품 수: ${result.results.length}`);
    console.log(`총 정책 수: ${totalPolicies}`);
    console.log(`시간: ${result.scrapedAt}`);
    console.log(`소요시간: ${result.totalDuration.toFixed(2)}초`);
    console.log('='.repeat(70));

    const tokenUsage = service.getTokenUsage();
    console.log('\n📊 토큰 사용량:');
    console.log(`  입력: ${tokenUsage.inputTokens.toLocaleString()}`);
    console.log(`  출력: ${tokenUsage.outputTokens.toLocaleString()}`);
    console.log(`  합계: ${tokenUsage.totalTokens.toLocaleString()}`);

    process.exit(0);
  } catch (error) {
    logger.error({ error }, 'Scraping failed');
    console.error('\n❌ 스크래핑 실패:', error);
    process.exit(1);
  }
}

main();
