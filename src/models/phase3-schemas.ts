import { z } from 'zod';
import { createHash } from 'crypto';

// ============================================================================
// Enums (Python 호환)
// ============================================================================

export const StorageTypeEnum = z.enum(['128GB', '256GB', '512GB', '1TB', '2TB']);
export type StorageType = z.infer<typeof StorageTypeEnum>;

// MNO 가입유형 Enum (ALL, DEVICE_CHANGE, NUMBER_TRANSFER)
export const JoinTypeEnum = z.enum(['ALL', 'DEVICE_CHANGE', 'NUMBER_TRANSFER']);
export type JoinType = z.infer<typeof JoinTypeEnum>;

// 할인유형 Enum (PUBLIC_SUBSIDY: 공시지원금, CONTRACT_DISCOUNT: 선택약정)
export const DiscountTypeEnum = z.enum(['PUBLIC_SUBSIDY', 'CONTRACT_DISCOUNT']);
export type DiscountType = z.infer<typeof DiscountTypeEnum>;

// 통신사 Enum (SKT, KT, LGU, MVNO)
export const CarrierEnum = z.enum(['SKT', 'KT', 'LGU', 'MVNO']);
export type Carrier = z.infer<typeof CarrierEnum>;

// SKU Code Enum (제품 모델 식별자)
export const SkuCodeEnum = z.enum([
  // Galaxy Z Flip
  'GALAXY_Z_FLIP7',
  'GALAXY_Z_FLIP6',
  'GALAXY_Z_FLIP5',
  'GALAXY_Z_FLIP4',
  'GALAXY_Z_FLIP3',
  // Galaxy Z Fold
  'GALAXY_Z_FOLD7',
  'GALAXY_Z_FOLD6',
  'GALAXY_Z_FOLD5',
  'GALAXY_Z_FOLD4',
  'GALAXY_Z_FOLD3',
  // Galaxy S Ultra
  'GALAXY_S25_EDGE',
  'GALAXY_S25_ULTRA',
  'GALAXY_S24_ULTRA',
  'GALAXY_S23_ULTRA',
  'GALAXY_S22_ULTRA',
  'GALAXY_S21_ULTRA',
  // Galaxy S Plus
  'GALAXY_S25_PLUS',
  'GALAXY_S24_PLUS',
  'GALAXY_S23_PLUS',
  'GALAXY_S22_PLUS',
  'GALAXY_S21_PLUS',
  // Galaxy S
  'GALAXY_S25',
  'GALAXY_S24',
  'GALAXY_S23',
  'GALAXY_S22',
  'GALAXY_S21',
  // Galaxy S FE
  'GALAXY_S24_FE',
  'GALAXY_S23_FE',
  'GALAXY_S22_FE',
  'GALAXY_S21_FE',
  // Galaxy A / Budget
  'GALAXY_A35',
  'GALAXY_A25',
  'GALAXY_A24',
  'GALAXY_JUMP3',
  'GALAXY_BUDDY3',
  'GALAXY_A16',
  'GALAXY_WIDE7',
  // iPhone Pro Max
  'IPHONE17_PRO_MAX',
  'IPHONE16_PRO_MAX',
  'IPHONE15_PRO_MAX',
  'IPHONE14_PRO_MAX',
  'IPHONE13_PRO_MAX',
  // iPhone Pro
  'IPHONE17_PRO',
  'IPHONE16_PRO',
  'IPHONE15_PRO',
  'IPHONE14_PRO',
  'IPHONE13_PRO',
  // iPhone Air / Plus
  'IPHONE_AIR',
  'IPHONE16_PLUS',
  'IPHONE15_PLUS',
  'IPHONE14_PLUS',
  'IPHONE13_PLUS',
  // iPhone Standard
  'IPHONE17',
  'IPHONE16',
  'IPHONE15',
  'IPHONE14',
  'IPHONE13',
  'IPHONE13_MINI',
  // iPhone SE / E
  'IPHONE_SE_4TH',
  'IPHONE_SE_3RD',
  'IPHONE16E',
  // Default
  'NOT_SET',
]);
export type SkuCode = z.infer<typeof SkuCodeEnum>;

// ============================================================================
// Core Schemas (camelCase)
// ============================================================================

