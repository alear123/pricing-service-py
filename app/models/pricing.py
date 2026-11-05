from datetime import datetime
from pydantic import BaseModel, Field

class PricingBase(BaseModel):
    articleId: str
    price: float

class PricingCreate(PricingBase):
    pass

class PricingInDB(PricingBase):
    id: str = Field(..., alias="_id")
    creationDate: datetime
    updateDate: datetime

    class Config:
        populate_by_name = True