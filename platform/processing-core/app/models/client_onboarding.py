from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ClientOnboarding(Base):
    __tablename__ = "client_onboarding"

    client_id = Column(GUID(), primary_key=True)
    owner_user_id = Column(String(64), nullable=False, index=True)
    step = Column(String(32), nullable=False, server_default="PROFILE")
    status = Column(String(32), nullable=False, server_default="DRAFT")
    client_type = Column(String(32), nullable=True)
    profile_json = Column(JSON_TYPE, nullable=True)
    contract_id = Column(GUID(), ForeignKey("client_onboarding_contracts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ClientOnboardingContract(Base):
    __tablename__ = "client_onboarding_contracts"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default="DRAFT")
    pdf_url = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, server_default="1")
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signature_meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = ["ClientOnboarding", "ClientOnboardingContract"]
