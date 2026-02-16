from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, text

from app.db import Base
from app.db.types import GUID, new_uuid_str
from app.models.partner import Partner


class PartnerLocation(Base):
    __tablename__ = "partner_locations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(Text, nullable=True)
    code = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    address = Column(Text, nullable=False)
    city = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    lat = Column(Numeric(), nullable=True)
    lon = Column(Numeric(), nullable=True)
    status = Column(Text, nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("ix_partner_locations_partner_id", "partner_id"),
        Index("ix_partner_locations_partner_status", "partner_id", "status"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_partner_locations_status_v1"),
    )


class PartnerUserRole(Base):
    __tablename__ = "partner_user_roles"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Text, nullable=False)
    roles = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("partner_id", "user_id", name="uq_partner_user_roles_partner_user"),
        Index("ix_partner_user_roles_user_id", "user_id"),
    )


class PartnerTerms(Base):
    __tablename__ = "partner_terms"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    terms = Column(JSON, nullable=False, default=dict)
    status = Column(Text, nullable=False, default="DRAFT")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("partner_id", "version", name="uq_partner_terms_partner_version"),
        CheckConstraint("status IN ('DRAFT','ACTIVE','ARCHIVED')", name="ck_partner_terms_status_v1"),
    )


__all__ = ["Partner", "PartnerLocation", "PartnerTerms", "PartnerUserRole"]
