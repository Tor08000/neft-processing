from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, new_uuid_str


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class PartnerLegalType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    IP = "IP"
    LEGAL_ENTITY = "LEGAL_ENTITY"


class PartnerTaxRegime(str, Enum):
    USN = "USN"
    OSNO = "OSNO"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    FOREIGN = "FOREIGN"
    OTHER = "OTHER"


class PartnerLegalStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class PartnerLegalProfile(Base):
    __tablename__ = "partner_legal_profiles"

    partner_id = Column(String(64), primary_key=True)
    legal_type = Column(ExistingEnum(PartnerLegalType, name="partner_legal_type"), nullable=False)
    country = Column(String(2), nullable=True)
    tax_residency = Column(String(2), nullable=True)
    tax_regime = Column(ExistingEnum(PartnerTaxRegime, name="partner_tax_regime"), nullable=True)
    vat_applicable = Column(Boolean, nullable=False, server_default="false")
    vat_rate = Column(Numeric(5, 2), nullable=True)
    legal_status = Column(
        ExistingEnum(PartnerLegalStatus, name="partner_legal_status"),
        nullable=False,
        server_default=PartnerLegalStatus.DRAFT.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerLegalDetails(Base):
    __tablename__ = "partner_legal_details"

    partner_id = Column(String(64), primary_key=True)
    legal_name = Column(String(255), nullable=True)
    inn = Column(String(32), nullable=True)
    kpp = Column(String(32), nullable=True)
    ogrn = Column(String(32), nullable=True)
    passport = Column(String(128), nullable=True)
    bank_account = Column(String(64), nullable=True)
    bank_bic = Column(String(32), nullable=True)
    bank_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerTaxPolicy(Base):
    __tablename__ = "partner_tax_policies"
    __table_args__ = (UniqueConstraint("legal_type", "tax_regime", name="uq_partner_tax_policy"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    legal_type = Column(ExistingEnum(PartnerLegalType, name="partner_legal_type"), nullable=False)
    tax_regime = Column(ExistingEnum(PartnerTaxRegime, name="partner_tax_regime"), nullable=False)
    income_tax_rate = Column(Numeric(5, 2), nullable=True)
    vat_rate = Column(Numeric(5, 2), nullable=True)
    withholding_required = Column(Boolean, nullable=False, server_default="false")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerLegalPack(Base):
    __tablename__ = "partner_legal_packs"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    partner_id = Column(String(64), nullable=False, index=True)
    format = Column(String(8), nullable=False)
    object_key = Column(Text, nullable=False)
    pack_hash = Column(String(64), nullable=False)
    metadata_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "PartnerLegalDetails",
    "PartnerLegalPack",
    "PartnerLegalProfile",
    "PartnerLegalStatus",
    "PartnerLegalType",
    "PartnerTaxPolicy",
    "PartnerTaxRegime",
]
