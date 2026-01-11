from __future__ import annotations

from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class FuelProviderConnectionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class FuelProviderAuthType(str, Enum):
    API_KEY = "API_KEY"
    OAUTH2 = "OAUTH2"
    EDI = "EDI"


class FuelIngestMode(str, Enum):
    POLL = "POLL"
    BACKFILL = "BACKFILL"
    REPLAY = "REPLAY"
    EDI = "EDI"


class FuelProviderBatchStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class FuelProviderRecordStatus(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


class FuelProviderConnection(Base):
    __tablename__ = "fuel_provider_connections"
    __table_args__ = (
        UniqueConstraint("client_id", "provider_code", name="uq_fuel_provider_conn_client_provider"),
        Index("ix_fuel_provider_conn_status", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    provider_code = Column(String(64), nullable=False, index=True)
    status = Column(
        ExistingEnum(FuelProviderConnectionStatus, name="fuel_provider_connection_status"),
        nullable=False,
    )
    auth_type = Column(ExistingEnum(FuelProviderAuthType, name="fuel_provider_auth_type"), nullable=False)
    secret_ref = Column(String(256), nullable=True)
    config = Column(JSON, nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_cursor = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FuelProviderCardMap(Base):
    __tablename__ = "fuel_provider_card_map"
    __table_args__ = (
        UniqueConstraint("provider_code", "provider_card_id", name="uq_fuel_provider_card_id"),
        UniqueConstraint("provider_code", "card_id", name="uq_fuel_provider_card_card"),
        Index("ix_fuel_provider_card_client", "client_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    provider_code = Column(String(64), nullable=False, index=True)
    card_id = Column(GUID(), nullable=False, index=True)
    provider_card_id = Column(String(128), nullable=False, index=True)
    status = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelProviderRawEvent(Base):
    __tablename__ = "fuel_provider_raw_events"
    __table_args__ = (
        Index("ix_fuel_provider_raw_events_client_created", "client_id", "created_at"),
        Index("ix_fuel_provider_raw_events_provider_created", "provider_code", "created_at"),
        Index(
            "uq_fuel_provider_raw_event_provider_event",
            "provider_code",
            "provider_event_id",
            unique=True,
            postgresql_where=sa.text("provider_event_id IS NOT NULL"),
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    provider_code = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    provider_event_id = Column(String(128), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    payload_redacted = Column(JSON, nullable=True)
    payload_hash = Column(String(64), nullable=False)
    ingest_job_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelProviderBatch(Base):
    __tablename__ = "fuel_provider_batches"
    __table_args__ = (
        UniqueConstraint("provider_code", "batch_key", name="uq_fuel_provider_batch_key"),
        Index("ix_fuel_provider_batches_provider_status", "provider_code", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider_code = Column(String(64), nullable=False, index=True)
    batch_key = Column(String(128), nullable=False, index=True)
    source = Column(String(32), nullable=False)
    status = Column(ExistingEnum(FuelProviderBatchStatus, name="fuel_provider_batch_status"), nullable=False)
    payload_ref = Column(Text, nullable=True)
    records_total = Column(Integer, nullable=False, default=0)
    records_applied = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    records_duplicate = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    is_offline_batch = Column(Boolean, nullable=False, default=False)
    offline_window = Column(String(64), nullable=True)
    offline_profile_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FuelProviderRecord(Base):
    __tablename__ = "fuel_provider_records"
    __table_args__ = (
        UniqueConstraint("provider_code", "provider_tx_id", name="uq_fuel_provider_records_tx"),
        Index("ix_fuel_provider_records_batch", "batch_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    batch_id = Column(GUID(), ForeignKey("fuel_provider_batches.id"), nullable=False, index=True)
    provider_code = Column(String(64), nullable=False, index=True)
    provider_tx_id = Column(String(128), nullable=False, index=True)
    status = Column(ExistingEnum(FuelProviderRecordStatus, name="fuel_provider_record_status"), nullable=False)
    error = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelProviderAuthorizationDecision(Base):
    __tablename__ = "fuel_provider_authorization_decisions"
    __table_args__ = (Index("ix_fuel_provider_auth_decisions_provider", "provider_code", "created_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider_code = Column(String(64), nullable=False, index=True)
    provider_tx_id = Column(String(128), nullable=True, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    card_id = Column(GUID(), nullable=True, index=True)
    decision = Column(String(32), nullable=False)
    reason_code = Column(String(64), nullable=False)
    auth_code = Column(String(64), nullable=True)
    offline_profile_id = Column(GUID(), nullable=True)
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "FuelIngestMode",
    "FuelProviderAuthType",
    "FuelProviderBatch",
    "FuelProviderBatchStatus",
    "FuelProviderAuthorizationDecision",
    "FuelProviderCardMap",
    "FuelProviderConnection",
    "FuelProviderConnectionStatus",
    "FuelProviderRecord",
    "FuelProviderRecordStatus",
    "FuelProviderRawEvent",
]
