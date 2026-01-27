import { Page } from 'playwright';
import { LLMClient } from '../core/llm-client.js';
import { getLogger } from './logger.js';
import {
  ScrapingResult,
  ProductResult,
  Product,
  Policy,
  JoinTypeEnum,
  DiscountTypeEnum,
  parseStorage,
  parsePrice,
  carrierToCode,
  generateProductId,
  generatePolicyId,
} from '../models/phase3-schemas.js';
import {
  SCREEN_PAGE_STRUCTURE_SYSTEM,
  formatScreenPageStructurePrompt,
  SCREEN_EXTRACT_PRICING_SYSTEM,
  formatScreenExtractPricingPrompt,
} from './prompts.js';
import { fixedDelay } from './delay.js';

const logger = getLogger('DetailPageAnalyzer');

interface OptionUIInfo {
  selector: string;
  type: 'button' | 'tab' | 'radio' | 'select';
  click_method?: string;
  value_attribute?: string;
}

interface PlanUIInfo {
  open_button_selector?: string;
  list_container_selector?: string;
  item_selector?: string;
  name_selector?: string;
  price_attribute?: string;
}

interface PageStructure {
  options: {
    storage?: OptionUIInfo;
    carrier?: OptionUIInfo;
    join_type?: OptionUIInfo;
    plan?: PlanUIInfo;
  };
  pricing: {
    retail_price_selector?: string;
    public_subsidy_selector?: string;
    additional_subsidy_selector?: string;
    installment_principal_selector?: string;
    monthly_payment_selector?: string;
  };
}

interface OptionValues {
  storage?: string[];
  carrier?: string[];
  join_type?: string[];
  plan?: Array<{ name: string; price: string }>;
}

interface Combination {
  storage?: string;
  carrier?: string;
  join_type?: string;
  plan?: string;
  plan_price?: string;
}

interface ExtractedPricing {
  retail_price?: number | null;
  public_subsidy?: number | null;
  additional_subsidy?: number | null;
  installment_principal?: number | null;
  monthly_payment?: number | null;
  final_price?: number | null;
  plan_name?: string | null;
  plan_monthly_fee?: number | null;
}

interface PolicyResultInternal {
  success: boolean;
  combo: Combination;
  pricing?: ExtractedPricing;
  error?: string;
}

export class DetailPageAnalyzer {
  private llm: LLMClient;

  // Step 2 캐싱: 사이트별 PageStructure 저장
  private structureCache: Map<string, PageStructure> = new Map();

  constructor(llmClient: LLMClient) {
    this.llm = llmClient;
    logger.info('DetailPageAnalyzer initialized');
  }