export const MobilePlanSchema = z.object({
  name: z.string(),
  monthlyFee: z.number(),
});
export type MobilePlan = z.infer<typeof MobilePlanSchema>;

export const PricingDetailsSchema = z.object({
  mnoRetailPrice: z.number().nullable().optional(),
  publicSubsidy: z.number().nullable().optional(),
  discount: z.number().nullable().optional(), // 추가지원금
  skuInstallmentFee: z.number().nullable().optional(), // 할부원금
  monthlyPayment: z.number().nullable().optional(),
});
export type PricingDetails = z.infer<typeof PricingDetailsSchema>;

export const AddonSchema = z.object({
  name: z.string(),
  price: z.number(),
  keepMonths: z.number().nullable().optional(),
});
export type Addon = z.infer<typeof AddonSchema>;

export const PolicySchema = z.object({
  policyId: z.string(),
  networkOperator: CarrierEnum, // SKT, KT, LGU, MVNO (to-be 통신사)
  currentNetworkOperator: CarrierEnum.nullable().optional(), // 패턴 B: 현재 통신사 (optional)
  mnoJoinType: JoinTypeEnum,
  mobilePlan: MobilePlanSchema,
  discountType: DiscountTypeEnum,
  pricing: PricingDetailsSchema,
  addons: z.array(AddonSchema).default([]),
  policyText: z.string().nullable().optional(),
});
export type Policy = z.infer<typeof PolicySchema>;

export const ProductSchema = z.object({
  productId: z.string(),
  skuCode: SkuCodeEnum,
  skuStorage: StorageTypeEnum.nullable().optional(),
  policies: z.array(PolicySchema).default([]),
  productName: z.string().nullable().optional(),
  productColor: z.string().nullable().optional(),
});
export type Product = z.infer<typeof ProductSchema>;

// ============================================================================
// Result Schemas
// ============================================================================

// 개별 상품 결과 (상세 페이지 단위)
export const ProductResultSchema = z.object({
  productName: z.string(),
  url: z.string(),
  policyCount: z.number(),
  duration: z.number(),
  products: z.array(ProductSchema),
});
export type ProductResult = z.infer<typeof ProductResultSchema>;

