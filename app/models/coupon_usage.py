from datetime import datetime
from pydantic import BaseModel, Field

class CouponUsageCreate(BaseModel):
    couponCode: str

class CouponUsageInDB(BaseModel):
    id: str = Field(..., alias="_id")
    couponId: str
    cartId: str
    usedOn: datetime

    class Config:
        populate_by_name = True