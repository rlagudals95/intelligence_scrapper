#!/usr/bin/env node

import 'dotenv/config';
import { Command } from 'commander';
import { PhoneScraperService } from './services/phone-scraper-service.js';
import { ProductResult, Product } from './models/phase3-schemas.js';
import { getLogger } from './utils/logger.js';

const logger = getLogger('scrape-simple');

// Site URL mapping
const SITE_URLS: Record<string, { samsung: string; apple: string }> = {
  하이폰: {
    samsung: 'https://hi-phone.kr/index.php?channel=list&cate=103001000000',
    apple: 'https://hi-phone.kr/index.php?channel=list&cate=103002000000',
  },
  딜리버리폰: {
    samsung: 'https://www.deliveryphone.co.kr/phone/list/2',
    apple: 'https://www.deliveryphone.co.kr/phone/list/3',
  },
  성지폰: {
    samsung: 'https://sungjiphone.com/phone/list/2',
    apple: 'https://sungjiphone.com/phone/list/3',
  },
  폰슐랭: {
    samsung: 'https://phonechelin.shop/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
    apple: 'https://phonechelin.shop/mshop/list?sst=c&cid=APPLE',
  },
  엘지티샵: {
    samsung: 'https://lgtshop.co.kr/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
    apple: 'https://lgtshop.co.kr/mshop/list?sst=c&cid=APPLE',
  },
  투게더몰: {
    samsung: 'https://uplustogethermall.com/section/samsung',
    apple: 'https://uplustogethermall.com/section/apple',
  },
  띵폰: {
    samsung: 'https://ddingphone.com/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
    apple: 'https://ddingphone.com/list?sst=c&cid=APPLE',
  },
};

// Detect phone type from model name
function detectPhoneType(models: string[]): 'samsung' | 'apple' {
  const modelStr = models.join(' ').toLowerCase();

  if (modelStr.includes('아이폰') || modelStr.includes('iphone')) {
    return 'apple';
  }

  return 'samsung';
}

const program = new Command();

program
  .name('scrape-simple')
  .description('Simple interface for phone scraping')
  .version('0.1.0')
  .requiredOption('-s, --site <site>', `Site name (${Object.keys(SITE_URLS).join(', ')})`)
  .requiredOption('-m, --models <models>', 'Target models (comma-separated)')
  .option('--headless', 'Run in headless mode', true)
  .option('--no-headless', 'Run with browser visible')
  .option('--no-slack', 'Disable Slack notifications')
  .parse(process.argv);

const options = program.opts();

async function main() {
  const siteName = options.site;
  const models = options.models.split(',').map((m: string) => m.trim());

  // Validate site
  if (!SITE_URLS[siteName]) {
    console.error(`❌ Unknown site: ${siteName}`);
    console.error(`Available sites: ${Object.keys(SITE_URLS).join(', ')}`);
    process.exit(1);
  }

  // Detect phone type
  const phoneType = detectPhoneType(models);
  const listingUrl = SITE_URLS[siteName][phoneType];

  console.log('\n' + '='.repeat(70));
  console.log('📱 간단 스크래핑 시작');
  console.log('='.repeat(70));
  console.log(`사이트: ${siteName}`);
  console.log(`타입: ${phoneType === 'samsung' ? '삼성' : '애플'}`);
  console.log(`모델: ${models.join(', ')}`);
  console.log(`URL: ${listingUrl}`);
  console.log('='.repeat(70) + '\n');

  logger.info({ siteName, phoneType, models, listingUrl }, 'Starting simple scrape');

  const service = new PhoneScraperService({
    siteName,
    listingUrl,
    targetModels: models,
    headless: options.headless,
    noSlack: options.noSlack || false,
  });

  try {
    const result = await service.run();

    const totalPolicies = result.results.reduce(
      (sum: number, r: ProductResult) =>
        sum + r.products.reduce((s: number, p: Product) => s + p.policies.length, 0),
      0
    );

    console.log('\n' + '='.repeat(70));
    console.log('✅ 스크래핑 완료!');
    console.log('='.repeat(70));
    console.log(`제품 수: ${result.results.length}`);
    console.log(`총 정책 수: ${totalPolicies}`);
    console.log(`소요시간: ${result.total_duration.toFixed(2)}초`);
    console.log('='.repeat(70));

    process.exit(0);
  } catch (error) {
    logger.error({ error }, 'Scraping failed');
    console.error('\n❌ 스크래핑 실패:', error);
    process.exit(1);
  }
}

main();
