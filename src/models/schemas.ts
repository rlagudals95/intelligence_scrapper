import { z } from 'zod';

// Option schema
export const OptionSchema = z.object({
  value: z.string(),
  disabled: z.boolean().default(false),
  reason: z.string().optional(),
});

export type Option = z.infer<typeof OptionSchema>;

// Plan option schema
export const PlanOptionSchema = z.object({
  name: z.string(),
  monthlyFee: z.number().optional(),
  benefits: z.string().optional(),
});

export type PlanOption = z.infer<typeof PlanOptionSchema>;

// Options catalog schema
export const OptionsCatalogSchema = z.object({
  carriers: z.array(OptionSchema).default([]),
  signupTypes: z.array(OptionSchema).default([]),
  plans: z.array(PlanOptionSchema).default([]),
  installments: z.array(OptionSchema).default([]),
  storages: z.array(OptionSchema).default([]),
  colors: z.array(OptionSchema).default([]),
  others: z.record(z.array(OptionSchema)).default({}),
});

export type OptionsCatalog = z.infer<typeof OptionsCatalogSchema>;

// Pricing schema
export const PricingSchema = z.object({
  finalPrice: z.number().optional(),
  retailPrice: z.number().optional(),
  installmentPrincipal: z.number().optional(),
  monthlyPayment: z.number().optional(),
  subsidyOfficial: z.number().optional(),
  subsidyAdditional: z.number().optional(),
  contractDiscount: z.number().optional(),
  totalDiscount: z.number().optional(),
});

export type Pricing = z.infer<typeof PricingSchema>;

// Selected options schema
export const SelectedOptionsSchema = z.object({
  carrier: z.string().optional(),
  signupType: z.string().optional(),
  plan: z.string().optional(),
  installment: z.string().optional(),
  storage: z.string().optional(),
  color: z.string().optional(),
  others: z.record(z.string()).default({}),
});

export type SelectedOptions = z.infer<typeof SelectedOptionsSchema>;

// Variant schema
export const VariantSchema = z.object({
  selectedOptions: SelectedOptionsSchema,
  pricing: PricingSchema,
  policyText: z.string().optional(),
  hash: z.string().optional(),
});

export type Variant = z.infer<typeof VariantSchema>;

// Phone listing item schema (from listing page)
export const PhoneListingItemSchema = z.object({
  modelName: z.string(),
  signupType: z.string().optional(),
  retailPrice: z.string().optional(),
  discountPrice: z.string().optional(),
  planName: z.string().optional(),
  detailUrl: z.string(),
  imageUrl: z.string().optional(),
  subsidy: z.string().optional(),
});

export type PhoneListingItem = z.infer<typeof PhoneListingItemSchema>;

// Product schema
export const ProductSchema = z.object({
  detailUrl: z.string(),
  productName: z.string(),
  manufacturer: z.string().optional(),
  modelCode: z.string().optional(),
  basePrice: z.string().optional(),
  status: z.string().optional(),
  optionsCatalog: OptionsCatalogSchema.optional(),
  variants: z.array(VariantSchema).default([]),
  errors: z.array(z.string()).default([]),
});

export type Product = z.infer<typeof ProductSchema>;

// Scraping metadata schema
export const ScrapingMetadataSchema = z.object({
  scrapedAt: z.string(),
  totalProducts: z.number(),
  totalVariants: z.number(),
  elapsedSeconds: z.number().optional(),
  siteName: z.string().optional(),
  sourceUrl: z.string().optional(),
});

export type ScrapingMetadata = z.infer<typeof ScrapingMetadataSchema>;

// Full scraping result schema
export const ScrapingResultSchema = z.object({
  products: z.array(ProductSchema),
  metadata: ScrapingMetadataSchema,
});

export type ScrapingResult = z.infer<typeof ScrapingResultSchema>;
