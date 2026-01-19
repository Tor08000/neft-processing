from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PartnerLegalProfileStatusUpdate(BaseModel):
    status: str
    comment: str | None = None


class PartnerLegalPackRequest(BaseModel):
    format: str = "ZIP"


class PartnerLegalPackOut(BaseModel):
    id: str
    partner_id: str
    format: str
    object_key: str
    pack_hash: str
    metadata: dict | None = None
    created_at: datetime
    download_url: str | None = None


class PartnerLegalPackHistoryResponse(BaseModel):
    items: list[PartnerLegalPackOut]


class PartnerLegalProfileAdminOut(BaseModel):
    partner_id: str
    legal_type: str | None = None
    country: str | None = None
    tax_residency: str | None = None
    tax_regime: str | None = None
    vat_applicable: bool | None = None
    vat_rate: float | None = None
    legal_status: str | None = None
    details: dict | None = None
    tax_context: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
