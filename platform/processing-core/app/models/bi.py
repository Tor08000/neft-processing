from __future__ import annotations

from enum import Enum
from uuid import uuid4
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base


json_variant = JSON().with_variant(postgresql.JSONB, "postgresql")


class BiScopeType(str, Enum):
    TENANT = "TENANT"
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    STATION = "STATION"


class BiExportKind(str, Enum):
    ORDERS = "ORDERS"
    ORDER_EVENTS = "ORDER_EVENTS"
    PAYOUTS = "PAYOUTS"
    DECLINES = "DECLINES"
    DAILY_METRICS = "DAILY_METRICS"


class BiExportFormat(str, Enum):
    CSV = "CSV"
    JSONL = "JSONL"
    PARQUET = "PARQUET"


class BiExportStatus(str, Enum):
    CREATED = "CREATED"
    GENERATED = "GENERATED"
    DELIVERED = "DELIVERED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class BiSyncRunType(str, Enum):
    INIT = "INIT"
    INCREMENTAL = "INCREMENTAL"


class BiSyncRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BiCursor(Base):
    __tablename__ = "bi_cursors"
    __table_args__ = {"schema": "bi"}

    name = Column(String(64), primary_key=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BiClickhouseCursor(Base):
    __tablename__ = "bi_clickhouse_cursors"
    __table_args__ = {"schema": "bi"}

    dataset = Column(String(64), primary_key=True)
    last_id = Column(String(128), nullable=True)
    last_occurred_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BiOrderEvent(Base):
    __tablename__ = "bi_order_events"
    __table_args__ = {"schema": "bi"}

    event_id = Column(String(64), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    order_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    amount = Column(BigInteger, nullable=True)
    currency = Column(String(8), nullable=True)
    service_id = Column(String(64), nullable=True)
    offer_id = Column(String(64), nullable=True)
    status_after = Column(String(64), nullable=True)
    correlation_id = Column(String(128), nullable=True)
    payload = Column(json_variant, nullable=True)


class BiPayoutEvent(Base):
    __tablename__ = "bi_payout_events"
    __table_args__ = {"schema": "bi"}

    event_id = Column(String(64), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    settlement_id = Column(String(64), nullable=True, index=True)
    payout_batch_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    amount_gross = Column(BigInteger, nullable=True)
    amount_net = Column(BigInteger, nullable=True)
    amount_commission = Column(BigInteger, nullable=True)
    currency = Column(String(8), nullable=True)
    correlation_id = Column(String(128), nullable=True)
    payload = Column(json_variant, nullable=True)


class BiDeclineEvent(Base):
    __tablename__ = "bi_decline_events"
    __table_args__ = {"schema": "bi"}

    operation_id = Column(String(64), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    primary_reason = Column(String(255), nullable=True, index=True)
    secondary_reasons = Column(json_variant, nullable=True)
    amount = Column(BigInteger, nullable=True)
    product_type = Column(String(32), nullable=True)
    station_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(128), nullable=True)


class BiDailyMetric(Base):
    __tablename__ = "bi_daily_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "scope_type", "scope_id", name="uq_bi_daily_scope"),
        {"schema": "bi"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    scope_type = Column(
        SAEnum(BiScopeType, name="bi_scope_type", schema="bi"),
        nullable=False,
        index=True,
    )
    scope_id = Column(String(64), nullable=False, index=True)
    spend_total = Column(BigInteger, nullable=False, default=0)
    orders_total = Column(BigInteger, nullable=False, default=0)
    orders_completed = Column(BigInteger, nullable=False, default=0)
    refunds_total = Column(BigInteger, nullable=False, default=0)
    payouts_total = Column(BigInteger, nullable=False, default=0)
    declines_total = Column(BigInteger, nullable=False, default=0)
    top_primary_reason = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BiPriceVersionMetric(Base):
    __tablename__ = "bi_price_version_metrics"
    __table_args__ = (
        UniqueConstraint(
            "partner_id",
            "price_version_id",
            "date",
            name="uq_bi_price_version_metric",
        ),
        {"schema": "bi"},
    )

    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(String(64), primary_key=True)
    price_version_id = Column(String(64), primary_key=True)
    date = Column(Date, primary_key=True)
    orders_count = Column(BigInteger, nullable=False, default=0)
    completed_orders_count = Column(BigInteger, nullable=False, default=0)
    revenue_total = Column(BigInteger, nullable=False, default=0)
    avg_order_value = Column(BigInteger, nullable=False, default=0)
    refunds_count = Column(BigInteger, nullable=False, default=0)


class BiOfferMetric(Base):
    __tablename__ = "bi_offer_metrics"
    __table_args__ = (
        UniqueConstraint("partner_id", "offer_id", "date", name="uq_bi_offer_metric"),
        {"schema": "bi"},
    )

    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(String(64), primary_key=True)
    offer_id = Column(String(64), primary_key=True)
    date = Column(Date, primary_key=True)
    views_count = Column(BigInteger, nullable=True)
    orders_count = Column(BigInteger, nullable=False, default=0)
    conversion_rate = Column(Numeric(10, 4), nullable=True)
    avg_price = Column(BigInteger, nullable=False, default=0)
    revenue_total = Column(BigInteger, nullable=False, default=0)


class BiExportBatch(Base):
    __tablename__ = "bi_export_batches"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    kind = Column(SAEnum(BiExportKind, name="bi_export_kind", schema="bi"), nullable=False)
    scope_type = Column(
        SAEnum(BiScopeType, name="bi_export_scope_type", schema="bi"),
        nullable=True,
    )
    scope_id = Column(String(64), nullable=True)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    format = Column(SAEnum(BiExportFormat, name="bi_export_format", schema="bi"), nullable=False)
    status = Column(SAEnum(BiExportStatus, name="bi_export_status", schema="bi"), nullable=False)
    object_key = Column(String(512), nullable=True)
    manifest_key = Column(String(512), nullable=True)
    bucket = Column(String(128), nullable=True)
    sha256 = Column(String(64), nullable=True)
    row_count = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class BiExport(Base):
    __tablename__ = "bi_exports"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    mart_name = Column(String(128), nullable=False)
    period = Column(String(64), nullable=False)
    format = Column(String(16), nullable=False)
    file_ref = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BiWatermark(Base):
    __tablename__ = "bi_watermarks"
    __table_args__ = {"schema": "bi"}

    name = Column(String(128), primary_key=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BiSyncRun(Base):
    __tablename__ = "bi_sync_runs"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    type = Column(SAEnum(BiSyncRunType, name="bi_sync_run_type", schema="bi"), nullable=False)
    status = Column(SAEnum(BiSyncRunStatus, name="bi_sync_run_status", schema="bi"), nullable=False)
    rows_written = Column(BigInteger, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BiMartVersion(Base):
    __tablename__ = "bi_mart_versions"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mart_name = Column(String(128), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BiMartFinanceDaily(Base):
    __tablename__ = "mart_finance_daily"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    gross_revenue = Column(BigInteger, nullable=False, default=0)
    net_revenue = Column(BigInteger, nullable=False, default=0)
    commission_income = Column(BigInteger, nullable=False, default=0)
    vat = Column(BigInteger, nullable=False, default=0)
    refunds = Column(BigInteger, nullable=False, default=0)
    penalties = Column(BigInteger, nullable=False, default=0)
    margin = Column(BigInteger, nullable=False, default=0)


class BiMartCashflow(Base):
    __tablename__ = "mart_cashflow"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    inflow = Column(BigInteger, nullable=False, default=0)
    outflow = Column(BigInteger, nullable=False, default=0)
    net_cashflow = Column(BigInteger, nullable=False, default=0)
    balance_estimated = Column(BigInteger, nullable=False, default=0)


class BiMartOpsSla(Base):
    __tablename__ = "mart_ops_sla"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    total_orders = Column(BigInteger, nullable=False, default=0)
    sla_breaches = Column(BigInteger, nullable=False, default=0)
    avg_resolution_time = Column(Numeric(12, 4), nullable=True)
    p95_resolution_time = Column(Numeric(12, 4), nullable=True)
    top_partners_by_breaches = Column(json_variant, nullable=True)


class BiMartPartnerPerformance(Base):
    __tablename__ = "mart_partner_performance"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(String(64), nullable=False, index=True)
    period = Column(Date, nullable=False, index=True)
    orders_count = Column(BigInteger, nullable=False, default=0)
    revenue = Column(BigInteger, nullable=False, default=0)
    penalties = Column(BigInteger, nullable=False, default=0)
    payout_amount = Column(BigInteger, nullable=False, default=0)
    sla_score = Column(Numeric(6, 4), nullable=True)


class BiMartClientSpend(Base):
    __tablename__ = "mart_client_spend"
    __table_args__ = {"schema": "bi"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    period = Column(Date, nullable=False, index=True)
    spend_total = Column(BigInteger, nullable=False, default=0)
    spend_by_product = Column(json_variant, nullable=True)
    fuel_spend = Column(BigInteger, nullable=False, default=0)
    marketplace_spend = Column(BigInteger, nullable=False, default=0)
    avg_ticket = Column(BigInteger, nullable=False, default=0)


__all__ = [
    "BiClickhouseCursor",
    "BiCursor",
    "BiDailyMetric",
    "BiDeclineEvent",
    "BiExportBatch",
    "BiExport",
    "BiExportFormat",
    "BiExportKind",
    "BiExportStatus",
    "BiMartCashflow",
    "BiMartClientSpend",
    "BiMartFinanceDaily",
    "BiMartOpsSla",
    "BiMartPartnerPerformance",
    "BiMartVersion",
    "BiOfferMetric",
    "BiOrderEvent",
    "BiPayoutEvent",
    "BiPriceVersionMetric",
    "BiScopeType",
    "BiSyncRun",
    "BiSyncRunStatus",
    "BiSyncRunType",
    "BiWatermark",
]
