from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ErpSystemType(str, Enum):
    ONE_C = "1C"
    SAP = "SAP"
    GENERIC = "GENERIC"


class ErpExportFormat(str, Enum):
    CSV = "CSV"
    JSON = "JSON"
    XML_1C = "XML_1C"


class ErpDeliveryMode(str, Enum):
    S3_PULL = "S3_PULL"
    WEBHOOK_PUSH = "WEBHOOK_PUSH"
    SFTP_PUSH = "SFTP_PUSH"
    API_PUSH = "API_PUSH"


class ErpMappingStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ErpMappingMatchKind(str, Enum):
    DOC_TYPE = "DOC_TYPE"
    SERVICE_CODE = "SERVICE_CODE"
    PRODUCT_TYPE = "PRODUCT_TYPE"
    COMMISSION_KIND = "COMMISSION_KIND"
    TAX_RATE = "TAX_RATE"
    PARTNER = "PARTNER"
    CUSTOM = "CUSTOM"


class ErpCounterpartyRefMode(str, Enum):
    INN_KPP = "INN_KPP"
    ERP_ID = "ERP_ID"
    NAME = "NAME"


class ErpReconciliationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    IN_PROGRESS = "IN_PROGRESS"
    OK = "OK"
    MISMATCH = "MISMATCH"
    FAILED = "FAILED"


class ErpReconciliationVerdict(str, Enum):
    OK = "OK"
    MISSING_IN_ERP = "MISSING_IN_ERP"
    EXTRA_IN_ERP = "EXTRA_IN_ERP"
    AMOUNT_DIFF = "AMOUNT_DIFF"
    TAX_DIFF = "TAX_DIFF"


class ErpExportProfile(Base):
    __tablename__ = "erp_export_profiles"
    __table_args__ = (
        Index("ix_erp_export_profiles_tenant", "tenant_id"),
        Index("ix_erp_export_profiles_client", "client_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True)
    system_type = Column(ExistingEnum(ErpSystemType, name="erp_system_type"), nullable=False)
    format = Column(ExistingEnum(ErpExportFormat, name="erp_export_format"), nullable=False)
    mapping_id = Column(GUID(), nullable=True)
    delivery_mode = Column(ExistingEnum(ErpDeliveryMode, name="erp_delivery_mode"), nullable=False)
    enabled = Column(Boolean, nullable=False, server_default="true", default=True)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ErpMapping(Base):
    __tablename__ = "erp_mappings"
    __table_args__ = (
        Index("ix_erp_mappings_tenant", "tenant_id"),
        Index("ix_erp_mappings_client", "client_id"),
        Index("ix_erp_mappings_status", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True)
    system_type = Column(ExistingEnum(ErpSystemType, name="erp_system_type"), nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(ExistingEnum(ErpMappingStatus, name="erp_mapping_status"), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    rules = relationship(
        "ErpMappingRule",
        back_populates="mapping",
        cascade="all, delete-orphan",
    )


class ErpMappingRule(Base):
    __tablename__ = "erp_mapping_rules"
    __table_args__ = (
        Index("ix_erp_mapping_rules_mapping_priority", "mapping_id", "priority"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    mapping_id = Column(GUID(), ForeignKey("erp_mappings.id"), nullable=False)
    match_kind = Column(ExistingEnum(ErpMappingMatchKind, name="erp_mapping_match_kind"), nullable=False)
    match_value = Column(Text, nullable=False)
    gl_account = Column(String(64), nullable=False)
    subaccount_1 = Column(String(64), nullable=True)
    subaccount_2 = Column(String(64), nullable=True)
    subaccount_3 = Column(String(64), nullable=True)
    cost_item = Column(String(128), nullable=True)
    vat_code = Column(String(64), nullable=True)
    counterparty_ref_mode = Column(
        ExistingEnum(ErpCounterpartyRefMode, name="erp_counterparty_ref_mode"),
        nullable=True,
    )
    nomenclature_ref = Column(String(128), nullable=True)
    priority = Column(Integer, nullable=False, default=100, server_default="100")
    enabled = Column(Boolean, nullable=False, server_default="true", default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    mapping = relationship("ErpMapping", back_populates="rules")


class ErpReconciliationRun(Base):
    __tablename__ = "erp_reconciliation_runs"
    __table_args__ = (
        Index("ix_erp_reconciliation_runs_batch", "export_batch_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True)
    export_batch_id = Column(String(36), ForeignKey("accounting_export_batches.id"), nullable=False)
    system_type = Column(ExistingEnum(ErpSystemType, name="erp_system_type"), nullable=False)
    status = Column(ExistingEnum(ErpReconciliationStatus, name="erp_reconciliation_status"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    metrics = Column(JSON_TYPE, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ErpReconciliationItem(Base):
    __tablename__ = "erp_reconciliation_items"
    __table_args__ = (
        Index("ix_erp_reconciliation_items_run", "run_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    run_id = Column(GUID(), ForeignKey("erp_reconciliation_runs.id"), nullable=False)
    item_key = Column(String(128), nullable=False)
    verdict = Column(ExistingEnum(ErpReconciliationVerdict, name="erp_reconciliation_verdict"), nullable=False)
    diff = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "ErpCounterpartyRefMode",
    "ErpDeliveryMode",
    "ErpExportFormat",
    "ErpExportProfile",
    "ErpMapping",
    "ErpMappingMatchKind",
    "ErpMappingRule",
    "ErpMappingStatus",
    "ErpReconciliationItem",
    "ErpReconciliationRun",
    "ErpReconciliationStatus",
    "ErpReconciliationVerdict",
    "ErpSystemType",
]
