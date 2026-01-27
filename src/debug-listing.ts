#!/usr/bin/env node

/**
 * Debug script to analyze listing page extraction issues
 */

import 'dotenv/config';
import { chromium } from 'playwright';
import { LLMClient } from './core/llm-client.js';
import {
  LISTING_PAGE_ANALYSIS_SYSTEM,
  formatListingAnalysisPrompt,
} from './utils/prompts.js';

const SITES = {
  하이폰: 'https://hi-phone.kr/index.php?channel=list&cate=103001000000',
  딜리버리폰: 'https://www.deliveryphone.co.kr/phone/list/2',
  성지폰: 'https://sungjiphone.com/phone/list/2',
};

async function debugSite(siteName: string, url: string) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`🔍 Debugging: ${siteName}`);
  console.log(`URL: ${url}`);
  console.log('='.repeat(70));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    locale: 'ko-KR',
  });
  const page = await context.newPage();

  try {
    // Navigate to page
    console.log('\n1. 페이지 로드 중...');
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    console.log('   ✅ 페이지 로드 완료');

    // Get simplified HTML
    console.log('\n2. HTML 간소화 중...');
    const simplifiedHtml = await page.evaluate(() => {
      const clone = document.body.cloneNode(true) as HTMLElement;
      ['script', 'style', 'noscript', 'iframe', 'svg', 'path'].forEach((tag) => {
        clone.querySelectorAll(tag).forEach((el) => el.remove());
      });
      ['style', 'onclick', 'onload', 'onerror'].forEach((attr) => {
        clone.querySelectorAll('*').forEach((el) => el.removeAttribute(attr));
      });
      return clone.innerHTML.replace(/\s+/g, ' ').replace(/>\s+</g, '><').trim();
    });
    console.log(`   ✅ HTML 길이: ${simplifiedHtml.length} chars`);

    // Get screenshot
    console.log('\n3. 스크린샷 촬영 중...');
    const screenshot = await page.screenshot({ type: 'png' });
    const screenshotBase64 = screenshot.toString('base64');
    console.log('   ✅ 스크린샷 완료');

    // Call LLM for analysis
    console.log('\n4. LLM 분석 중...');
    const llmClient = new LLMClient();
    const prompt = formatListingAnalysisPrompt(simplifiedHtml);

    const response = await llmClient.completeWithVision(
      LISTING_PAGE_ANALYSIS_SYSTEM,
      prompt,
      screenshotBase64
    );

    // Parse JSON from response
    let jsonStr = response.content.trim();
    const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1].trim();
    }
    const jsonObjMatch = jsonStr.match(/(\{[\s\S]*\})/);
    if (jsonObjMatch) {
      jsonStr = jsonObjMatch[1];
    }

    const selectors = JSON.parse(jsonStr);
    console.log('   ✅ LLM 분석 완료');
    console.log('\n📋 LLM이 반환한 셀렉터:');
    console.log(JSON.stringify(selectors, null, 2));

    // Test selectors
    console.log('\n5. 셀렉터 테스트 중...');

    const testSelector = async (name: string, selector: string | null | undefined) => {
      if (!selector) {
        console.log(`   ⚪ ${name}: (없음)`);
        return 0;
      }
      try {
        const count = await page.locator(selector).count();
        const status = count > 0 ? '✅' : '❌';
        console.log(`   ${status} ${name}: "${selector}" → ${count}개`);
        return count;
      } catch (e) {
        console.log(`   ❌ ${name}: "${selector}" → 에러: ${e}`);
        return 0;
      }
    };

    const cardCount = await testSelector('product_card', selectors.product_card_selector);
    await testSelector('product_name', selectors.product_name_selector);
    await testSelector('detail_link', selectors.detail_link_selector);
    await testSelector('retail_price', selectors.retail_price_selector);
    await testSelector('discount_price', selectors.discount_price_selector);

    // Try to extract first card's data
    if (cardCount > 0) {
      console.log('\n6. 첫 번째 카드 데이터 추출 테스트...');

      const cardSelector = selectors.product_card_selector;
      const nameSelector = selectors.product_name_selector;
      const linkSelector = selectors.detail_link_selector;

      const firstCard = await page.evaluate(
        ([cardSel, nameSel, linkSel]) => {
          const card = document.querySelector(cardSel);
          if (!card) return { error: 'card not found' };

          // Try to find name element
          const nameEl = card.querySelector(nameSel);
          const modelName = nameEl?.textContent?.trim() || null;

          // Try to find link element
          const linkEl = card.querySelector(linkSel) as HTMLAnchorElement | null;
          let detailUrl = null;
          if (linkEl) {
            detailUrl = linkEl.href || linkEl.getAttribute('href') || null;
            if (detailUrl && detailUrl.startsWith('/')) {
              detailUrl = window.location.origin + detailUrl;
            }
          }

          return {
            modelName,
            detailUrl,
            cardHtml: card.innerHTML.slice(0, 800),
            nameFound: !!nameEl,
            linkFound: !!linkEl,
          };
        },
        [cardSelector, nameSelector, linkSelector]
      );

      console.log(`   모델명 요소 찾음: ${firstCard.nameFound ? '✅' : '❌'}`);
      console.log(`   링크 요소 찾음: ${firstCard.linkFound ? '✅' : '❌'}`);
      console.log(`   모델명: ${firstCard.modelName || '❌ 없음'}`);
      console.log(`   URL: ${firstCard.detailUrl || '❌ 없음'}`);
      console.log(`\n   카드 HTML:\n${firstCard.cardHtml}`);
    }

    // Show sample of actual HTML structure
    console.log('\n7. 실제 HTML 구조 샘플 (첫 번째 상품 영역):');
    const sampleHtml = await page.evaluate(() => {
      // Common product card patterns
      const selectors = [
        '.goodsItemBox',
        '.product-item',
        '.phone-item',
        'li.default',
        '.item-box',
        '[class*="product"]',
        '[class*="goods"]',
        '[class*="item"]',
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          return {
            selector: sel,
            html: el.outerHTML.slice(0, 1500),
          };
        }
      }

      // If none found, get first list item
      const listItem = document.querySelector('ul li, ol li');
      if (listItem) {
        return {
          selector: 'ul li / ol li',
          html: listItem.outerHTML.slice(0, 1500),
        };
      }

      return null;
    });

    if (sampleHtml) {
      console.log(`   찾은 셀렉터: ${sampleHtml.selector}`);
      console.log(`   HTML:\n${sampleHtml.html}`);
    }
  } catch (error) {
    console.error('❌ 에러:', error);
  } finally {
    await browser.close();
  }
}

async function main() {
  const siteName = process.argv[2] || '하이폰';

  if (siteName === 'all') {
    for (const [name, url] of Object.entries(SITES)) {
      await debugSite(name, url);
    }
  } else if (SITES[siteName as keyof typeof SITES]) {
    await debugSite(siteName, SITES[siteName as keyof typeof SITES]);
  } else {
    console.log(`사용법: npx tsx src/debug-listing.ts [사이트명]`);
    console.log(`사이트: ${Object.keys(SITES).join(', ')}, all`);
  }
}

main().catch(console.error);
