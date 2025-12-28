"""
데이터 스키마 정의 (Pydantic Models)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# 옵션 관련 스키마
# ============================================================================

class PlanOption(BaseModel):
    """요금제 옵션"""
    name: str = Field(..., description="요금제 이름")
    monthly_fee: Optional[str] = Field(None, description="월정액")
    benefits: Optional[str] = Field(None, description="혜택 설명")
    disabled: bool = Field(False, description="비활성 여부")
    disabled_reason: Optional[str] = Field(None, description="비활성 사유")


class Option(BaseModel):
    """일반 옵션 (색상, 용량 등)"""
    value: str = Field(..., description="옵션 값")
    disabled: bool = Field(False, description="비활성 여부")
    disabled_reason: Optional[str] = Field(None, description="비활성 사유")


class OptionsCatalog(BaseModel):
    """옵션 카탈로그 (전수 수집)"""
    carriers: List[str] = Field(default_factory=list, description="통신사 목록 (SKT/KT/LGU+)")
    signup_types: List[str] = Field(default_factory=list, description="가입유형 목록")
    plans: List[PlanOption] = Field(default_factory=list, description="요금제 목록")
    installments: List[str] = Field(default_factory=list, description="할부/약정 기간 목록")
    storages: List[Option] = Field(default_factory=list, description="용량 옵션 목록")
    colors: List[Option] = Field(default_factory=list, description="색상 옵션 목록")
    others: Dict[str, List[Option]] = Field(default_factory=dict, description="기타 옵션")


# ============================================================================
# 가격/정책 스키마
# ============================================================================

class Pricing(BaseModel):
    """가격 정보"""
    final_price: Optional[str] = Field(None, description="최종가")
    installment_principal: Optional[str] = Field(None, description="할부원금")
    monthly_payment: Optional[str] = Field(None, description="월 납부금")
    subsidy_official: Optional[str] = Field(None, description="공시지원금")
    subsidy_additional: Optional[str] = Field(None, description="추가지원금")
    plan_combination: Optional[str] = Field(None, description="요금제 결합 조건")


class SelectedOptions(BaseModel):
    """선택된 옵션 조합"""
    carrier: Optional[str] = Field(None, description="통신사")
    signup_type: Optional[str] = Field(None, description="가입유형")
    plan: Optional[str] = Field(None, description="요금제")
    installment: Optional[str] = Field(None, description="할부/약정")
    storage: Optional[str] = Field(None, description="용량")
    color: Optional[str] = Field(None, description="색상")
    others: Dict[str, str] = Field(default_factory=dict, description="기타 옵션")


class Variant(BaseModel):
    """옵션 조합별 가격/정책 (가지치기 적용)"""
    selected_options: SelectedOptions = Field(..., description="선택된 옵션 조합")
    pricing: Pricing = Field(..., description="가격 정보")
    policy_text: Optional[str] = Field(None, description="정책/면책/주의사항 텍스트")
    scraped_at: datetime = Field(default_factory=datetime.now, description="수집 시각")


# ============================================================================
# 리스팅 스키마 (Phase 2)
# ============================================================================

class PhoneListingItem(BaseModel):
    """리스팅 페이지에서 수집한 휴대폰 정보"""
    model_name: str = Field(..., description="휴대폰 기종명 (예: 갤럭시 S24 Ultra)")
    
    # 통신사 정보
    carrier: Optional[str] = Field(None, description="통신사 (SKT, KT, LGU+ 등)")
    signup_type: Optional[str] = Field(None, description="변경유형 (번호이동, 기기변경, 신규가입 등)")
    
    # 가격 정보
    retail_price: Optional[str] = Field(None, description="출고가")
    discount_price: Optional[str] = Field(None, description="할인가/최종가")
    subsidy_type: Optional[str] = Field(None, description="지원금 타입 (공시지원(공통지원), 선택약정)")
    public_subsidy: Optional[str] = Field(None, description="공시지원금 (공통지원금 + 통신사지원금 합계)")
    additional_subsidy: Optional[str] = Field(None, description="추가지원금 (판매점 제휴할인)")
    
    # 요금제 및 혜택
    plan_name: Optional[str] = Field(None, description="요금제 (리스팅에 표시된 경우)")
    benefits: Optional[str] = Field(None, description="혜택/사은품/프로모션")
    
    # URL 정보
    detail_url: str = Field(..., description="상세 페이지 URL")
    image_url: Optional[str] = Field(None, description="제품 이미지 URL")
    list_url: Optional[str] = Field(None, description="리스팅 페이지 URL (출처)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "갤럭시 S24 Ultra",
                "carrier": "SKT",
                "signup_type": "번호이동",
                "retail_price": "1,698,400",
                "discount_price": "567,000",
                "subsidy_type": "공시지원",
                "public_subsidy": "400,000",
                "additional_subsidy": "100,000",
                "plan_name": "5G 프리미어 에센셜",
                "benefits": "워치 증정",
                "detail_url": "https://example.com/product/12345",
                "image_url": "https://example.com/image.jpg",
                "list_url": "https://example.com/list"
            }
        }


# ============================================================================
# 제품 스키마
# ============================================================================

class Product(BaseModel):
    """단말 정보"""
    detail_url: str = Field(..., description="상세 페이지 URL")
    list_url: Optional[str] = Field(None, description="리스팅 페이지 URL")
    product_name: str = Field(..., description="상품명")
    manufacturer: Optional[str] = Field(None, description="제조사")
    model_code: Optional[str] = Field(None, description="모델코드(SKU)")
    base_price: Optional[str] = Field(None, description="출고가/정가")
    status: Optional[str] = Field(None, description="판매 상태 (재고/품절/사전예약/한정)")
    options_catalog: OptionsCatalog = Field(..., description="옵션 카탈로그 (전수)")
    variants: List[Variant] = Field(default_factory=list, description="가격/정책 조합 (부분 전수)")
    errors: List[str] = Field(default_factory=list, description="에러 목록")


# ============================================================================
# 최종 출력 스키마
# ============================================================================

class Metadata(BaseModel):
    """메타데이터"""
    scraped_at: datetime = Field(default_factory=datetime.now, description="수집 시각")
    total_products: int = Field(0, description="총 제품 수")
    total_variants: int = Field(0, description="총 Variant 수")
    elapsed_seconds: Optional[float] = Field(None, description="소요 시간 (초)")


class ScrapingResult(BaseModel):
    """최종 스크래핑 결과"""
    products: List[Product] = Field(default_factory=list, description="제품 목록")
    metadata: Metadata = Field(default_factory=Metadata, description="메타데이터")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

