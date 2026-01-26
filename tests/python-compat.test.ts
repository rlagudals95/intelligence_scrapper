/**
 * Python 호환성 테스트
 * TypeScript 출력이 Python 출력과 동일한 형식인지 검증
 */
import { describe, it, expect } from 'vitest';
import {
  generateProductId,
  generatePolicyId,
  parseStorage,
  parsePrice,
  carrierToCode,
  codeToCarrier,
  createPolicy,
  createProduct,
  PolicySchema,
  ProductSchema,
  ScrapingResultSchema,
  type Policy,
  type Product,
} from '../src/models/phase3-schemas.js';

describe('Python Compatibility: ID Generation', () => {
  it('should generate product_id matching Python format', () => {
    // MD5 해시, 16자
    const productId = generateProductId('갤럭시 S25 - 하이폰', '256GB');

    expect(productId).toHaveLength(16);
    expect(productId).toMatch(/^[a-f0-9]{16}$/);
  });

  it('should generate policy_id matching Python format', () => {
    const policyId = generatePolicyId('1', '기기변경', '256GB', '5G 프리미어 슈퍼');

    expect(policyId).toHaveLength(16);
    expect(policyId).toMatch(/^[a-f0-9]{16}$/);
  });

  it('should generate consistent IDs for same input', () => {
    const id1 = generateProductId('갤럭시 S25', '256GB');
    const id2 = generateProductId('갤럭시 S25', '256GB');

    expect(id1).toBe(id2);
  });

  it('should generate different IDs for different storage', () => {
    const id256 = generateProductId('갤럭시 S25', '256GB');
    const id512 = generateProductId('갤럭시 S25', '512GB');

    expect(id256).not.toBe(id512);
  });
});

describe('Python Compatibility: Carrier Codes', () => {
  it('should convert carrier names to codes', () => {
    expect(carrierToCode('SKT')).toBe('1');
    expect(carrierToCode('KT')).toBe('2');
    expect(carrierToCode('LGU+')).toBe('3');
  });

  it('should convert codes back to carrier names', () => {
    expect(codeToCarrier('1')).toBe('SKT');
    expect(codeToCarrier('2')).toBe('KT');
    expect(codeToCarrier('3')).toBe('LGU+');
  });

  it('should handle Korean carrier names', () => {
    expect(carrierToCode('SK텔레콤')).toBe('1');
    expect(carrierToCode('케이티')).toBe('2');
    expect(carrierToCode('LG유플러스')).toBe('3');
  });
});

describe('Python Compatibility: Storage Parsing', () => {
  it('should parse storage strings', () => {
    expect(parseStorage('256GB')).toBe('256GB');
    expect(parseStorage('256G')).toBe('256GB');
    expect(parseStorage('256')).toBe('256GB');
    expect(parseStorage('256 GB')).toBe('256GB');
  });

  it('should parse TB storage', () => {
    expect(parseStorage('1TB')).toBe('1TB');
    expect(parseStorage('1T')).toBe('1TB');
    expect(parseStorage('2TB')).toBe('2TB');
  });

  it('should return null for invalid storage', () => {
    expect(parseStorage('')).toBeNull();
    expect(parseStorage(null)).toBeNull();
    expect(parseStorage(undefined)).toBeNull();
  });
});

describe('Python Compatibility: Price Parsing', () => {
  it('should parse price strings', () => {
    expect(parsePrice('1,155,000')).toBe(1155000);
    expect(parsePrice('1155000')).toBe(1155000);
    expect(parsePrice('1,155,000원')).toBe(1155000);
  });

  it('should handle negative prices (discounts)', () => {
    expect(parsePrice('-550,000')).toBe(-550000);
  });

  it('should return null for empty', () => {
    expect(parsePrice(null)).toBeNull();
    expect(parsePrice(undefined)).toBeNull();
  });

  it('should pass through numbers', () => {
    expect(parsePrice(1155000)).toBe(1155000);
  });
});

