from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class TerminalBase(BaseModel):
    merchant_id: str
    status: str = "ACTIVE"
    location: Optional[str] = None


class TerminalCreate(TerminalBase):
    id: str


class TerminalUpdate(BaseModel):
    merchant_id: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None


class TerminalSchema(TerminalBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class TerminalsPage(BaseModel):
    items: List[TerminalSchema]
    total: int
    limit: int
    offset: int
