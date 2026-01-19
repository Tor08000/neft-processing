from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PartnerLegalProfileIn(BaseModel):
    legal_type: str
    country: str | None = None
    tax_residency: str | None = None
    tax_regime: str | None = None
    vat_applicable: bool = False
    vat_rate: float | None = None


class PartnerLegalDetailsIn(BaseModel):
    legal_name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    passport: str | None = None
    bank_account: str | None = None
    bank_bic: str | None = None
    bank_name: str | None = None


class PartnerLegalDetailsOut(PartnerLegalDetailsIn):
    partner_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PartnerLegalProfileOut(BaseModel):
    partner_id: str
    legal_type: str
    country: str | None = None
    tax_residency: str | None = None
    tax_regime: str | None = None
    vat_applicable: bool
    vat_rate: float | None = None
    legal_status: str
    details: PartnerLegalDetailsOut | None = None
    tax_context: dict | None = None


class PartnerLegalChecklistOut(BaseModel):
    legal_profile: bool
    legal_details: bool
    verified: bool


class PartnerLegalProfileResponse(BaseModel):
    profile: PartnerLegalProfileOut | None
    checklist: PartnerLegalChecklistOut
