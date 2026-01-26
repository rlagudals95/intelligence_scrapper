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
    expect(parsePrice(null)).toBe(0);
    expect(parsePrice(undefined)).toBe(0);
    expect(parsePrice('')).toBe(0);
  });

  it('should handle number input', () => {
    expect(parsePrice(1500000)).toBe(1500000);
  });
});

describe('parseStorage', () => {
  it('should parse storage strings', () => {
    expect(parseStorage('128GB')).toBe('STORAGE_128GB');
    expect(parseStorage('256GB')).toBe('STORAGE_256GB');
    expect(parseStorage('512GB')).toBe('STORAGE_512GB');
    expect(parseStorage('1TB')).toBe('STORAGE_1TB');
  });

  it('should handle case insensitivity', () => {
    expect(parseStorage('128gb')).toBe('STORAGE_128GB');
    expect(parseStorage('1tb')).toBe('STORAGE_1TB');
  });

  it('should return undefined for invalid input', () => {
    expect(parseStorage(null)).toBeUndefined();
    expect(parseStorage('')).toBeUndefined();
    expect(parseStorage('invalid')).toBeUndefined();
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
  it('should parse valid policy', () => {
    const policy = PolicySchema.parse({
      carrier: 'SKT',
      joinType: '번호이동',
      discountType: '공시지원금',
      plan: {
        name: '5G 프리미어',
        monthlyFee: 89000,
      },
      pricing: {
        retailPrice: 1500000,
        finalPrice: 1000000,
      },
      hash: 'abc123',
    });

    expect(policy.carrier).toBe('SKT');
    expect(policy.joinType).toBe('번호이동');
    expect(policy.plan.name).toBe('5G 프리미어');
  });
});
