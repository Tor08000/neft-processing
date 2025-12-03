from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class MerchantBase(BaseModel):
    name: str
    status: str = "ACTIVE"


class MerchantCreate(MerchantBase):
    id: str


class MerchantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


class MerchantSchema(MerchantBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class MerchantsPage(BaseModel):
    items: List[MerchantSchema]
    total: int
    limit: int
    offset: int
