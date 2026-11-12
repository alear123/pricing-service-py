from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PricingBase(BaseModel):
    articleId: str
    price: float

class PricingCreate(PricingBase):
    pass

class PricingInDB(PricingBase):
    id: str = Field(..., alias="_id")
    creationDate: datetime
    updateDate: datetime

    model_config = ConfigDict(populate_by_name=True)