  /**
   * 사이트 도메인에서 캐시 키 추출
   */
  private getSiteCacheKey(url: string): string {
    try {
      const parsed = new URL(url);
      return parsed.hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  }

  /**
   * 캐시 초기화 (새 스크래핑 세션 시작 시)
   */
  clearCache(): void {
    this.structureCache.clear();
    logger.info('Structure cache cleared');
  }

  /**
   * Analyze detail page and extract all policies (Python 호환 출력)
   */
  async analyzeDetailPage(
    page: Page,
    url: string,
    siteName: string = 'Unknown'
  ): Promise<ProductResult> {
    const startTime = Date.now();
    logger.info({ url, siteName }, 'Starting detail page analysis');

    // Step 1: Extract basic info
    const basicInfo = await this.step1ExtractBasicInfo(page, url);
    logger.info({ productName: basicInfo.product_name }, 'Step 1 complete: Basic info extracted');

    // Step 2: Analyze option UI and extract selectors (캐싱 적용)
    const step2Result = await this.step2AnalyzeOptionUI(page, url);
    logger.info(
      { optionTypes: Object.keys(step2Result.options) },
      'Step 2 complete: Option UI analyzed'
    );

    // Step 3: Option values validation (already extracted in step 2)
    const optionValues = step2Result.options;

    // Step 4: Generate combinations
    const combinations = this.step4GenerateCombinations(optionValues, step2Result.structure);
    logger.info({ count: combinations.length }, 'Step 4 complete: Combinations generated');

    // Step 5: Extract policies for each combination
    const policyResults = await this.step5ExtractPolicies(
      page,
      combinations,
      basicInfo,
      step2Result.structure
    );
    logger.info(
      {
        success: policyResults.filter((r: PolicyResultInternal) => r.success).length,
        failed: policyResults.filter((r: PolicyResultInternal) => !r.success).length,
      },
      'Step 5 complete: Policies extracted'
    );

    // Step 6: Convert to schema (Python 호환)
    const products = this.step6ConvertToSchema(policyResults, siteName, basicInfo);
    const duration = (Date.now() - startTime) / 1000;
    const policyCount = products.reduce((sum: number, p: Product) => sum + p.policies.length, 0);

    logger.info(
      { products: products.length, policies: policyCount, duration },
      'Step 6 complete: Converted to schema'
    );

    return {
      product_name: basicInfo.product_name,
      url,
      policy_count: policyCount,
      duration,
      products,
    };
  }

  /**
   * Step 1: Extract basic page info
   */
  private async step1ExtractBasicInfo(
    page: Page,
    url: string
  ): Promise<{ product_name: string; current_url: string; page_title: string }> {
    try {
      const title = await page.title();
      const currentUrl = page.url();

      return {
        product_name: title.trim(),
        current_url: currentUrl,
        page_title: title,
      };
    } catch (error) {
      logger.error({ error }, 'Step 1 failed');
      return {
        product_name: 'Unknown',
        current_url: url,
        page_title: '',
      };
    }
  }

  /**
   * Step 2: Analyze option UI using LLM (캐싱 적용)
   */
  private async step2AnalyzeOptionUI(
    page: Page,
    url: string
  ): Promise<{ structure: PageStructure; options: OptionValues }> {
    try {
      const cacheKey = this.getSiteCacheKey(url);
      let structure: PageStructure;

      // 캐시에서 구조 확인
      const cachedStructure = this.structureCache.get(cacheKey);
      if (cachedStructure) {
        logger.info({ cacheKey }, 'Using cached page structure (Step 2 캐시 히트)');
        structure = cachedStructure;
      } else {
        // 캐시 미스: LLM으로 분석
        logger.info({ cacheKey }, 'Cache miss - analyzing page structure with LLM');
        const html = await page.content();
        const cleanedHtml = this.cleanHtml(html);
        structure = await this.step2aExtractSelectors(cleanedHtml);

        // 캐시에 저장
        this.structureCache.set(cacheKey, structure);
        logger.info({ cacheKey }, 'Page structure cached');
      }

      // Step 2B: Extract option values using selectors (항상 실행 - 옵션 값은 제품마다 다름)
      const options = await this.step2bExtractOptionValues(page, structure);

      return { structure, options };
    } catch (error) {
      logger.error({ error }, 'Step 2 failed');
      return {
        structure: { options: {}, pricing: {} },
        options: {},
      };
    }
  }

  /**
   * Clean HTML by removing scripts, styles, etc.
   */
  private cleanHtml(html: string): string {
    let cleaned = html;

    // Remove scripts
    cleaned = cleaned.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
    // Remove styles
    cleaned = cleaned.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
    // Remove comments
    cleaned = cleaned.replace(/<!--[\s\S]*?-->/g, '');
    // Remove header, footer, nav
    cleaned = cleaned.replace(/<header[^>]*>[\s\S]*?<\/header>/gi, '');
    cleaned = cleaned.replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, '');
    cleaned = cleaned.replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '');
    // Normalize whitespace
    cleaned = cleaned.replace(/\s+/g, ' ');