describe('Python Compatibility: Schema Structure', () => {
  it('should create policy with snake_case fields', () => {
    const policy = createPolicy({
      carrier: 'SKT',
      joinType: '기기변경',
      storage: '256GB',
      plan: { name: '5G 프리미어 슈퍼', monthly_fee: 115000 },
      discountType: '공시지원금',
      pricing: {
        mno_retail_price: 1155000,
        public_subsidy: 480000,
        discount: 650000,
        sku_installment_fee: 25000,
        monthly_payment: null,
      },
    });

    // Validate snake_case field names (Python 호환)
    expect(policy).toHaveProperty('policy_id');
    expect(policy).toHaveProperty('mno_join_type');
    expect(policy).toHaveProperty('mobile_plan');
    expect(policy).toHaveProperty('discount_type');
    expect(policy).toHaveProperty('policy_text');

    // Carrier should be code
    expect(policy.carrier).toBe('1');

    // Nested snake_case
    expect(policy.mobile_plan).toHaveProperty('monthly_fee');
    expect(policy.pricing).toHaveProperty('mno_retail_price');
    expect(policy.pricing).toHaveProperty('public_subsidy');
    expect(policy.pricing).toHaveProperty('sku_installment_fee');
  });

  it('should create product with snake_case fields', () => {
    const product = createProduct({
      skuCode: '갤럭시 S25 - 하이폰',
      storage: '256GB',
      policies: [],
      productName: '갤럭시 S25',
    });

    expect(product).toHaveProperty('product_id');
    expect(product).toHaveProperty('sku_code');
    expect(product).toHaveProperty('sku_storage');
    expect(product).toHaveProperty('product_name');
    expect(product).toHaveProperty('product_color');
  });

  it('should validate policy with Zod schema', () => {
    const policyData = {
      policy_id: '52ae44f34c7dfa8e',
      carrier: '1',
      mno_join_type: '기기변경' as const,
      mobile_plan: {
        name: '5G 프리미어 슈퍼',
        monthly_fee: 115000,
      },
      discount_type: '공시지원금' as const,
      pricing: {
        mno_retail_price: 1155000,
        public_subsidy: 480000,
        discount: 650000,
        sku_installment_fee: 25000,
        monthly_payment: null,
      },
      addons: [],
      policy_text: null,
    };

    const result = PolicySchema.safeParse(policyData);
    expect(result.success).toBe(true);
  });

  it('should validate product with Zod schema', () => {
    const productData = {
      product_id: '72f9e864f1435245',
      sku_code: '갤럭시 S25 - 하이폰',
      sku_storage: '256GB' as const,
      policies: [],
      product_name: '갤럭시 S25',
      product_color: null,
    };

    const result = ProductSchema.safeParse(productData);
    expect(result.success).toBe(true);
  });
});

describe('Python Compatibility: Parse Python Output', () => {
  // Python 실제 출력 형식 테스트
  const pythonOutput = {
    site_name: '하이폰_삼성',
    list_url: 'https://hi-phone.kr/index.php?channel=list&cate=103001000000',
    target_models: ['갤럭시S25'],
    scraped_at: '2026-01-06T21:22:01.775920',
    total_duration: 351.1169910430908,
    results: [
      {
        product_name: '갤럭시 S25',
        url: 'https://hi-phone.kr/index.php?channel=view&cate=103001000000&uid=10337',
        policy_count: 24,
        duration: 98.2957010269165,
        products: [
          {
            product_id: '72f9e864f1435245',
            sku_code: '갤럭시 S25 - 하이폰',
            sku_storage: '256GB',
            policies: [
              {
                policy_id: '52ae44f34c7dfa8e',
                carrier: '1',
                mno_join_type: '기기변경',
                mobile_plan: {
                  name: '5G 프리미어 슈퍼',
                  monthly_fee: 115000,
                },
                discount_type: '공시지원금',
                pricing: {
                  mno_retail_price: 1155000,
                  public_subsidy: 480000,
                  discount: 650000,
                  sku_installment_fee: 25000,
                  monthly_payment: null,
                },
                addons: [],
                policy_text: null,
              },
            ],
            product_name: null,
            product_color: null,
          },
        ],
      },
    ],
  };

  it('should validate Python output with TypeScript schema', () => {
    const result = ScrapingResultSchema.safeParse(pythonOutput);

    if (!result.success) {
      console.error('Validation errors:', result.error.errors);
    }

    expect(result.success).toBe(true);
  });

  it('should access all fields correctly', () => {
    const result = ScrapingResultSchema.parse(pythonOutput);

    expect(result.site_name).toBe('하이폰_삼성');
    expect(result.results[0].product_name).toBe('갤럭시 S25');
    expect(result.results[0].products[0].sku_storage).toBe('256GB');
    expect(result.results[0].products[0].policies[0].carrier).toBe('1');
    expect(result.results[0].products[0].policies[0].pricing.mno_retail_price).toBe(1155000);
  });
});

describe('Python Compatibility: Output JSON Format', () => {
  it('should produce JSON matching Python output structure', () => {
    const policy = createPolicy({
      carrier: 'SKT',
      joinType: '기기변경',
      storage: '256GB',
      plan: { name: '5G 프리미어 슈퍼', monthly_fee: 115000 },
      discountType: '공시지원금',
      pricing: {
        mno_retail_price: 1155000,
        public_subsidy: 480000,
        discount: 650000,
        sku_installment_fee: 25000,
        monthly_payment: null,
      },
    });

    const product = createProduct({
      skuCode: '갤럭시 S25 - 하이폰',
      storage: '256GB',
      policies: [policy],
    });

    const json = JSON.stringify(product, null, 2);

    // Python 출력과 동일한 키 확인
    expect(json).toContain('"product_id"');
    expect(json).toContain('"sku_code"');
    expect(json).toContain('"sku_storage"');
    expect(json).toContain('"policy_id"');
    expect(json).toContain('"mno_join_type"');
    expect(json).toContain('"mobile_plan"');
    expect(json).toContain('"monthly_fee"');
    expect(json).toContain('"discount_type"');
    expect(json).toContain('"mno_retail_price"');
    expect(json).toContain('"public_subsidy"');
    expect(json).toContain('"sku_installment_fee"');

    // camelCase가 없어야 함
    expect(json).not.toContain('"monthlyFee"');
    expect(json).not.toContain('"joinType"');
    expect(json).not.toContain('"retailPrice"');
  });
});
