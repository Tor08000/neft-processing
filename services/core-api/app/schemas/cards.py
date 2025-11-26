from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CardBase(BaseModel):
    client_id: str
    status: str = "ACTIVE"
    pan_masked: Optional[str] = None
    expires_at: Optional[str] = None


class CardCreate(CardBase):
    id: str


class CardUpdate(BaseModel):
    client_id: Optional[str] = None
    status: Optional[str] = None
    pan_masked: Optional[str] = None
    expires_at: Optional[str] = None


class CardSchema(CardBase):
    id: str

    class Config:
        from_attributes = True


class CardsPage(BaseModel):
    items: List[CardSchema]
    total: int
    limit: int
    offset: int
