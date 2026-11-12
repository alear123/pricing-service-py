from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class MovType(str, Enum):
    SET = "SET"
    INCR = "INCR"
    DECR = "DECR"

class MovPricingCreate(BaseModel):
    pricingId: str
    movType: MovType
    value: float
    description: Optional[str] = None
    userLogin: Optional[str] = None

class MovPricingInDB(MovPricingCreate):
    id: str = Field(..., alias="_id")
    creationDate: datetime

    model_config = ConfigDict(populate_by_name=True)