
export interface Discount {
  value: number;
  source: string;
}

export interface PolicyLevel {
  discount_max: Discount;
  discount_min: Discount;
  moyo_discount: Discount;
}

export interface MobilePlan {
  name: string;
  monthly_fee: number;
}

export interface Cell {
  cell_key: string;
  carrier: string;
  mno_join_type: 'DEVICE_CHANGE' | 'NUMBER_TRANSFER';
  mobile_plan: MobilePlan;
  policy_level: PolicyLevel;
}

export interface View {
  sku_code: string;
  cells: Cell[];
}

export interface FilterOption {
  value: string;
  label: string;
}

export interface Filters {
  sku_codes: FilterOption[];
  carriers: FilterOption[];
}

export interface DashboardData {
  captured_at: string;
  filters: Filters;
  views: View[];
}

export interface PlanGroup {
    plan: MobilePlan;
    device_change: Cell | null;
    number_transfer: Cell | null;
}

// --- Raw Data Types ---

export interface RawPricing {
  mno_retail_price: number;
  public_subsidy: number;
  discount: number;
  sku_installment_fee: number;
}

export interface RawPolicy {
  carrier: string;
  mno_join_type: 'DEVICE_CHANGE' | 'NUMBER_TRANSFER';
  mobile_plan: MobilePlan;
  pricing: RawPricing;
}

export interface RawProduct {
  product_id: string;
  sku_code: string;
  sku_storage: string;
  policies: RawPolicy[];
}

export interface RawCapture {
  captured_at: string;
  source: {
    site: string;
    url: string;
  };
  products: RawProduct[];
}

export interface FlattenedRow {
  site: string;
  capturedAt: string;
  skuCode: string;
  storage: string;
  carrier: string;
  joinType: string;
  planName: string;
  monthlyFee: string;
  retailPrice: string;
  publicSubsidy: string;
  discount: string;
  installmentFee: string;
}
