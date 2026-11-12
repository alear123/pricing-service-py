from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class CouponUsageCreate(BaseModel):
    couponCode: str

class CouponUsageInDB(BaseModel):
    id: str = Field(..., alias="_id")
    couponId: str
    cartId: str
    usedOn: datetime

    model_config = ConfigDict(populate_by_name=True)