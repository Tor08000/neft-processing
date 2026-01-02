from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class ContractImmutableError(ValueError):
    """Raised when a WORM contract record is mutated."""


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    contract_number = Column(String(64), nullable=False, unique=True)
    contract_type = Column(String(32), nullable=False)
    party_a_type = Column(String(32), nullable=False)
    party_a_id = Column(GUID(), nullable=False)
    party_b_type = Column(String(32), nullable=False)
    party_b_id = Column(GUID(), nullable=False)
    currency = Column(String(8), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default=ContractStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


class ContractVersion(Base):
    __tablename__ = "contract_versions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    terms = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


class ContractObligation(Base):
    __tablename__ = "contract_obligations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_type = Column(String(32), nullable=False)
    metric = Column(String(64), nullable=False)
    threshold = Column(Numeric(18, 4), nullable=False)
    comparison = Column(String(8), nullable=False)
    window = Column(String(32), nullable=True)
    penalty_type = Column(String(16), nullable=False)
    penalty_value = Column(Numeric(18, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ContractEvent(Base):
    __tablename__ = "contract_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON_TYPE, nullable=False)
    hash = Column(String(64), nullable=False)
    signature = Column(String(512), nullable=True)
    signature_alg = Column(String(64), nullable=True)
    signing_key_id = Column(String(128), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(GUID(), nullable=False)


class SLAResult(Base):
    __tablename__ = "sla_results"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_id = Column(GUID(), ForeignKey("contract_obligations.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    measured_value = Column(Numeric(18, 4), nullable=False)
    status = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


@event.listens_for(Contract, "before_update")
@event.listens_for(Contract, "before_delete")
def _block_contract_mutation(mapper, connection, target: Contract) -> None:
    raise ContractImmutableError("contract_immutable")


@event.listens_for(ContractVersion, "before_update")
@event.listens_for(ContractVersion, "before_delete")
def _block_contract_version_mutation(mapper, connection, target: ContractVersion) -> None:
    raise ContractImmutableError("contract_version_immutable")


@event.listens_for(ContractEvent, "before_update")
@event.listens_for(ContractEvent, "before_delete")
def _block_contract_event_mutation(mapper, connection, target: ContractEvent) -> None:
    raise ContractImmutableError("contract_event_immutable")


__all__ = [
    "Contract",
    "ContractEvent",
    "ContractImmutableError",
    "ContractObligation",
    "ContractStatus",
    "ContractVersion",
    "SLAResult",
]
