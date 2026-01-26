import { describe, it, expect } from 'vitest';
import {
  PhoneListingItemSchema,
  PricingSchema,
  VariantSchema,
} from '../src/models/schemas.js';
import {
  parsePrice,
  parseStorage,
  normalizeCarrier,
  PolicySchema,
  MobilePlanSchema,
  PricingDetailsSchema,
} from '../src/models/phase3-schemas.js';

describe('PhoneListingItemSchema', () => {
  it('should parse valid listing item', () => {
    const item = PhoneListingItemSchema.parse({
      modelName: '갤럭시 S25',
      detailUrl: 'https://example.com/phone/1',
      retailPrice: '1,500,000원',
      discountPrice: '1,000,000원',
    });

    expect(item.modelName).toBe('갤럭시 S25');
    expect(item.detailUrl).toBe('https://example.com/phone/1');
  });

  it('should require modelName and detailUrl', () => {
    expect(() => PhoneListingItemSchema.parse({})).toThrow();
    expect(() => PhoneListingItemSchema.parse({ modelName: 'Test' })).toThrow();
  });
});

describe('PricingSchema', () => {
  it('should parse pricing with optional fields', () => {
    const pricing = PricingSchema.parse({
      finalPrice: 1000000,
      retailPrice: 1500000,
      subsidyOfficial: 300000,
    });

    expect(pricing.finalPrice).toBe(1000000);
    expect(pricing.monthlyPayment).toBeUndefined();
  });
});

describe('parsePrice', () => {
  it('should parse Korean price format', () => {
    expect(parsePrice('1,500,000')).toBe(1500000);
    expect(parsePrice('1500000')).toBe(1500000);
    expect(parsePrice('1,500,000원')).toBe(1500000);
  });

  it('should handle invalid input', () => {
    expect(parsePrice(null)).toBeNull();
    expect(parsePrice(undefined)).toBeNull();
    expect(parsePrice('')).toBeNull();
  });

  it('should handle number input', () => {
    expect(parsePrice(1500000)).toBe(1500000);
  });
});

describe('parseStorage', () => {
  it('should parse storage strings', () => {
    expect(parseStorage('128GB')).toBe('128GB');
    expect(parseStorage('256GB')).toBe('256GB');
    expect(parseStorage('512GB')).toBe('512GB');
    expect(parseStorage('1TB')).toBe('1TB');
  });

  it('should handle case insensitivity', () => {
    expect(parseStorage('128gb')).toBe('128GB');
    expect(parseStorage('1tb')).toBe('1TB');
  });

  it('should return null for invalid input', () => {
    expect(parseStorage(null)).toBeNull();
    expect(parseStorage('')).toBeNull();
    expect(parseStorage('invalid')).toBeNull();
  });
});

describe('normalizeCarrier', () => {
  it('should normalize SKT variants', () => {
    expect(normalizeCarrier('SKT')).toBe('SKT');
    expect(normalizeCarrier('SK텔레콤')).toBe('SKT');
    expect(normalizeCarrier('에스케이')).toBe('SKT');
  });

  it('should normalize KT variants', () => {
    expect(normalizeCarrier('KT')).toBe('KT');
    expect(normalizeCarrier('케이티')).toBe('KT');
  });

  it('should normalize LGU+ variants', () => {
    expect(normalizeCarrier('LGU+')).toBe('LGU+');
    expect(normalizeCarrier('LG유플러스')).toBe('LGU+');
    expect(normalizeCarrier('유플러스')).toBe('LGU+');
  });
});

describe('PolicySchema', () => {
  it('should parse valid policy with Python-compatible format', () => {
    const policy = PolicySchema.parse({
      policy_id: 'abc123def4567890',
      carrier: '1', // SKT carrier code
      mno_join_type: '번호이동',
      discount_type: '공시지원금',
      mobile_plan: {
        name: '5G 프리미어',
        monthly_fee: 89000,
      },
      pricing: {
        mno_retail_price: 1500000,
        public_subsidy: 300000,
        discount: 50000,
        sku_installment_fee: 1150000,
        monthly_payment: 47916,
      },
    });

    expect(policy.carrier).toBe('1');
    expect(policy.mno_join_type).toBe('번호이동');
    expect(policy.mobile_plan.name).toBe('5G 프리미어');
    expect(policy.mobile_plan.monthly_fee).toBe(89000);
    expect(policy.pricing.mno_retail_price).toBe(1500000);
    expect(policy.pricing.public_subsidy).toBe(300000);
  });
});
