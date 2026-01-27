#!/usr/bin/env node

import 'dotenv/config';
import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { PhoneScraperService } from './services/phone-scraper-service.js';
import { ScrapingResult } from './models/phase3-schemas.js';
import { getLogger } from './utils/logger.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

const logger = getLogger('test-sites');

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

interface SiteResult {
  siteName: string;
  phoneType: 'samsung' | 'apple';
  success: boolean;
  result?: ScrapingResult;
  error?: string;
  duration: number;
}

interface TestSummary {
  timestamp: string;
  models: string[];
  phoneType: 'samsung' | 'apple';
  totalSites: number;
  successCount: number;
  failCount: number;
  totalProducts: number;
  totalPolicies: number;
  totalDuration: number;
  sites: Array<{
    name: string;
    success: boolean;
    products: number;
    policies: number;
    duration: number;
    error?: string;
  }>;
}

function detectPhoneType(models: string[]): 'samsung' | 'apple' {
  const modelStr = models.join(' ').toLowerCase();
  if (modelStr.includes('아이폰') || modelStr.includes('iphone')) {
    return 'apple';
  }
  return 'samsung';
}

function getTimestamp(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const h = String(now.getHours()).padStart(2, '0');
  const min = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  return `${y}-${m}-${d}_${h}${min}${s}`;
}

const program = new Command();

program
  .name('test-sites')
  .description('Test scraping across multiple sites')
  .version('0.1.0')
  .option('-m, --models <models>', 'Target models (comma-separated)', '갤럭시 S25')
  .option('-a, --all', 'Scrape all models without filtering (ignores --models)')
  .option('-s, --sites <sites>', 'Specific sites to test (comma-separated, default: all)')
  .option('--headless', 'Run in headless mode', true)
  .option('--no-headless', 'Run with browser visible')
  .option('--samsung-only', 'Only test Samsung phones')
  .option('--apple-only', 'Only test Apple phones')
  .option('-f, --force', 'Force re-scrape by clearing visited URLs state')
  .parse(process.argv);

const options = program.opts();

async function scrapeSite(
  siteName: string,
  listingUrl: string,
  models: string[] | undefined,
  phoneType: 'samsung' | 'apple',
  headless: boolean
): Promise<SiteResult> {
  const startTime = Date.now();

  console.log(`\n${'─'.repeat(50)}`);
  console.log(`🔍 ${siteName} (${phoneType === 'samsung' ? '삼성' : '애플'})`);
  console.log(`${'─'.repeat(50)}`);

  try {
    const service = new PhoneScraperService({
      siteName,
      listingUrl,
      targetModels: models,
      headless,
      noSlack: true, // Don't send Slack notifications during test
    });

    const result = await service.run();
    const duration = (Date.now() - startTime) / 1000;

    const productCount = result.results.length;
    const policyCount = result.results.reduce(
      (sum, r) => sum + r.products.reduce((s, p) => s + p.policies.length, 0),
      0
    );

    console.log(`✅ 성공: 제품 ${productCount}개, 정책 ${policyCount}개 (${duration.toFixed(1)}초)`);

    return {
      siteName,
      phoneType,
      success: true,
      result,
      duration,
    };
  } catch (error) {
    const duration = (Date.now() - startTime) / 1000;
    const errorMsg = error instanceof Error ? error.message : String(error);

    console.log(`❌ 실패: ${errorMsg} (${duration.toFixed(1)}초)`);

    return {
      siteName,
      phoneType,
      success: false,
      error: errorMsg,
      duration,
    };
  }
}

