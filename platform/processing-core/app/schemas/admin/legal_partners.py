from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LegalPartnerSummary(BaseModel):
    partner_id: str
    partner_name: str | None = None
    legal_status: str | None = None
    payout_blocked: bool | None = None
    updated_at: datetime | None = None


class LegalPartnerListResponse(BaseModel):
    items: list[LegalPartnerSummary]
    total: int
    cursor: str | None = None


class LegalPartnerDocument(BaseModel):
    id: str
    title: str | None = None
    status: str | None = None
    url: str | None = None
    updated_at: datetime | None = None


class LegalPartnerDetail(BaseModel):
    partner_id: str
    partner_name: str | None = None
    legal_status: str | None = None
    payout_blocks: list[str] | None = None
    documents: list[LegalPartnerDocument] | None = None
    profile: dict | None = None
    raw: dict | None = None


class LegalPartnerStatusUpdate(BaseModel):
    status: str
    reason: str = Field(..., min_length=1)
    correlation_id: str | None = None


__all__ = [
    "LegalPartnerDetail",
    "LegalPartnerDocument",
    "LegalPartnerListResponse",
    "LegalPartnerStatusUpdate",
    "LegalPartnerSummary",
]