    // Extract body content
    const bodyMatch = cleaned.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch) {
      cleaned = bodyMatch[1];
    }

    // Limit size
    return cleaned.slice(0, 100000);
  }

  /**
   * Step 2A: Extract CSS selectors using LLM
   */
  private async step2aExtractSelectors(html: string): Promise<PageStructure> {
    const prompt = formatScreenPageStructurePrompt(html);

    const response = await this.llm.complete(SCREEN_PAGE_STRUCTURE_SYSTEM, prompt);

    const parsed = this.parseJsonResponse(response.content);
    return parsed as PageStructure;
  }

  /**
   * Step 2B: Extract actual option values using selectors
   */
  private async step2bExtractOptionValues(
    page: Page,
    structure: PageStructure
  ): Promise<OptionValues> {
    const options: OptionValues = {};

    // 먼저 숨겨진 드롭다운/팝업 펼치기
    await this.expandAllDropdowns(page);
    await fixedDelay(0.5);

    // Extract storage values
    if (structure.options.storage?.selector) {
      const values = await this.extractValuesWithSelector(
        page,
        structure.options.storage.selector,
        structure.options.storage.value_attribute
      );
      if (values.length > 0) {
        options.storage = values;
      }
    }

    // Extract carrier values
    if (structure.options.carrier?.selector) {
      const values = await this.extractValuesWithSelector(
        page,
        structure.options.carrier.selector,
        structure.options.carrier.value_attribute
      );
      if (values.length > 0) {
        options.carrier = values;
      }
    }

    // Extract join_type values
    if (structure.options.join_type?.selector) {
      const values = await this.extractValuesWithSelector(
        page,
        structure.options.join_type.selector,
        structure.options.join_type.value_attribute
      );
      if (values.length > 0) {
        options.join_type = values;
      }
    }

    // Extract plans - always try, even without open_button_selector
    // 요금제는 매우 중요한 정보이므로 항상 추출 시도
    const planInfo = structure.options.plan || {};
    const plans = await this.extractPlansWithLLM(page, planInfo);
    if (plans.length > 0) {
      options.plan = plans;
      logger.info({ planCount: plans.length }, 'Plans extracted successfully');
    } else {
      // Fallback: 현재 페이지에서 직접 요금제 추출 시도
      logger.info('No plans found with planInfo, trying direct extraction');
      const fallbackPlans = await this.extractPlansDirectlyFromPage(page);
      if (fallbackPlans.length > 0) {
        options.plan = fallbackPlans;
        logger.info({ planCount: fallbackPlans.length }, 'Plans extracted via fallback');
      } else {
        logger.warn('Failed to extract plans - policies will have Unknown plan');
      }
    }

    return options;
  }

  /**
   * Extract values from elements using selector
   */
  private async extractValuesWithSelector(
    page: Page,
    selector: string,
    valueAttribute?: string
  ): Promise<string[]> {
    try {
      const values = await page.evaluate(
        ({ sel, attr }) => {
          const elements = document.querySelectorAll(sel);
          return Array.from(elements)
            .map((el) => {
              if (attr && el.getAttribute(attr)) {
                return el.getAttribute(attr);
              }
              return el.textContent?.trim();
            })
            .filter((v): v is string => !!v);
        },
        { sel: selector, attr: valueAttribute }
      );
      return values;
    } catch (error) {
      logger.warn({ selector, error }, 'Failed to extract values');
      return [];
    }
  }

  /**
   * 숨겨진 드롭다운/팝업 펼치기 (이전 프로젝트 패턴 적용)
   */
  private async expandAllDropdowns(page: Page): Promise<void> {
    try {
      // 1. 화살표 아이콘 클릭 (▼, ▲, >, <, 등)
      const arrowButtons = await page.$$('i[class*="caret"], i[class*="arrow"], i[class*="xi-"], button[class*="expand"], span[class*="arrow"]');
      for (const btn of arrowButtons.slice(0, 5)) {
        try {
          await btn.click();
          await fixedDelay(0.5);
        } catch {}
      }

      // 2. "요금제" 관련 요소 클릭
      const planKeywords = ['요금제', '요금 선택', '요금제 선택', '요금제 변경'];
      for (const keyword of planKeywords) {
        try {
          const elements = await page.$$(`text=${keyword}`);
          if (elements.length > 0) {
            await elements[0].click();
            await fixedDelay(0.5);
          }
        } catch {}
      }

      // 3. "더보기", "전체보기" 등 클릭
      const expandTexts = ['더보기', '전체보기', '펼치기', '모두보기'];
      for (const text of expandTexts) {
        try {
          await page.click(`text=${text}`, { timeout: 1000 });
          await fixedDelay(0.5);
        } catch {}
      }

      logger.debug('Expanded all dropdowns');
    } catch (error) {
      logger.debug({ error }, 'expandAllDropdowns: some dropdowns may not exist');
    }
  }

  /**
   * 페이지 전체에서 직접 요금제 추출 (fallback)
   * 이전 프로젝트의 findAllOptions 패턴 적용
   */
  private async extractPlansDirectlyFromPage(
    page: Page
  ): Promise<Array<{ name: string; price: string }>> {
    try {
      // 먼저 드롭다운 펼치기
      await this.expandAllDropdowns(page);
      await fixedDelay(1);

      // HTML + 텍스트 모두 가져오기
      const pageHtml = await page.evaluate(() => document.body.innerHTML);
      const pageText = await page.evaluate(() => document.body.innerText);

      // 상세한 프롬프트로 요금제 추출
      const prompt = `
이 페이지에서 **모든 휴대폰 요금제**를 찾으세요.
드롭다운이나 숨겨진 요소에 있는 요금제도 모두 찾아야 합니다!

# HTML (첫 60,000자)
${pageHtml.slice(0, 60000)}

# 페이지 텍스트 (첫 20,000자)
${pageText.slice(0, 20000)}

# 요금제 찾는 방법
1. "plan_list_item", "plan_list_title" 클래스 안의 텍스트
2. "월 XX,XXX원" 형식 근처의 요금제명
3. "5G", "LTE", "프리미어", "시그니처", "초이스", "무제한" 등 키워드
4. 통신사 요금제 패턴: "5G 프리미어 슈퍼", "5G 시그니처", "LTE 프리미어", "5GX 프리미엄" 등

# 규칙
1. 요금제 이름 + 월 요금이 있는 항목만
2. 월 60,000원 이상인 요금제만
3. 부가서비스(넷플릭스, 유튜브 프리미엄 등)는 제외

# 응답 형식 (JSON 배열만)
[
  {"name": "5G 프리미어 슈퍼", "price": "110000"},
  {"name": "5G 프리미어 플러스", "price": "89000"},
  {"name": "5G 시그니처", "price": "109000"}
]

**반드시 실제 페이지에 있는 요금제만 반환하세요. 예시를 그대로 반환하지 마세요!**
`;

      const response = await this.llm.complete(
        '당신은 휴대폰 요금제 추출 전문가입니다. 페이지에서 모든 통신 요금제를 찾아야 합니다.',
        prompt
      );

      const plans = this.parseJsonResponse(response.content) as Array<{
        name: string;
        price: string | number;
      }>;

      if (!Array.isArray(plans)) {
        logger.warn('extractPlansDirectlyFromPage: Invalid response format');
        return [];
      }

      const filteredPlans = plans
        .filter((p) => {
          if (!p.name || !p.price) return false;
          const price = typeof p.price === 'string' ? parseInt(p.price.replace(/,/g, '')) : p.price;
          return price >= 60000;
        })
        .map((p) => ({
          name: p.name,
          price: String(typeof p.price === 'string' ? p.price.replace(/,/g, '') : p.price),
        }));

      logger.info({ count: filteredPlans.length }, 'extractPlansDirectlyFromPage: Plans found');
      return filteredPlans;
    } catch (error) {
      logger.error({ error }, 'extractPlansDirectlyFromPage failed');
      return [];
    }
  }

  /**
   * Extract plans using LLM
   */
  private async extractPlansWithLLM(
    page: Page,
    planInfo: PlanUIInfo
  ): Promise<Array<{ name: string; price: string }>> {
    try {
      // Click open button if exists
      if (planInfo.open_button_selector) {
        try {
          await page.click(planInfo.open_button_selector);
          await fixedDelay(1);
        } catch {
          // Ignore click errors
        }
      }

      // Extract HTML with price information
      const html = await page.evaluate(() => {
        const allElements = document.querySelectorAll('*');
        let bestElement: Element | null = null;
        let maxPrices = 0;

        for (const el of allElements) {
          const style = window.getComputedStyle(el);
          if (style.display === 'none' || style.visibility === 'hidden') continue;

          const text = el.innerHTML || '';
          const priceMatches = text.match(/\d{2,3},?\d{3}\s*원/g);
          const priceCount = priceMatches?.length || 0;

          if (priceCount >= 5 && priceCount > maxPrices) {
            maxPrices = priceCount;
            bestElement = el;
          }
        }

        return bestElement?.outerHTML || document.body.innerHTML.slice(0, 100000);
      });

      // Use LLM to extract plans
      const prompt = `
다음 HTML에서 **모든 휴대폰 요금제**를 추출하세요.

# HTML
${html.slice(0, 50000)}

# 규칙
1. 요금제 이름 + 가격이 있는 항목만
2. 60,000원 이상만
3. 부가 혜택(무제한, 넷플릭스 등) 제외

# 응답 (JSON 배열만)
[
  {"name": "5G 심플 30GB", "price": "61000"}
]
`;

      const response = await this.llm.complete(
        '당신은 요금제 추출 전문가입니다.',
        prompt
      );

      const plans = this.parseJsonResponse(response.content) as Array<{
        name: string;
        price: string | number;
      }>;

      return plans
        .filter((p) => {
          const price = typeof p.price === 'string' ? parseInt(p.price.replace(/,/g, '')) : p.price;
          return price >= 60000;
        })
        .map((p) => ({
          name: p.name,
          price: String(typeof p.price === 'string' ? p.price.replace(/,/g, '') : p.price),
        }));
    } catch (error) {
      logger.warn({ error }, 'Failed to extract plans');
      return [];
    }
  }

  /**
   * Step 4: Generate option combinations
   */
  private step4GenerateCombinations(
    options: OptionValues,
    _structure: PageStructure
  ): Combination[] {
    const combinations: Combination[] = [];

    // Use defaults if options are empty or undefined
    const storages = options.storage && options.storage.length > 0
      ? options.storage
      : ['256GB'];
    const carriers = options.carrier && options.carrier.length > 0
      ? options.carrier
      : ['SKT', 'KT', 'LGU+'];
    const joinTypes = options.join_type && options.join_type.length > 0
      ? options.join_type
      : ['번호이동', '기기변경', '신규가입'];  // 신규가입 추가
    const plans = options.plan || [];

    for (const storage of storages) {
      for (const carrier of carriers) {
        for (const joinType of joinTypes) {
          if (plans.length > 0) {
            for (const plan of plans) {
              combinations.push({
                storage,
                carrier,
                join_type: joinType,
                plan: plan.name,
                plan_price: plan.price,
              });
            }
          } else {
            combinations.push({
              storage,
              carrier,
              join_type: joinType,
            });
          }
        }
      }
    }

    return combinations;
  }

  /**
   * Step 5: Extract policies for each combination (배치 처리 최적화)
   * 모든 조합을 한 번의 LLM 호출로 추출
   */
  private async step5ExtractPolicies(
    page: Page,
    combinations: Combination[],
    _basicInfo: { product_name: string },
    structure: PageStructure
  ): Promise<PolicyResultInternal[]> {
    // 배치 처리: 페이지 HTML 한 번 가져와서 모든 조합 한번에 추출
    logger.debug({ count: combinations.length }, 'Extracting all combinations in batch');

    try {
      // 먼저 현재 페이지 HTML 가져오기
      const html = await page.content();
      const cleanedHtml = this.cleanHtml(html);

      // 배치로 모든 조합의 가격 추출
      const batchResults = await this.extractPricingBatch(cleanedHtml, combinations);

      // 결과 매핑
      const results: PolicyResultInternal[] = combinations.map((combo, index) => {
        const pricing = batchResults[index];
        if (pricing) {
          return { success: true, combo, pricing };
        } else {
          return { success: false, combo, error: 'No pricing found' };
        }
      });

      return results;
    } catch (error) {
      logger.error({ error }, 'Batch extraction failed, falling back to sequential');
      // Fallback to sequential processing
      return this.step5ExtractPoliciesSequential(page, combinations, structure);
    }
  }

  /**
   * Step 5 Sequential fallback (배치 실패 시)
   */
  private async step5ExtractPoliciesSequential(
    page: Page,
    combinations: Combination[],
    structure: PageStructure
  ): Promise<PolicyResultInternal[]> {
    const results: PolicyResultInternal[] = [];

    for (let i = 0; i < combinations.length; i++) {
      const combo = combinations[i];
      logger.debug({ index: i + 1, total: combinations.length, combo }, 'Processing combination (sequential)');

      try {
        await this.selectOptions(page, combo, structure);
        const pricing = await this.extractPricing(page, structure);
        results.push({ success: true, combo, pricing });
      } catch (error) {
        logger.warn({ combo, error }, 'Failed to process combination');
        results.push({ success: false, combo, error: String(error) });
      }
    }

    return results;
  }

  /**
   * 배치로 모든 조합의 가격 추출 (단일 LLM 호출)
   */
  private async extractPricingBatch(
    html: string,
    combinations: Combination[]
  ): Promise<(ExtractedPricing | null)[]> {
    const comboList = combinations.map((c, i) => ({
      index: i,
      storage: c.storage || '256GB',
      carrier: c.carrier || 'SKT',
      join_type: c.join_type || '기기변경',
      plan: c.plan || 'Unknown',
      plan_price: c.plan_price,
    }));

    const prompt = `
다음 휴대폰 상세 페이지 HTML에서 **모든 조합의 가격 정보**를 추출하세요.

# HTML (첫 50,000자)
${html.slice(0, 50000)}

# 추출할 조합 목록
${JSON.stringify(comboList, null, 2)}

# 규칙
1. 각 조합에 대해 해당하는 가격 정보 추출
2. 휴대폰 가격은 보통 100,000원 이상임
3. 같은 용량/통신사/가입유형에서 요금제만 다른 경우, 할부원금과 월 납부금만 다를 수 있음
4. 찾을 수 없는 필드는 null로 설정

# 가격 필드 설명
- retail_price: 출고가/기기가격 (예: 1,980,000원)
- public_subsidy: 공시지원금 (예: 400,000원)
- additional_subsidy: 추가지원금/할인 (예: 150,000원)
- installment_principal: 할부원금 (출고가 - 지원금)
- monthly_payment: 월 할부금/월 납부액

# 응답 형식 (JSON 배열, 조합 순서대로)
[
  {
    "index": 0,
    "retail_price": 1980000,
    "public_subsidy": 400000,
    "additional_subsidy": 150000,
    "installment_principal": 1430000,
    "monthly_payment": 63314
  },
  {
    "index": 1,
    "retail_price": 1980000,
    "public_subsidy": 400000,
    "additional_subsidy": 150000,
    "installment_principal": 1430000,
    "monthly_payment": 63314
  }
]

**반드시 ${combinations.length}개의 결과를 반환하세요. JSON 배열만 출력하세요.**
`;

    try {
      const response = await this.llm.complete(
        '당신은 휴대폰 가격 정보 추출 전문가입니다. HTML에서 정확한 가격을 추출해야 합니다.',
        prompt
      );

      const parsed = this.parseJsonResponse(response.content) as Array<{
        index: number;
        retail_price?: number | null;
        public_subsidy?: number | null;
        additional_subsidy?: number | null;
        installment_principal?: number | null;
        monthly_payment?: number | null;
      }>;

      if (!Array.isArray(parsed)) {
        logger.warn('Batch extraction returned non-array');
        return combinations.map(() => null);
      }

      // index 기반으로 매핑
      const resultMap = new Map(parsed.map(p => [p.index, p]));

      return combinations.map((_, i) => {
        const p = resultMap.get(i);
        if (!p) return null;
        return {
          retail_price: p.retail_price ?? null,
          public_subsidy: p.public_subsidy ?? null,
          additional_subsidy: p.additional_subsidy ?? null,
          installment_principal: p.installment_principal ?? null,
          monthly_payment: p.monthly_payment ?? null,
        };
      });
    } catch (error) {
      logger.error({ error }, 'extractPricingBatch failed');
      return combinations.map(() => null);
    }
  }

  /**
   * Select options on page
   */
  private async selectOptions(
    page: Page,
    combo: Combination,
    structure: PageStructure
  ): Promise<void> {
    // Select storage
    if (combo.storage && structure.options.storage?.selector) {
      await this.clickOptionByValue(page, structure.options.storage.selector, combo.storage);
      await fixedDelay(0.3);
    }

    // Select carrier
    if (combo.carrier && structure.options.carrier?.selector) {
      await this.clickOptionByValue(page, structure.options.carrier.selector, combo.carrier);
      await fixedDelay(0.5);
    }

    // Select join type
    if (combo.join_type && structure.options.join_type?.selector) {
      await this.clickOptionByValue(page, structure.options.join_type.selector, combo.join_type);
      await fixedDelay(0.3);
    }

    // Select plan
    if (combo.plan && structure.options.plan?.open_button_selector) {
      await this.selectPlan(page, structure.options.plan, combo.plan, combo.plan_price);
      await fixedDelay(1);
    }
  }

  /**
   * Click option by value
   */
  private async clickOptionByValue(
    page: Page,
    selector: string,
    value: string
  ): Promise<boolean> {
    try {
      const clicked = await page.evaluate(
        ({ sel, val }) => {
          const elements = document.querySelectorAll(sel);
          for (const el of elements) {
            const attrValue = el.getAttribute('value') || el.textContent?.trim();
            if (attrValue === val || attrValue?.includes(val)) {
              (el as HTMLElement).click();
              return true;
            }
          }
          return false;
        },
        { sel: selector, val: value }
      );
      return clicked;
    } catch {
      return false;
    }
  }

  /**
   * Select plan from dropdown/modal
   */
  private async selectPlan(
    page: Page,
    planInfo: PlanUIInfo,
    planName: string,
    planPrice?: string
  ): Promise<boolean> {
    try {
      // Open dropdown
      if (planInfo.open_button_selector) {
        await page.click(planInfo.open_button_selector);
        await fixedDelay(0.5);
      }

      // Click plan item
      if (planInfo.item_selector) {
        const clicked = await page.evaluate(
          ({ itemSel, name, price }) => {
            const items = document.querySelectorAll(itemSel);
            for (const item of items) {
              const text = item.textContent || '';
              // Match by price first
              if (price) {
                const priceMatch = text.match(/(\d{1,3}(?:,\d{3})*)/);
                if (priceMatch && priceMatch[1].replace(/,/g, '') === price) {
                  (item as HTMLElement).click();
                  return true;
                }
              }
              // Match by name
              if (text.includes(name)) {
                (item as HTMLElement).click();
                return true;
              }
            }
            return false;
          },
          { itemSel: planInfo.item_selector, name: planName, price: planPrice }
        );
        return clicked;
      }

      return false;
    } catch {
      return false;
    }
  }

  /**
   * Extract pricing information
   */
  private async extractPricing(page: Page, structure: PageStructure): Promise<ExtractedPricing> {
    const pricing: ExtractedPricing = {};

    const selectors = structure.pricing;

    // Try to extract each price field
    if (selectors.retail_price_selector) {
      pricing.retail_price = await this.extractPriceFromSelector(
        page,
        selectors.retail_price_selector
      );
    }

    if (selectors.public_subsidy_selector) {
      pricing.public_subsidy = await this.extractPriceFromSelector(
        page,
        selectors.public_subsidy_selector
      );
    }

    if (selectors.additional_subsidy_selector) {
      pricing.additional_subsidy = await this.extractPriceFromSelector(
        page,
        selectors.additional_subsidy_selector
      );
    }

    if (selectors.installment_principal_selector) {
      pricing.installment_principal = await this.extractPriceFromSelector(
        page,
        selectors.installment_principal_selector
      );
    }

    if (selectors.monthly_payment_selector) {
      pricing.monthly_payment = await this.extractPriceFromSelector(
        page,
        selectors.monthly_payment_selector
      );
    }

    // If no prices extracted, try LLM fallback
    if (!Object.values(pricing).some((v) => v !== undefined && v !== null)) {
      return this.extractPricingWithLLM(page);
    }

    return pricing;
  }

  /**
   * Extract price from selector
   */
  private async extractPriceFromSelector(page: Page, selector: string): Promise<number | null> {
    try {
      const value = await page.evaluate((sel) => {
        const elem = document.querySelector(sel);
        if (!elem) return null;

        const text = elem.textContent || '';
        // Look for price patterns (Korean won format: 1,234,000원 or just 1234000)
        const match = text.match(/[\d,]+/);
        if (match) {
          return parseInt(match[0].replace(/,/g, ''));
        }
        return null;
      }, selector);

      // Validate: phone prices should be at least 100,000 won
      // Invalid prices (like ranking numbers "25") are filtered out
      if (value !== null && value < 100000) {
        logger.debug({ selector, value }, 'Price too low, likely invalid extraction');
        return null;
      }

      return value;
    } catch {
      return null;
    }
  }

  /**
   * Extract pricing using LLM
   */
  private async extractPricingWithLLM(page: Page): Promise<ExtractedPricing> {
    try {
      const html = await page.content();
      const prompt = formatScreenExtractPricingPrompt(html);

      const response = await this.llm.complete(SCREEN_EXTRACT_PRICING_SYSTEM, prompt);

      return this.parseJsonResponse(response.content) as ExtractedPricing;
    } catch (error) {
      logger.warn({ error }, 'Failed to extract pricing with LLM');
      return {};
    }
  }

  /**
   * Step 6: Convert results to Product[] schema (Python 호환)
   * PRD 필터링 적용: 할인유형=공시지원금만, 요금제>=6만원
   */
  private step6ConvertToSchema(
    results: PolicyResultInternal[],
    siteName: string,
    basicInfo: { product_name: string }
  ): Product[] {
    const successfulResults = results.filter((r) => r.success);

    if (successfulResults.length === 0) {
      return [];
    }

    // Group by storage
    const productsMap = new Map<string, { storage: string; policies: Policy[] }>();

    for (const result of successfulResults) {
      const combo = result.combo;
      const pricing = result.pricing || {};

      // PRD 필터: 요금제 6만원 이상만 (안전장치)
      const monthlyFee = parsePrice(combo.plan_price) || 0;
      if (monthlyFee < 60000) {
        logger.debug({ combo, monthlyFee }, 'Skipping policy: monthly_fee < 60000');
        continue;
      }

      const storage = combo.storage || '256GB';
      const storageType = parseStorage(storage);

      if (!productsMap.has(storage)) {
        productsMap.set(storage, { storage, policies: [] });
      }

      // Determine join type
      const joinTypeStr = combo.join_type || '기기변경';
      let joinType: '번호이동' | '기기변경' | '신규가입' = '기기변경';
      if (joinTypeStr.includes('번호이동')) joinType = '번호이동';
      else if (joinTypeStr.includes('신규')) joinType = '신규가입';

      // Convert carrier to code
      const carrierCode = carrierToCode(combo.carrier || 'SKT');

      // Generate policy ID
      const policyId = generatePolicyId(
        carrierCode,
        joinType,
        storageType,
        combo.plan || 'Unknown'
      );

      // Create policy (Python 호환 snake_case)
      // PRD: 할인유형 = 공시지원금만
      const policy: Policy = {
        policy_id: policyId,
        carrier: carrierCode,
        mno_join_type: JoinTypeEnum.parse(joinType),
        mobile_plan: {
          name: combo.plan || 'Unknown',
          monthly_fee: monthlyFee,
        },
        discount_type: DiscountTypeEnum.parse('공시지원금'),
        pricing: {
          mno_retail_price: pricing.retail_price || null,
          public_subsidy: pricing.public_subsidy || null,
          discount: pricing.additional_subsidy || null,
          sku_installment_fee: pricing.installment_principal || null,
          monthly_payment: pricing.monthly_payment || null,
        },
        addons: [],
        policy_text: null,
      };

      productsMap.get(storage)!.policies.push(policy);
    }

    // Convert to products (Python 호환)
    const products: Product[] = Array.from(productsMap.entries()).map(([storage, data]) => {
      const storageType = parseStorage(storage);
      const skuCode = `${basicInfo.product_name} - ${siteName}`;
      const productId = generateProductId(skuCode, storageType);

      return {
        product_id: productId,
        sku_code: skuCode,
        sku_storage: storageType,
        policies: data.policies,
        product_name: null,
        product_color: null,
      };
    });

    return products;
  }

  /**
   * Parse JSON from LLM response
   */
  private parseJsonResponse(content: string): unknown {
    let jsonStr = content.trim();

    // Remove markdown code blocks
    const jsonBlockMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonBlockMatch) {
      jsonStr = jsonBlockMatch[1].trim();
    }

    // Find JSON object or array
    const jsonMatch = jsonStr.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1];
    }

    try {
      return JSON.parse(jsonStr);
    } catch (error) {
      logger.error({ content: content.slice(0, 500), error }, 'Failed to parse JSON');
      return {};
    }
  }
}

export function createDetailPageAnalyzer(llmClient: LLMClient): DetailPageAnalyzer {
  return new DetailPageAnalyzer(llmClient);
}
