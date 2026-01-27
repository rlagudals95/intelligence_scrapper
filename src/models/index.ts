// Phase 2 schemas (listing page)
export {
  OptionSchema,
  Option,
  PlanOptionSchema,
  PlanOption,
  OptionsCatalogSchema,
  OptionsCatalog,
  PricingSchema,
  Pricing,
  SelectedOptionsSchema,
  SelectedOptions,
  VariantSchema,
  Variant,
  PhoneListingItemSchema,
  PhoneListingItem,
} from './schemas.js';

// Phase 3 schemas (Python 호환)
export {
  // Enums
  StorageTypeEnum,
  StorageType,
  JoinTypeEnum,
  JoinType,
  DiscountTypeEnum,
  DiscountType,
  CarrierEnum,
  Carrier,
  SkuCodeEnum,
  SkuCode,
  // Core schemas
  MobilePlanSchema,
  MobilePlan,
  PricingDetailsSchema,
  PricingDetails,
  AddonSchema,
  Addon,
  PolicySchema,
  Policy,
  ProductSchema,
  Product,
  // Result schemas
  ProductResultSchema,
  ProductResult,
  ScrapingResultSchema,
  ScrapingResult,
  // ID generation
  generateProductId,
  generatePolicyId,
  // Utilities
  parsePrice,
  parseStorage,
  normalizeCarrier,
  normalizeDiscountType,
  normalizeJoinType,
  normalizeSkuCode,
  // Builders
  createPolicy,
  createProduct,
} from './phase3-schemas.js';
