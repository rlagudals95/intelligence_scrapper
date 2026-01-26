import { z } from 'zod';

// Storage type enum
export const StorageTypeEnum = z.enum([
  'STORAGE_128GB',
  'STORAGE_256GB',
  'STORAGE_512GB',
  'STORAGE_1TB',
  'STORAGE_2TB',
]);

export type StorageType = z.infer<typeof StorageTypeEnum>;

// Join type enum
export const JoinTypeEnum = z.enum(['기기변경', '번호이동', '신규가입']);

export type JoinType = z.infer<typeof JoinTypeEnum>;

// Discount type enum
export const DiscountTypeEnum = z.enum(['공시지원금', '선택약정']);

export type DiscountType = z.infer<typeof DiscountTypeEnum>;

// Mobile plan schema
export const MobilePlanSchema = z.object({
  name: z.string(),
  monthlyFee: z.number(),
});

export type MobilePlan = z.infer<typeof MobilePlanSchema>;

// Pricing details schema
export const PricingDetailsSchema = z.object({
  retailPrice: z.number(),
  publicSubsidy: z.number().optional(),
  additionalDiscount: z.number().optional(),
  contractDiscount: z.number().optional(),
  finalPrice: z.number(),
  monthlyInstallment: z.number().optional(),
  installmentMonths: z.number().optional(),
});

export type PricingDetails = z.infer<typeof PricingDetailsSchema>;

// Addon schema
export const AddonSchema = z.object({
  name: z.string(),
  price: z.number().optional(),
  description: z.string().optional(),
});

export type Addon = z.infer<typeof AddonSchema>;

// Policy schema
export const PolicySchema = z.object({
  carrier: z.string(),
  joinType: JoinTypeEnum,
  discountType: DiscountTypeEnum,
  plan: MobilePlanSchema,
  storage: StorageTypeEnum.optional(),
  color: z.string().optional(),
  pricing: PricingDetailsSchema,
  policyText: z.string().optional(),
  addons: z.array(AddonSchema).optional(),
  hash: z.string(),
});

export type Policy = z.infer<typeof PolicySchema>;

// Phase 3 Product schema
export const Phase3ProductSchema = z.object({
  name: z.string(),
  manufacturer: z.string().optional(),
  modelCode: z.string().optional(),
  sku: z.string().optional(),
  policies: z.array(PolicySchema),
});

export type Phase3Product = z.infer<typeof Phase3ProductSchema>;

// Source info schema
export const SourceInfoSchema = z.object({
  siteName: z.string(),
  url: z.string().url(),
});

export type SourceInfo = z.infer<typeof SourceInfoSchema>;

// Phase 3 Scraping result schema
export const Phase3ScrapingResultSchema = z.object({
  products: z.array(Phase3ProductSchema),
  capturedAt: z.string(),
  source: SourceInfoSchema,
});

export type Phase3ScrapingResult = z.infer<typeof Phase3ScrapingResultSchema>;

// Utility functions
export function parsePrice(priceStr: string | number | undefined | null): number {
  if (priceStr === undefined || priceStr === null) return 0;
  if (typeof priceStr === 'number') return priceStr;

  const cleaned = priceStr.replace(/[^\d]/g, '');
  const parsed = parseInt(cleaned, 10);
  return isNaN(parsed) ? 0 : parsed;
}

export function parseStorage(storageStr: string | undefined | null): StorageType | undefined {
  if (!storageStr) return undefined;

  const normalized = storageStr.toUpperCase().replace(/\s/g, '');

  if (normalized.includes('128')) return 'STORAGE_128GB';
  if (normalized.includes('256')) return 'STORAGE_256GB';
  if (normalized.includes('512')) return 'STORAGE_512GB';
  if (normalized.includes('1TB') || normalized.includes('1024')) return 'STORAGE_1TB';
  if (normalized.includes('2TB') || normalized.includes('2048')) return 'STORAGE_2TB';

  return undefined;
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
