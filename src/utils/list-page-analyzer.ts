import { z } from 'zod';
import { LLMClient } from '../core/llm-client.js';
import { BrowserManager } from '../core/browser.js';
import { getLogger } from './logger.js';
import {
  LISTING_PAGE_ANALYSIS_SYSTEM,
  formatListingAnalysisPrompt,
  DETAIL_PAGE_OPTIONS_SYSTEM,
  formatDetailOptionsPrompt,
  PRICING_AREA_SYSTEM,
  formatPricingAreaPrompt,
} from './prompts.js';

const logger = getLogger('ListPageAnalyzer');

// Schema for listing page analysis result
export const ListingAnalysisResultSchema = z.object({
  product_card_selector: z.string(),
  product_name_selector: z.string(),
  detail_link_selector: z.string(),
  carrier_selector: z.string().nullable().optional(),
  signup_type_selector: z.string().nullable().optional(),
  retail_price_selector: z.string().nullable().optional(),
  discount_price_selector: z.string().nullable().optional(),
  subsidy_type_selector: z.string().nullable().optional(),
  public_subsidy_selector: z.string().nullable().optional(),
  additional_subsidy_selector: z.string().nullable().optional(),
  plan_name_selector: z.string().nullable().optional(),
  benefits_selector: z.string().nullable().optional(),
  image_selector: z.string().nullable().optional(),
  pagination_type: z.enum(['pagination', 'infinite_scroll', 'none']).default('none'),
  next_button_selector: z.string().nullable().optional(),
});

export type ListingAnalysisResult = z.infer<typeof ListingAnalysisResultSchema>;

// Schema for option UI info
export const OptionUIInfoSchema = z.object({
  selector: z.string().nullable().optional(),
  type: z.enum(['select', 'radio', 'button', 'tab']).nullable().optional(),
  option_selector: z.string().nullable().optional(),
  exists: z.boolean().default(false),
});

export type OptionUIInfo = z.infer<typeof OptionUIInfoSchema>;

// Schema for detail page options analysis result
export const DetailOptionsResultSchema = z.object({
  carrier: OptionUIInfoSchema.optional(),
  signup_type: OptionUIInfoSchema.optional(),
  plan: OptionUIInfoSchema.optional(),
  installment: OptionUIInfoSchema.optional(),
  storage: OptionUIInfoSchema.optional(),
  color: OptionUIInfoSchema.optional(),
});

export type DetailOptionsResult = z.infer<typeof DetailOptionsResultSchema>;

// Schema for pricing area info
export const PricingAreaInfoSchema = z.object({
  selector: z.string().nullable().optional(),
  exists: z.boolean().default(false),
});

export type PricingAreaInfo = z.infer<typeof PricingAreaInfoSchema>;

// Schema for pricing area analysis result
export const PricingAreaResultSchema = z.object({
  final_price: PricingAreaInfoSchema.optional(),
  installment_principal: PricingAreaInfoSchema.optional(),
  monthly_payment: PricingAreaInfoSchema.optional(),
  subsidy_official: PricingAreaInfoSchema.optional(),
  subsidy_additional: PricingAreaInfoSchema.optional(),
  plan_condition: PricingAreaInfoSchema.optional(),
  policy_text: PricingAreaInfoSchema.optional(),
});

export type PricingAreaResult = z.infer<typeof PricingAreaResultSchema>;

export class ListPageAnalyzer {
  private llmClient: LLMClient;

  constructor(llmClient: LLMClient) {
    this.llmClient = llmClient;
  }

  /**
   * Analyze listing page structure using LLM
   */
  async analyzeListingPage(
    browser: BrowserManager,
    useScreenshot: boolean = true
  ): Promise<ListingAnalysisResult> {
    logger.info('Analyzing listing page structure...');

    const html = await browser.getSimplifiedHtml();
    const prompt = formatListingAnalysisPrompt(html);

    let response;
    if (useScreenshot) {
      const screenshotBase64 = await browser.screenshotBase64();
      response = await this.llmClient.completeWithVision(
        LISTING_PAGE_ANALYSIS_SYSTEM,
        prompt,
        screenshotBase64
      );
    } else {
      response = await this.llmClient.complete(LISTING_PAGE_ANALYSIS_SYSTEM, prompt);
    }

    const parsed = this.parseJsonResponse(response.content);
    const result = ListingAnalysisResultSchema.parse(parsed);

    logger.info(
      {
        productCardSelector: result.product_card_selector,
        paginationType: result.pagination_type,
      },
      'Listing page analysis complete'
    );

    return result;
  }

  /**
   * Analyze detail page options UI using LLM
   */
  async analyzeDetailPageOptions(
    browser: BrowserManager,
    useScreenshot: boolean = true
  ): Promise<DetailOptionsResult> {
    logger.info('Analyzing detail page options...');

    const html = await browser.getSimplifiedHtml();
    const prompt = formatDetailOptionsPrompt(html);

    let response;
    if (useScreenshot) {
      const screenshotBase64 = await browser.screenshotBase64();
      response = await this.llmClient.completeWithVision(
        DETAIL_PAGE_OPTIONS_SYSTEM,
        prompt,
        screenshotBase64
      );
    } else {
      response = await this.llmClient.complete(DETAIL_PAGE_OPTIONS_SYSTEM, prompt);
    }

    const parsed = this.parseJsonResponse(response.content);
    const result = DetailOptionsResultSchema.parse(parsed);

    logger.info('Detail page options analysis complete');

    return result;
  }

  /**
   * Analyze pricing area selectors using LLM
   */
  async analyzePricingArea(
    browser: BrowserManager,
    useScreenshot: boolean = true
  ): Promise<PricingAreaResult> {
    logger.info('Analyzing pricing area...');

    const html = await browser.getSimplifiedHtml();
    const prompt = formatPricingAreaPrompt(html);

    let response;
    if (useScreenshot) {
      const screenshotBase64 = await browser.screenshotBase64();
      response = await this.llmClient.completeWithVision(
        PRICING_AREA_SYSTEM,
        prompt,
        screenshotBase64
      );
    } else {
      response = await this.llmClient.complete(PRICING_AREA_SYSTEM, prompt);
    }

    const parsed = this.parseJsonResponse(response.content);
    const result = PricingAreaResultSchema.parse(parsed);

    logger.info('Pricing area analysis complete');

    return result;
  }

  /**
   * Parse JSON from LLM response, handling markdown code blocks
   */
  private parseJsonResponse(content: string): unknown {
    // Remove markdown code blocks if present
    let jsonStr = content.trim();

    // Handle ```json ... ``` format
    const jsonBlockMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonBlockMatch) {
      jsonStr = jsonBlockMatch[1].trim();
    }

    // Try to find JSON object or array
    const jsonMatch = jsonStr.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1];
    }

    try {
      return JSON.parse(jsonStr);
    } catch (error) {
      logger.error({ content, error }, 'Failed to parse JSON from LLM response');
      throw new Error(`Failed to parse JSON: ${error}`);
    }
  }
}

export function createListPageAnalyzer(llmClient: LLMClient): ListPageAnalyzer {
  return new ListPageAnalyzer(llmClient);
}