async function main() {
  // --all 옵션이 있으면 모델 필터링 비활성화
  const models: string[] | undefined = options.all
    ? undefined
    : options.models.split(',').map((m: string) => m.trim());

  // 폰 타입 결정: --all 모드에서는 --samsung-only나 --apple-only로 지정, 기본값 samsung
  let phoneType: 'samsung' | 'apple';
  if (options.appleOnly) {
    phoneType = 'apple';
  } else if (options.samsungOnly || options.all) {
    phoneType = 'samsung';
  } else {
    phoneType = detectPhoneType(models || []);
  }

  // Force mode: clear visited URLs state
  if (options.force) {
    const statePath = path.join(projectRoot, 'checkpoints', 'state.json');
    if (fs.existsSync(statePath)) {
      fs.unlinkSync(statePath);
      console.log('🔄 State cleared (--force mode)');
    }
  }

  // Determine which sites to test
  let sitesToTest = Object.keys(SITE_URLS);
  if (options.sites) {
    sitesToTest = options.sites.split(',').map((s: string) => s.trim());
    // Validate sites
    for (const site of sitesToTest) {
      if (!SITE_URLS[site]) {
        console.error(`❌ Unknown site: ${site}`);
        console.error(`Available sites: ${Object.keys(SITE_URLS).join(', ')}`);
        process.exit(1);
      }
    }
  }

  const timestamp = getTimestamp();
  const outputDir = path.join(projectRoot, 'output', 'test-results', timestamp);
  fs.mkdirSync(outputDir, { recursive: true });

  console.log('\n' + '═'.repeat(60));
  console.log('🧪 멀티 사이트 테스트 시작');
  console.log('═'.repeat(60));
  console.log(`모델: ${models ? models.join(', ') : '전체 (필터링 없음)'}`);
  console.log(`타입: ${phoneType === 'samsung' ? '삼성' : '애플'}`);
  console.log(`사이트: ${sitesToTest.join(', ')}`);
  console.log(`출력 폴더: ${outputDir}`);
  console.log('═'.repeat(60));

  const results: SiteResult[] = [];

  for (const siteName of sitesToTest) {
    const listingUrl = SITE_URLS[siteName][phoneType];
    const result = await scrapeSite(siteName, listingUrl, models, phoneType, options.headless);
    results.push(result);

    // Save individual result
    if (result.result) {
      const fileName = `${siteName}_${phoneType}.json`;
      const filePath = path.join(outputDir, fileName);
      fs.writeFileSync(filePath, JSON.stringify(result.result, null, 2), 'utf8');
    }
  }

  // Calculate summary
  const successResults = results.filter((r) => r.success);
  const totalProducts = successResults.reduce(
    (sum, r) => sum + (r.result?.results.length || 0),
    0
  );
  const totalPolicies = successResults.reduce(
    (sum, r) =>
      sum +
      (r.result?.results.reduce(
        (s, res) => s + res.products.reduce((ps, p) => ps + p.policies.length, 0),
        0
      ) || 0),
    0
  );
  const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);

  const summary: TestSummary = {
    timestamp,
    models: models || ['전체'],
    phoneType,
    totalSites: results.length,
    successCount: successResults.length,
    failCount: results.length - successResults.length,
    totalProducts,
    totalPolicies,
    totalDuration,
    sites: results.map((r) => ({
      name: r.siteName,
      success: r.success,
      products: r.result?.results.length || 0,
      policies:
        r.result?.results.reduce(
          (s, res) => s + res.products.reduce((ps, p) => ps + p.policies.length, 0),
          0
        ) || 0,
      duration: r.duration,
      error: r.error,
    })),
  };

  // Save summary
  const summaryPath = path.join(outputDir, 'summary.json');
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf8');

  // Print summary
  console.log('\n' + '═'.repeat(60));
  console.log('📊 테스트 결과 요약');
  console.log('═'.repeat(60));
  console.log(`성공: ${summary.successCount}/${summary.totalSites} 사이트`);
  console.log(`총 제품: ${summary.totalProducts}개`);
  console.log(`총 정책: ${summary.totalPolicies}개`);
  console.log(`총 소요시간: ${summary.totalDuration.toFixed(1)}초`);
  console.log('─'.repeat(60));

  for (const site of summary.sites) {
    const status = site.success ? '✅' : '❌';
    const info = site.success
      ? `제품 ${site.products}개, 정책 ${site.policies}개`
      : site.error;
    console.log(`${status} ${site.name}: ${info} (${site.duration.toFixed(1)}초)`);
  }

  console.log('═'.repeat(60));
  console.log(`📁 결과 저장: ${outputDir}`);
  console.log('═'.repeat(60) + '\n');

  process.exit(summary.failCount > 0 ? 1 : 0);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
