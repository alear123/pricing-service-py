# app/models/events.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.coupon import DiscountType

class PriceUpdatedEvent(BaseModel):
    eventType: str = "PRICE_UPDATED"
    timestamp: datetime
    articleId: str
    price: float
    discountType: Optional[DiscountType] = None
    discountValue: Optional[float] = None

class CouponCreatedEvent(BaseModel):
    eventType: str = "COUPON_CREATED"
    timestamp: datetime
    couponCode: str
    expirationDate: datetime
    discountType: DiscountType
    discountValue: float

class CouponAppliedEvent(BaseModel):
    eventType: str = "COUPON_APPLIED"
    timestamp: datetime
    couponCode: str
    cartId: str
    discountType: DiscountType
    discountValue: float

class CouponUpdatedEvent(BaseModel):
    eventType: str = "COUPON_UPDATED"
    timestamp: datetime
    couponCode: str
    newExpirationDate: Optional[datetime] = None
    discountType: Optional[DiscountType] = None
    discountValue: Optional[float] = None

class PriceQueriedEvent(BaseModel):
    eventType: str = "PRICE_QUERIED"
    timestamp: datetime
    articleId: str