// 최종 스크래핑 결과
export const ScrapingResultSchema = z.object({
  siteName: z.string(),
  listUrl: z.string(),
  targetModels: z.array(z.string()),
  scrapedAt: z.string(),
  totalDuration: z.number(),
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

export function normalizeCarrier(carrier: string): Carrier {
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
    return 'LGU';
  if (
    normalized.includes('MVNO') ||
    normalized.includes('알뜰') ||
    normalized.includes('알뜰폰')
  )
    return 'MVNO';

  // 기본값: SKT (유효하지 않은 입력 처리)
  return 'SKT';
}

/**
 * 할인유형을 DiscountType enum 값으로 변환
 * 한글/영문 모두 지원
 */
export function normalizeDiscountType(discountType: string): DiscountType {
  const normalized = discountType.toUpperCase().replace(/\s/g, '');

  // 선택약정 / CONTRACT_DISCOUNT
  if (
    normalized.includes('선택약정') ||
    normalized.includes('약정') ||
    normalized.includes('CONTRACT') ||
    normalized.includes('CONTRACTDISCOUNT') ||
    normalized.includes('CONTRACT_DISCOUNT')
  ) {
    return 'CONTRACT_DISCOUNT';
  }

  // 공시지원금 / PUBLIC_SUBSIDY (기본값)
  return 'PUBLIC_SUBSIDY';
}

/**
 * 가입유형을 JoinType enum 값으로 변환
 * 한글/영문 모두 지원
 */
export function normalizeJoinType(joinType: string): JoinType {
  const normalized = joinType.toUpperCase().replace(/\s/g, '');

  // 번호이동 / NUMBER_TRANSFER
  if (
    normalized.includes('번호이동') ||
    normalized.includes('NUMBERTRANSFER') ||
    normalized.includes('NUMBER_TRANSFER') ||
    normalized.includes('MNP')
  ) {
    return 'NUMBER_TRANSFER';
  }

  // 기기변경 / DEVICE_CHANGE
  if (
    normalized.includes('기기변경') ||
    normalized.includes('기변') ||
    normalized.includes('DEVICECHANGE') ||
    normalized.includes('DEVICE_CHANGE')
  ) {
    return 'DEVICE_CHANGE';
  }

  // ALL (전체 / 모든 유형)
  if (
    normalized.includes('ALL') ||
    normalized.includes('전체') ||
    normalized.includes('모두')
  ) {
    return 'ALL';
  }

  // 기본값: DEVICE_CHANGE
  return 'DEVICE_CHANGE';
}

/**
 * 제품명을 SkuCode enum 값으로 변환
 * 다양한 사이트의 제품명 형식을 처리
 */
export function normalizeSkuCode(productName: string): SkuCode {
  // 정규화: 공백 제거, 대문자 변환, 특수문자 처리
  const normalized = productName
    .toUpperCase()
    .replace(/[^A-Z0-9가-힣]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  // Galaxy Z Flip 시리즈 (먼저 체크 - 더 구체적인 패턴)
  if (/Z\s*FLIP\s*7|플립\s*7/i.test(normalized)) return 'GALAXY_Z_FLIP7';
  if (/Z\s*FLIP\s*6|플립\s*6/i.test(normalized)) return 'GALAXY_Z_FLIP6';
  if (/Z\s*FLIP\s*5|플립\s*5/i.test(normalized)) return 'GALAXY_Z_FLIP5';
  if (/Z\s*FLIP\s*4|플립\s*4/i.test(normalized)) return 'GALAXY_Z_FLIP4';
  if (/Z\s*FLIP\s*3|플립\s*3/i.test(normalized)) return 'GALAXY_Z_FLIP3';

  // Galaxy Z Fold 시리즈
  if (/Z\s*FOLD\s*7|폴드\s*7/i.test(normalized)) return 'GALAXY_Z_FOLD7';
  if (/Z\s*FOLD\s*6|폴드\s*6/i.test(normalized)) return 'GALAXY_Z_FOLD6';
  if (/Z\s*FOLD\s*5|폴드\s*5/i.test(normalized)) return 'GALAXY_Z_FOLD5';
  if (/Z\s*FOLD\s*4|폴드\s*4/i.test(normalized)) return 'GALAXY_Z_FOLD4';
  if (/Z\s*FOLD\s*3|폴드\s*3/i.test(normalized)) return 'GALAXY_Z_FOLD3';

  // Galaxy S Edge (S25 Edge)
  if (/S\s*25\s*EDGE|S25\s*엣지/i.test(normalized)) return 'GALAXY_S25_EDGE';

  // Galaxy S Ultra 시리즈 (Edge보다 뒤에)
  if (/S\s*25\s*ULTRA|S25\s*울트라/i.test(normalized)) return 'GALAXY_S25_ULTRA';
  if (/S\s*24\s*ULTRA|S24\s*울트라/i.test(normalized)) return 'GALAXY_S24_ULTRA';
  if (/S\s*23\s*ULTRA|S23\s*울트라/i.test(normalized)) return 'GALAXY_S23_ULTRA';
  if (/S\s*22\s*ULTRA|S22\s*울트라/i.test(normalized)) return 'GALAXY_S22_ULTRA';
  if (/S\s*21\s*ULTRA|S21\s*울트라/i.test(normalized)) return 'GALAXY_S21_ULTRA';

  // Galaxy S Plus 시리즈
  if (/S\s*25\s*PLUS|S25\s*플러스|S25\s*\+/i.test(normalized)) return 'GALAXY_S25_PLUS';
  if (/S\s*24\s*PLUS|S24\s*플러스|S24\s*\+/i.test(normalized)) return 'GALAXY_S24_PLUS';
  if (/S\s*23\s*PLUS|S23\s*플러스|S23\s*\+/i.test(normalized)) return 'GALAXY_S23_PLUS';
  if (/S\s*22\s*PLUS|S22\s*플러스|S22\s*\+/i.test(normalized)) return 'GALAXY_S22_PLUS';
  if (/S\s*21\s*PLUS|S21\s*플러스|S21\s*\+/i.test(normalized)) return 'GALAXY_S21_PLUS';

  // Galaxy S FE 시리즈 (일반 S보다 먼저)
  if (/S\s*24\s*FE/i.test(normalized)) return 'GALAXY_S24_FE';
  if (/S\s*23\s*FE/i.test(normalized)) return 'GALAXY_S23_FE';
  if (/S\s*22\s*FE/i.test(normalized)) return 'GALAXY_S22_FE';
  if (/S\s*21\s*FE/i.test(normalized)) return 'GALAXY_S21_FE';

  // Galaxy S 시리즈 (기본 모델 - 가장 마지막에 체크)
  if (/갤럭시\s*S\s*25(?!\s*(?:ULTRA|PLUS|EDGE|\+|울트라|플러스|엣지))|GALAXY\s*S\s*25(?!\s*(?:ULTRA|PLUS|EDGE|\+))/i.test(normalized)) return 'GALAXY_S25';
  if (/갤럭시\s*S\s*24(?!\s*(?:ULTRA|PLUS|FE|\+|울트라|플러스))|GALAXY\s*S\s*24(?!\s*(?:ULTRA|PLUS|FE|\+))/i.test(normalized)) return 'GALAXY_S24';
  if (/갤럭시\s*S\s*23(?!\s*(?:ULTRA|PLUS|FE|\+|울트라|플러스))|GALAXY\s*S\s*23(?!\s*(?:ULTRA|PLUS|FE|\+))/i.test(normalized)) return 'GALAXY_S23';
  if (/갤럭시\s*S\s*22(?!\s*(?:ULTRA|PLUS|FE|\+|울트라|플러스))|GALAXY\s*S\s*22(?!\s*(?:ULTRA|PLUS|FE|\+))/i.test(normalized)) return 'GALAXY_S22';
  if (/갤럭시\s*S\s*21(?!\s*(?:ULTRA|PLUS|FE|\+|울트라|플러스))|GALAXY\s*S\s*21(?!\s*(?:ULTRA|PLUS|FE|\+))/i.test(normalized)) return 'GALAXY_S21';

  // Galaxy A 시리즈
  if (/A\s*35/i.test(normalized)) return 'GALAXY_A35';
  if (/A\s*25/i.test(normalized)) return 'GALAXY_A25';
  if (/A\s*24/i.test(normalized)) return 'GALAXY_A24';
  if (/A\s*16/i.test(normalized)) return 'GALAXY_A16';

  // Galaxy Budget 시리즈
  if (/JUMP\s*3|점프\s*3/i.test(normalized)) return 'GALAXY_JUMP3';
  if (/BUDDY\s*3|버디\s*3/i.test(normalized)) return 'GALAXY_BUDDY3';
  if (/WIDE\s*7|와이드\s*7/i.test(normalized)) return 'GALAXY_WIDE7';

  // iPhone Pro Max 시리즈 (가장 구체적인 것 먼저)
  if (/IPHONE\s*17\s*PRO\s*MAX|아이폰\s*17\s*프로\s*맥스/i.test(normalized)) return 'IPHONE17_PRO_MAX';
  if (/IPHONE\s*16\s*PRO\s*MAX|아이폰\s*16\s*프로\s*맥스/i.test(normalized)) return 'IPHONE16_PRO_MAX';
  if (/IPHONE\s*15\s*PRO\s*MAX|아이폰\s*15\s*프로\s*맥스/i.test(normalized)) return 'IPHONE15_PRO_MAX';
  if (/IPHONE\s*14\s*PRO\s*MAX|아이폰\s*14\s*프로\s*맥스/i.test(normalized)) return 'IPHONE14_PRO_MAX';
  if (/IPHONE\s*13\s*PRO\s*MAX|아이폰\s*13\s*프로\s*맥스/i.test(normalized)) return 'IPHONE13_PRO_MAX';

  // iPhone Pro 시리즈
  if (/IPHONE\s*17\s*PRO|아이폰\s*17\s*프로(?!\s*맥스)/i.test(normalized)) return 'IPHONE17_PRO';
  if (/IPHONE\s*16\s*PRO|아이폰\s*16\s*프로(?!\s*맥스)/i.test(normalized)) return 'IPHONE16_PRO';
  if (/IPHONE\s*15\s*PRO|아이폰\s*15\s*프로(?!\s*맥스)/i.test(normalized)) return 'IPHONE15_PRO';
  if (/IPHONE\s*14\s*PRO|아이폰\s*14\s*프로(?!\s*맥스)/i.test(normalized)) return 'IPHONE14_PRO';
  if (/IPHONE\s*13\s*PRO|아이폰\s*13\s*프로(?!\s*맥스)/i.test(normalized)) return 'IPHONE13_PRO';

  // iPhone Air
  if (/IPHONE\s*AIR|아이폰\s*에어/i.test(normalized)) return 'IPHONE_AIR';

  // iPhone Plus 시리즈
  if (/IPHONE\s*16\s*PLUS|아이폰\s*16\s*플러스/i.test(normalized)) return 'IPHONE16_PLUS';
  if (/IPHONE\s*15\s*PLUS|아이폰\s*15\s*플러스/i.test(normalized)) return 'IPHONE15_PLUS';
  if (/IPHONE\s*14\s*PLUS|아이폰\s*14\s*플러스/i.test(normalized)) return 'IPHONE14_PLUS';
  if (/IPHONE\s*13\s*PLUS|아이폰\s*13\s*플러스/i.test(normalized)) return 'IPHONE13_PLUS';

  // iPhone Mini
  if (/IPHONE\s*13\s*MINI|아이폰\s*13\s*미니/i.test(normalized)) return 'IPHONE13_MINI';

  // iPhone SE
  if (/IPHONE\s*SE\s*4|아이폰\s*SE\s*4|SE\s*4세대/i.test(normalized)) return 'IPHONE_SE_4TH';
  if (/IPHONE\s*SE\s*3|아이폰\s*SE\s*3|SE\s*3세대/i.test(normalized)) return 'IPHONE_SE_3RD';

  // iPhone E (16E)
  if (/IPHONE\s*16\s*E|아이폰\s*16\s*E|16E/i.test(normalized)) return 'IPHONE16E';

  // iPhone 기본 모델 (가장 마지막에)
  if (/IPHONE\s*17(?!\s*(?:PRO|PLUS|\+))|아이폰\s*17(?!\s*(?:프로|플러스))/i.test(normalized)) return 'IPHONE17';
  if (/IPHONE\s*16(?!\s*(?:PRO|PLUS|E|\+))|아이폰\s*16(?!\s*(?:프로|플러스|E))/i.test(normalized)) return 'IPHONE16';
  if (/IPHONE\s*15(?!\s*(?:PRO|PLUS|\+))|아이폰\s*15(?!\s*(?:프로|플러스))/i.test(normalized)) return 'IPHONE15';
  if (/IPHONE\s*14(?!\s*(?:PRO|PLUS|\+))|아이폰\s*14(?!\s*(?:프로|플러스))/i.test(normalized)) return 'IPHONE14';
  if (/IPHONE\s*13(?!\s*(?:PRO|PLUS|MINI|\+))|아이폰\s*13(?!\s*(?:프로|플러스|미니))/i.test(normalized)) return 'IPHONE13';

  // 기본값
  return 'NOT_SET';
}

// ============================================================================
// Builder Functions
// ============================================================================

export function createPolicy(params: {
  networkOperator: string; // to-be 통신사 (이동할 통신사)
  currentNetworkOperator?: string | null; // 패턴 B: 현재 통신사 (optional)
  joinType: JoinType;
  storage: StorageType | null;
  plan: MobilePlan;
  discountType: DiscountType;
  pricing: PricingDetails;
  addons?: Addon[];
  policyText?: string | null;
}): Policy {
  const networkOperatorName = normalizeCarrier(params.networkOperator);
  const currentNetworkOperatorName = params.currentNetworkOperator
    ? normalizeCarrier(params.currentNetworkOperator)
    : null;
  const policyId = generatePolicyId(
    networkOperatorName,
    params.joinType,
    params.storage,
    params.plan.name
  );

  return {
    policyId: policyId,
    networkOperator: networkOperatorName,
    currentNetworkOperator: currentNetworkOperatorName,
    mnoJoinType: params.joinType,
    mobilePlan: params.plan,
    discountType: params.discountType,
    pricing: params.pricing,
    addons: params.addons || [],
    policyText: params.policyText || null,
  };
}

export function createProduct(params: {
  skuCode: SkuCode;
  storage: StorageType | null;
  policies: Policy[];
  productName?: string | null;
  productColor?: string | null;
}): Product {
  const productId = generateProductId(params.skuCode, params.storage);

  return {
    productId: productId,
    skuCode: params.skuCode,
    skuStorage: params.storage,
    policies: params.policies,
    productName: params.productName || null,
    productColor: params.productColor || null,
  };
}
