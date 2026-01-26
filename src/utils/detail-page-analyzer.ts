import crypto from 'crypto';
import { Page } from 'playwright';
import { LLMClient } from '../core/llm-client.js';
import { getLogger } from './logger.js';
import {
  Phase3ScrapingResult,
  Phase3Product,
  Policy,
  MobilePlan,
  PricingDetails,
  SourceInfo,
  JoinTypeEnum,
  DiscountTypeEnum,
  parseStorage,
  parsePrice,
  normalizeCarrier,
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

interface PolicyResult {
  success: boolean;
  combo: Combination;
  pricing?: ExtractedPricing;
  error?: string;
}

export class DetailPageAnalyzer {
  private llm: LLMClient;

  constructor(llmClient: LLMClient) {
    this.llm = llmClient;
    logger.info('DetailPageAnalyzer initialized');
  }

  /**
   * Analyze detail page and extract all policies
   */
  async analyzeDetailPage(
    page: Page,
    url: string,
    siteName: string = 'Unknown'
  ): Promise<Phase3ScrapingResult> {
    logger.info({ url, siteName }, 'Starting detail page analysis');

    // Step 1: Extract basic info
    const basicInfo = await this.step1ExtractBasicInfo(page, url);
    logger.info({ productName: basicInfo.product_name }, 'Step 1 complete: Basic info extracted');

    // Step 2: Analyze option UI and extract selectors
    const step2Result = await this.step2AnalyzeOptionUI(page);
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
        success: policyResults.filter((r) => r.success).length,
        failed: policyResults.filter((r) => !r.success).length,
      },
      'Step 5 complete: Policies extracted'
    );

    // Step 6: Convert to schema
    const result = this.step6ConvertToSchema(policyResults, url, siteName, basicInfo);
    logger.info(
      {
        products: result.products.length,
        policies: result.products.reduce((sum, p) => sum + p.policies.length, 0),
      },
      'Step 6 complete: Converted to schema'
    );

    return result;
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
   * Step 2: Analyze option UI using LLM
   */
  private async step2AnalyzeOptionUI(
    page: Page
  ): Promise<{ structure: PageStructure; options: OptionValues }> {
    try {
      const html = await page.content();
      const cleanedHtml = this.cleanHtml(html);

      // Step 2A: Extract selectors using LLM
      const structure = await this.step2aExtractSelectors(cleanedHtml);

      // Step 2B: Extract option values using selectors
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

    // Extract plans (requires opening dropdown/modal)
    if (structure.options.plan?.open_button_selector) {
      const plans = await this.extractPlansWithLLM(page, structure.options.plan);
      if (plans.length > 0) {
        options.plan = plans;
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

    const storages = options.storage || ['256GB'];
    const carriers = options.carrier || ['SKT', 'KT', 'LGU+'];
    const joinTypes = options.join_type || ['번호이동', '기기변경'];
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
   * Step 5: Extract policies for each combination
   */
  private async step5ExtractPolicies(
    page: Page,
    combinations: Combination[],
    _basicInfo: { product_name: string },
    structure: PageStructure
  ): Promise<PolicyResult[]> {
    const results: PolicyResult[] = [];

    for (let i = 0; i < combinations.length; i++) {
      const combo = combinations[i];
      logger.debug({ index: i + 1, total: combinations.length, combo }, 'Processing combination');

      try {
        // Select options
        await this.selectOptions(page, combo, structure);

        // Extract pricing
        const pricing = await this.extractPricing(page, structure);

        results.push({
          success: true,
          combo,
          pricing,
        });
      } catch (error) {
        logger.warn({ combo, error }, 'Failed to process combination');
        results.push({
          success: false,
          combo,
          error: String(error),
        });
      }
    }

    return results;
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
        const match = text.match(/[\d,]+/);
        if (match) {
          return parseInt(match[0].replace(/,/g, ''));
        }
        return null;
      }, selector);
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
   * Step 6: Convert results to Phase3ScrapingResult schema
   */
  private step6ConvertToSchema(
    results: PolicyResult[],
    url: string,
    siteName: string,
    basicInfo: { product_name: string }
  ): Phase3ScrapingResult {
    const successfulResults = results.filter((r) => r.success);

    if (successfulResults.length === 0) {
      return {
        products: [],
        capturedAt: new Date().toISOString(),
        source: { siteName, url },
      };
    }

    // Group by storage
    const productsMap = new Map<string, { storage: string; policies: Policy[] }>();

    for (const result of successfulResults) {
      const combo = result.combo;
      const pricing = result.pricing || {};

      const storage = combo.storage || '256GB';

      if (!productsMap.has(storage)) {
        productsMap.set(storage, { storage, policies: [] });
      }

      // Determine join type
      const joinTypeStr = combo.join_type || '기기변경';
      let joinType: '번호이동' | '기기변경' | '신규가입' = '기기변경';
      if (joinTypeStr.includes('번호이동')) joinType = '번호이동';
      else if (joinTypeStr.includes('신규')) joinType = '신규가입';

      // Normalize carrier
      const carrier = normalizeCarrier(combo.carrier || 'SKT');

      // Generate hash
      const hashInput = `${carrier}_${joinType}_${storage}_${combo.plan || ''}`;
      const hash = crypto.createHash('md5').update(hashInput).digest('hex').slice(0, 16);

      // Create policy
      const policy: Policy = {
        carrier,
        joinType: JoinTypeEnum.parse(joinType),
        discountType: DiscountTypeEnum.parse('공시지원금'),
        plan: {
          name: combo.plan || 'Unknown',
          monthlyFee: parsePrice(combo.plan_price),
        },
        storage: parseStorage(storage),
        pricing: {
          retailPrice: pricing.retail_price || 0,
          publicSubsidy: pricing.public_subsidy ?? undefined,
          additionalDiscount: pricing.additional_subsidy ?? undefined,
          finalPrice: pricing.final_price || pricing.installment_principal || 0,
          monthlyInstallment: pricing.monthly_payment ?? undefined,
        },
        hash,
      };

      productsMap.get(storage)!.policies.push(policy);
    }

    // Convert to products
    const products: Phase3Product[] = Array.from(productsMap.values()).map((data) => ({
      name: basicInfo.product_name,
      policies: data.policies,
    }));

    return {
      products,
      capturedAt: new Date().toISOString(),
      source: { siteName, url },
    };
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
