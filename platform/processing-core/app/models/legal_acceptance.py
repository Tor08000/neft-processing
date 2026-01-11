from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, String, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class LegalSubjectType(str, Enum):
    USER = "USER"
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class LegalAcceptanceImmutableError(ValueError):
    """Raised when a legal acceptance record is mutated."""


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subject_type = Column(ExistingEnum(LegalSubjectType, name="legal_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    document_code = Column(String(64), nullable=False)
    document_version = Column(String(32), nullable=False)
    document_locale = Column(String(8), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    acceptance_hash = Column(String(64), nullable=False)
    signature = Column(JSON_TYPE, nullable=True)
    meta = Column(JSON_TYPE, nullable=True)


@event.listens_for(LegalAcceptance, "before_update")
@event.listens_for(LegalAcceptance, "before_delete")
def _block_acceptance_mutation(mapper, connection, target: LegalAcceptance) -> None:
    raise LegalAcceptanceImmutableError("legal_acceptance_immutable")


__all__ = ["LegalAcceptance", "LegalAcceptanceImmutableError", "LegalSubjectType"]
