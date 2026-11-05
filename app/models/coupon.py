from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"

class CouponBase(BaseModel):
    couponCode: str
    usageLimit: int
    discountType: DiscountType
    discountValue: float
    startDate: datetime
    expirationDate: datetime

class CouponCreate(CouponBase):
    pass

class CouponUpdate(BaseModel):
    usageLimit: Optional[int] = None
    expirationDate: Optional[datetime] = None
    discountType: Optional[DiscountType] = None
    discountValue: Optional[float] = None

class CouponInDB(CouponBase):
    id: str = Field(..., alias="_id")
    creationDate: datetime

    class Config:
        populate_by_name = True