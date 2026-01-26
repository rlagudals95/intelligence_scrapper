import { z } from 'zod';
import { createHash } from 'crypto';

// ============================================================================
// Enums (Python 호환)
// ============================================================================

export const StorageTypeEnum = z.enum(['128GB', '256GB', '512GB', '1TB', '2TB']);
export type StorageType = z.infer<typeof StorageTypeEnum>;

export const JoinTypeEnum = z.enum(['기기변경', '번호이동', '신규가입']);
export type JoinType = z.infer<typeof JoinTypeEnum>;

export const DiscountTypeEnum = z.enum(['공시지원금', '선택약정']);
export type DiscountType = z.infer<typeof DiscountTypeEnum>;

// Carrier codes (Python uses "1", "2", "3")
export const CarrierCodeMap: Record<string, string> = {
  '1': 'SKT',
  '2': 'KT',
  '3': 'LGU+',
  SKT: '1',
  KT: '2',
  'LGU+': '3',
  LGU: '3',
};

// ============================================================================
// Core Schemas (Python snake_case 호환)
// ============================================================================

export const MobilePlanSchema = z.object({
  name: z.string(),
  monthly_fee: z.number(),
});
export type MobilePlan = z.infer<typeof MobilePlanSchema>;

export const PricingDetailsSchema = z.object({
  mno_retail_price: z.number().nullable().optional(),
  public_subsidy: z.number().nullable().optional(),
  discount: z.number().nullable().optional(), // 추가지원금
  sku_installment_fee: z.number().nullable().optional(), // 할부원금
  monthly_payment: z.number().nullable().optional(),
});
export type PricingDetails = z.infer<typeof PricingDetailsSchema>;

export const AddonSchema = z.object({
  name: z.string(),
  price: z.number(),
  keep_months: z.number().nullable().optional(),
});
export type Addon = z.infer<typeof AddonSchema>;

export const PolicySchema = z.object({
  policy_id: z.string(),
  carrier: z.string(), // "1", "2", "3" 코드
  mno_join_type: JoinTypeEnum,
  mobile_plan: MobilePlanSchema,
  discount_type: DiscountTypeEnum,
  pricing: PricingDetailsSchema,
  addons: z.array(AddonSchema).default([]),
  policy_text: z.string().nullable().optional(),
});
export type Policy = z.infer<typeof PolicySchema>;

export const ProductSchema = z.object({
  product_id: z.string(),
  sku_code: z.string(),
  sku_storage: StorageTypeEnum.nullable().optional(),
  policies: z.array(PolicySchema).default([]),
  product_name: z.string().nullable().optional(),
  product_color: z.string().nullable().optional(),
});
export type Product = z.infer<typeof ProductSchema>;

// ============================================================================
// Result Schemas
// ============================================================================

// 개별 상품 결과 (상세 페이지 단위)
export const ProductResultSchema = z.object({
  product_name: z.string(),
  url: z.string(),
  policy_count: z.number(),
  duration: z.number(),
  products: z.array(ProductSchema),
});
export type ProductResult = z.infer<typeof ProductResultSchema>;

// 최종 스크래핑 결과 (Python 출력 형식)
export const ScrapingResultSchema = z.object({
  site_name: z.string(),
  list_url: z.string(),
  target_models: z.array(z.string()),
  scraped_at: z.string(),
  total_duration: z.number(),
  results: z.array(ProductResultSchema),
});
export type ScrapingResult = z.infer<typeof ScrapingResultSchema>;

// ============================================================================
// ID Generation (MD5 Hash - Python 호환)
// ============================================================================

/**
 * Generate product ID (MD5 hash, 16 chars)
 * Python: hashlib.md5(f"{sku_code}|{storage}").hexdigest()[:16]
 */
export function generateProductId(skuCode: string, storage: string | null): string {
  const input = `${skuCode}|${storage || ''}`;
  return createHash('md5').update(input).digest('hex').slice(0, 16);
}

/**
 * Generate policy ID (MD5 hash, 16 chars)
 * Python: hashlib.md5(f"{carrier}|{join_type}|{storage}|{plan_name}").hexdigest()[:16]
 */
export function generatePolicyId(
  carrier: string,
  joinType: string,
  storage: string | null,
  planName: string
): string {
  const input = `${carrier}|${joinType}|${storage || ''}|${planName}`;
  return createHash('md5').update(input).digest('hex').slice(0, 16);
}

// ============================================================================
// Utility Functions
// ============================================================================

export function parsePrice(priceStr: string | number | undefined | null): number | null {
  if (priceStr === undefined || priceStr === null) return null;
  if (typeof priceStr === 'number') return priceStr;

  const cleaned = priceStr.replace(/[^\d-]/g, '');
  const parsed = parseInt(cleaned, 10);
  return isNaN(parsed) ? null : parsed;
}

export function parseStorage(storageStr: string | undefined | null): StorageType | null {
  if (!storageStr) return null;

  const normalized = storageStr.toUpperCase().replace(/\s/g, '');

  // Extract number
  const match = normalized.match(/(\d+)/);
  if (!match) return null;

  let sizeGB = parseInt(match[1], 10);

  // Handle TB
  if (normalized.includes('TB') || normalized.includes('T')) {
    sizeGB = sizeGB * 1024;
  }

  if (sizeGB <= 128) return '128GB';
  if (sizeGB <= 256) return '256GB';
  if (sizeGB <= 512) return '512GB';
  if (sizeGB <= 1024) return '1TB';
  if (sizeGB <= 2048) return '2TB';

  return null;
}

export function normalizeCarrier(carrier: string): string {
  const normalized = carrier.toUpperCase().replace(/\s/g, '');

  if (normalized.includes('SKT') || normalized.includes('SK텔레콤') || normalized.includes('에스케이'))
    return 'SKT';
  if (normalized.includes('KT') || normalized.includes('케이티')) return 'KT';
  if (
    normalized.includes('LGU') ||
    normalized.includes('LG유플러스') ||
    normalized.includes('엘지') ||
    normalized.includes('유플러스')
  )
    return 'LGU+';

  return carrier;
}

export function carrierToCode(carrier: string): string {
  const normalized = normalizeCarrier(carrier);
  return CarrierCodeMap[normalized] || carrier;
}

export function codeToCarrier(code: string): string {
  return CarrierCodeMap[code] || code;
}

// ============================================================================
// Builder Functions
// ============================================================================

export function createPolicy(params: {
  carrier: string;
  joinType: JoinType;
  storage: StorageType | null;
  plan: MobilePlan;
  discountType: DiscountType;
  pricing: PricingDetails;
  addons?: Addon[];
  policyText?: string | null;
}): Policy {
  const carrierCode = carrierToCode(params.carrier);
  const policyId = generatePolicyId(
    carrierCode,
    params.joinType,
    params.storage,
    params.plan.name
  );

  return {
    policy_id: policyId,
    carrier: carrierCode,
    mno_join_type: params.joinType,
    mobile_plan: params.plan,
    discount_type: params.discountType,
    pricing: params.pricing,
    addons: params.addons || [],
    policy_text: params.policyText || null,
  };
}

export function createProduct(params: {
  skuCode: string;
  storage: StorageType | null;
  policies: Policy[];
  productName?: string | null;
  productColor?: string | null;
}): Product {
  const productId = generateProductId(params.skuCode, params.storage);

  return {
    product_id: productId,
    sku_code: params.skuCode,
    sku_storage: params.storage,
    policies: params.policies,
    product_name: params.productName || null,
    product_color: params.productColor || null,
  };
}
