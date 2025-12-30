"""
Phase 3: 상세페이지 옵션 정책 수집 스키마
"""
import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class StorageType(str, Enum):
    """저장용량 타입"""
    STORAGE_128GB = "128GB"
    STORAGE_256GB = "256GB"
    STORAGE_512GB = "512GB"
    STORAGE_1TB = "1TB"
    STORAGE_2TB = "2TB"


class JoinType(str, Enum):
    """가입 유형"""
    DEVICE_CHANGE = "기기변경"
    NUMBER_TRANSFER = "번호이동"
    NEW_SUBSCRIPTION = "신규가입"


class DiscountType(str, Enum):
    """할인 방식"""
    PUBLIC_SUBSIDY = "공시지원금"
    CONTRACT_DISCOUNT = "선택약정"


class MobilePlan(BaseModel):
    """요금제 정보"""
    name: str = Field(..., description="요금제 이름")
    monthly_fee: int = Field(..., description="월 요금 (원)")


class PricingDetails(BaseModel):
    """가격 정책 상세"""
    mno_retail_price: Optional[int] = Field(None, description="통신사 출고가 (원)")
    public_subsidy: Optional[int] = Field(None, description="공시지원금 (원)")
    discount: Optional[int] = Field(None, description="추가지원금 (원)")
    sku_installment_fee: Optional[int] = Field(None, description="할부원금 (원)")
    monthly_payment: Optional[int] = Field(None, description="월 할부금 (원)")


class Addon(BaseModel):
    """부가 서비스/보험"""
    name: str = Field(..., description="서비스 이름")
    price: int = Field(..., description="월 가격 (원)")
    keep_months: Optional[int] = Field(None, description="유지 개월 수")


class Policy(BaseModel):
    """정책 (하나의 옵션 조합)"""
    policy_id: str = Field(..., description="정책 고유 ID (해시)")
    carrier: str = Field(..., description="통신사 (SKT, KT, LGU+)")
    mno_join_type: JoinType = Field(..., description="가입 유형")
    mobile_plan: MobilePlan = Field(..., description="모바일 요금제")
    discount_type: DiscountType = Field(..., description="할인 방식")
    pricing: PricingDetails = Field(..., description="가격 정책")
    addons: List[Addon] = Field(default_factory=list, description="부가 서비스")
    policy_text: Optional[str] = Field(None, description="정책 원문")


class Product(BaseModel):
    """제품 (하나의 SKU)"""
    product_id: str = Field(..., description="상품 고유 ID (해시)")
    sku_code: str = Field(..., description="상품 SKU 코드 (예: 갤럭시 S25)")
    sku_storage: Optional[StorageType] = Field(None, description="저장 용량")
    policies: List[Policy] = Field(default_factory=list, description="정책 목록")
    product_name: Optional[str] = Field(None, description="상품명")
    product_color: Optional[str] = Field(None, description="색상")


class SourceInfo(BaseModel):
    """데이터 출처"""
    site: str = Field(..., description="사이트 이름")
    url: str = Field(..., description="URL")


class ScrapingResult(BaseModel):
    """최종 스크래핑 결과"""
    captured_at: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        description="캡처 시각"
    )
    source: SourceInfo = Field(..., description="출처 정보")
    products: List[Product] = Field(default_factory=list, description="수집된 상품")


# 유틸리티 함수
def parse_price(price_str: Optional[str]) -> Optional[int]:
    """가격 문자열을 정수로 변환"""
    if not price_str:
        return None
    try:
        return int("".join(filter(str.isdigit, price_str)))
    except ValueError:
        return None


def parse_storage(storage_str: Optional[str]) -> Optional[StorageType]:
    """저장 용량 문자열을 Enum으로 변환"""
    if not storage_str:
        return None
    
    storage_map = {
        "128GB": StorageType.STORAGE_128GB,
        "256GB": StorageType.STORAGE_256GB,
        "512GB": StorageType.STORAGE_512GB,
        "1TB": StorageType.STORAGE_1TB,
        "2TB": StorageType.STORAGE_2TB,
    }
    
    return storage_map.get(storage_str.upper())

