from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.integrations.fuel.models import FuelIngestMode


class FuelCardStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class FuelStationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelStationHealthStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class FuelStationHealthSource(str, Enum):
    MANUAL = "MANUAL"
    INTEGRATION = "INTEGRATION"
    TERMINAL = "TERMINAL"
    SYSTEM = "SYSTEM"


class FuelStationPriceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelStationPriceSource(str, Enum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    API = "API"


class FuelStationRiskZone(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class FuelNetworkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelProviderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class FuelTransactionStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DECLINED = "DECLINED"
    REVERSED = "REVERSED"
    SETTLED = "SETTLED"


class FuelTransactionAuthType(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class FuelIngestJobStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class FuelLimitCheckStatus(str, Enum):
    OK = "OK"
    SOFT_BREACH = "SOFT_BREACH"
    HARD_BREACH = "HARD_BREACH"


class FuelLimitBreachStatus(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    IGNORED = "IGNORED"


class FuelLimitBreachType(str, Enum):
    AMOUNT = "AMOUNT"
    VOLUME = "VOLUME"
    CATEGORY = "CATEGORY"
    STATION = "STATION"


class FuelLimitBreachScopeType(str, Enum):
    CARD = "card"
    GROUP = "group"


class FuelLimitScopeType(str, Enum):
    CLIENT = "CLIENT"
    CARD = "CARD"
    CARD_GROUP = "CARD_GROUP"
    VEHICLE = "VEHICLE"
    DRIVER = "DRIVER"


class FuelLimitType(str, Enum):
    AMOUNT = "AMOUNT"
    VOLUME = "VOLUME"
    COUNT = "COUNT"


class FuelLimitPeriod(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class FuelAnomalyType(str, Enum):
    SPIKE_AMOUNT = "SPIKE_AMOUNT"
    SPIKE_VOLUME = "SPIKE_VOLUME"
    NEW_MERCHANT = "NEW_MERCHANT"
    MERCHANT_OUTLIER = "MERCHANT_OUTLIER"
    TIME_OF_DAY = "TIME_OF_DAY"
    FREQUENCY_BURST = "FREQUENCY_BURST"
    GEO_DISTANCE = "GEO_DISTANCE"
    REPEATED_BREACH = "REPEATED_BREACH"


class FleetNotificationSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FuelAnomalyStatus(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    IGNORED = "IGNORED"


class FleetNotificationChannelType(str, Enum):
    WEBHOOK = "WEBHOOK"
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    TELEGRAM = "TELEGRAM"
    SMS = "SMS"
    VOICE = "VOICE"


class FleetNotificationChannelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class FleetTelegramBindingScopeType(str, Enum):
    CLIENT = "client"
    GROUP = "group"


class FleetTelegramChatType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class FleetTelegramBindingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    PENDING = "PENDING"


class FleetTelegramLinkTokenStatus(str, Enum):
    ISSUED = "ISSUED"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class FleetNotificationPolicyScopeType(str, Enum):
    CLIENT = "client"
    GROUP = "group"
    CARD = "card"


class FleetNotificationEventType(str, Enum):
    LIMIT_BREACH = "LIMIT_BREACH"
    ANOMALY = "ANOMALY"
    INGEST_FAILED = "INGEST_FAILED"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    POLICY_ACTION = "POLICY_ACTION"
    TEST = "TEST"


class FleetNotificationOutboxStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DEAD = "DEAD"


class FuelLimitEscalationAction(str, Enum):
    NOTIFY_ONLY = "NOTIFY_ONLY"
    AUTO_BLOCK_CARD = "AUTO_BLOCK_CARD"
    SUSPEND_GROUP = "SUSPEND_GROUP"


class FuelLimitEscalationStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class FuelType(str, Enum):
    DIESEL = "DIESEL"
    AI92 = "AI-92"
    AI95 = "AI-95"
    AI98 = "AI-98"
    GAS = "GAS"
    OTHER = "OTHER"


class FuelFraudSignalType(str, Enum):
    FUEL_OFF_ROUTE_STRONG = "FUEL_OFF_ROUTE_STRONG"
    FUEL_STOP_MISMATCH_STRONG = "FUEL_STOP_MISMATCH_STRONG"
    MULTI_CARD_SAME_STATION_BURST = "MULTI_CARD_SAME_STATION_BURST"
    REPEATED_NIGHT_REFUEL = "REPEATED_NIGHT_REFUEL"
    TANK_SANITY_REPEAT = "TANK_SANITY_REPEAT"
    STATION_OUTLIER_CLUSTER = "STATION_OUTLIER_CLUSTER"
    DRIVER_VEHICLE_MISMATCH = "DRIVER_VEHICLE_MISMATCH"
    ROUTE_DEVIATION_BEFORE_FUEL = "ROUTE_DEVIATION_BEFORE_FUEL"


class FleetOfflineProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FleetOfflineReconciliationStatus(str, Enum):
    STARTED = "STARTED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class FleetOfflineDiscrepancyReason(str, Enum):
    OFFLINE_LIMIT_EXCEEDED = "OFFLINE_LIMIT_EXCEEDED"
    UNEXPECTED_PRODUCT = "UNEXPECTED_PRODUCT"
    CARD_BLOCKED_AT_TIME = "CARD_BLOCKED_AT_TIME"
    DUPLICATE_TX = "DUPLICATE_TX"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"


class FuelCard(Base):
    __tablename__ = "fuel_cards"
    __table_args__ = (
        UniqueConstraint("tenant_id", "card_token", name="uq_fuel_cards_tenant_token"),
        UniqueConstraint("card_alias", name="uq_fuel_cards_card_alias"),
        Index("ix_fuel_cards_client_status", "client_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    card_token = Column(String(128), nullable=False, index=True)
    card_alias = Column(String(128), nullable=True, index=True)
    masked_pan = Column(String(32), nullable=True)
    token_ref = Column(String(128), nullable=True)
    status = Column(ExistingEnum(FuelCardStatus, name="fuel_card_status"), nullable=False)
    card_group_id = Column(GUID(), ForeignKey("fuel_card_groups.id"), nullable=True, index=True)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True, index=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True, index=True)
    card_offline_profile_id = Column(GUID(), ForeignKey("fleet_offline_profiles.id"), nullable=True, index=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
    currency = Column(String(3), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelCardStatusEventActorType(str, Enum):
    SYSTEM = "system"
    USER = "user"


class FuelCardStatusEvent(Base):
    __tablename__ = "fuel_card_status_events"
    __table_args__ = (
        Index("ix_fuel_card_status_events_card_created", "card_id", "created_at"),
        Index("ix_fuel_card_status_events_client_created", "client_id", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    card_id = Column(GUID(), ForeignKey("fuel_cards.id"), nullable=False, index=True)
    from_status = Column(ExistingEnum(FuelCardStatus, name="fuel_card_status"), nullable=True)
    to_status = Column(ExistingEnum(FuelCardStatus, name="fuel_card_status"), nullable=False)
    reason = Column(Text, nullable=True)
    actor_type = Column(
        ExistingEnum(FuelCardStatusEventActorType, name="fuel_card_status_actor_type"),
        nullable=False,
    )
    actor_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FuelCardGroupStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelCardGroup(Base):
    __tablename__ = "fuel_card_groups"
    __table_args__ = (UniqueConstraint("client_id", "name", name="uq_fuel_card_groups_client_name"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(256), nullable=True)
    status = Column(ExistingEnum(FuelCardGroupStatus, name="fuel_card_group_status"), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelNetwork(Base):
    __tablename__ = "fuel_networks"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    name = Column(String(128), nullable=False)
    provider_code = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(ExistingEnum(FuelNetworkStatus, name="fuel_network_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelProvider(Base):
    __tablename__ = "fuel_providers"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    status = Column(ExistingEnum(FuelProviderStatus, name="fuel_provider_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelMerchant(Base):
    __tablename__ = "fuel_merchants"
    __table_args__ = (UniqueConstraint("provider_code", "merchant_key", name="uq_fuel_merchants_provider_key"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider_code = Column(String(64), nullable=False, index=True)
    merchant_key = Column(String(256), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    category_default = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelStationNetwork(Base):
    __tablename__ = "fuel_station_networks"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    name = Column(String(128), nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelStation(Base):
    __tablename__ = "fuel_stations"
    __table_args__ = (
        Index("ix_fuel_stations_lat_lon", "lat", "lon"),
        UniqueConstraint("network_id", "station_code", name="uq_fuel_station_code_network"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    network_id = Column(GUID(), ForeignKey("fuel_networks.id"), nullable=False, index=True)
    station_network_id = Column(
        GUID(),
        ForeignKey("fuel_station_networks.id"),
        nullable=True,
        index=True,
    )
    name = Column(String(256), nullable=False)
    country = Column(String(64), nullable=True)
    region = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    nav_url = Column(Text, nullable=True)
    geo_hash = Column(String(16), nullable=True)
    mcc = Column(String(8), nullable=True)
    station_code = Column(String(64), nullable=True, index=True)
    status = Column(ExistingEnum(FuelStationStatus, name="fuel_station_status"), nullable=False)
    risk_zone = Column(String(16), nullable=True, index=True)
    risk_zone_reason = Column(Text, nullable=True)
    risk_zone_updated_at = Column(DateTime(timezone=True), nullable=True)
    risk_zone_updated_by = Column(String(256), nullable=True)
    risk_manual_lock = Column(Boolean, nullable=False, server_default="false", default=False)
    risk_manual_until = Column(DateTime(timezone=True), nullable=True)
    risk_auto_enabled = Column(Boolean, nullable=False, server_default="true", default=True)
    risk_last_auto_at = Column(DateTime(timezone=True), nullable=True)
    risk_red_clear_streak_days = Column(Integer, nullable=False, server_default="0", default=0)
    risk_yellow_clear_streak_days = Column(Integer, nullable=False, server_default="0", default=0)
    risk_last_eval_day = Column(Date, nullable=True)
    health_status = Column(String(16), nullable=True, index=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True, index=True)
    health_reason = Column(Text, nullable=True)
    health_updated_at = Column(DateTime(timezone=True), nullable=True)
    health_updated_by = Column(String(256), nullable=True)
    health_source = Column(String(16), nullable=True)
    health_manual_lock = Column(Boolean, nullable=False, server_default="false", default=False)
    health_manual_until = Column(DateTime(timezone=True), nullable=True)
    health_auto_enabled = Column(Boolean, nullable=False, server_default="true", default=True)
    health_last_auto_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OpsStationEvent(Base):
    __tablename__ = "ops_station_events"
    __table_args__ = (
        Index("ix_ops_station_events_station_created", "station_id", "created_at"),
        Index("ix_ops_station_events_type_created", "event_type", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    old_value = Column(String(64), nullable=True)
    new_value = Column(String(64), nullable=True)
    computed_metrics = Column(JSON, nullable=True)
    policy_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(128), nullable=False, server_default="system")


class FuelTransaction(Base):
    __tablename__ = "fuel_transactions"
    __table_args__ = (
        Index("ix_fuel_transactions_client_time", "client_id", "occurred_at"),
        Index("ix_fuel_transactions_card_time", "card_id", "occurred_at"),
        Index("ix_fuel_transactions_vehicle_time", "vehicle_id", "occurred_at"),
        Index("ix_fuel_transactions_status_time", "status", "occurred_at"),
        Index("ix_fuel_transactions_external_ref", "external_ref"),
        Index("ix_fuel_transactions_provider_tx", "provider_code", "provider_tx_id"),
        Index("ix_fuel_transactions_provider_batch", "provider_batch_key"),
        UniqueConstraint("provider_code", "provider_tx_id", name="uq_fuel_transactions_provider_tx"),
        UniqueConstraint("provider_code", "external_ref", name="uq_fuel_transactions_provider_external_ref"),
        UniqueConstraint(
            "tenant_id",
            "network_id",
            "external_ref",
            name="uq_fuel_transactions_tenant_network_external_ref",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    card_id = Column(GUID(), ForeignKey("fuel_cards.id"), nullable=False, index=True)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True, index=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True, index=True)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    network_id = Column(GUID(), ForeignKey("fuel_networks.id"), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    fuel_type = Column(ExistingEnum(FuelType, name="fuel_type"), nullable=False)
    volume_ml = Column(BigInteger, nullable=False)
    unit_price_minor = Column(BigInteger, nullable=False)
    amount_total_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(ExistingEnum(FuelTransactionStatus, name="fuel_tx_status"), nullable=False)
    auth_type = Column(ExistingEnum(FuelTransactionAuthType, name="fuel_tx_auth_type"), nullable=True)
    decline_code = Column(String(64), nullable=True)
    risk_decision_id = Column(GUID(), ForeignKey("risk_decisions.id"), nullable=True)
    ledger_transaction_id = Column(
        GUID(), ForeignKey("internal_ledger_transactions.id"), nullable=True
    )
    provider_code = Column(String(64), nullable=True, index=True)
    provider_tx_id = Column(String(128), nullable=True, index=True)
    provider_batch_key = Column(String(128), nullable=True, index=True)
    merchant_key = Column(String(256), nullable=True, index=True)
    external_ref = Column(String(128), nullable=True)
    external_settlement_ref = Column(String(128), nullable=True)
    external_reverse_ref = Column(String(128), nullable=True)
    amount = Column(Numeric, nullable=True)
    volume_liters = Column(Numeric, nullable=True)
    category = Column(String(128), nullable=True)
    merchant_name = Column(String(256), nullable=True)
    station_external_id = Column(String(128), nullable=True)
    location = Column(String(256), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    raw_payload_redacted = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    limit_check_status = Column(
        ExistingEnum(FuelLimitCheckStatus, name="fuel_limit_check_status"), nullable=True
    )
    limit_check_details = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelStationPrice(Base):
    __tablename__ = "fuel_station_prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_fuel_station_prices_price_positive"),
        CheckConstraint("currency = 'RUB'", name="ck_fuel_station_prices_currency"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            name="ck_fuel_station_prices_valid_window",
        ),
        UniqueConstraint(
            "station_id",
            "product_code",
            "valid_from",
            "valid_to",
            name="uq_fuel_station_prices_station_product_validity",
        ),
        Index("ix_fuel_station_prices_station_product_status", "station_id", "product_code", "status"),
        Index("ix_fuel_station_prices_station_status", "station_id", "status"),
        Index("ix_fuel_station_prices_valid_from", "valid_from"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    product_code = Column(String(32), nullable=False)
    price = Column(Numeric(12, 3), nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    status = Column(ExistingEnum(FuelStationPriceStatus, name="fuel_station_price_status"), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    source = Column(ExistingEnum(FuelStationPriceSource, name="fuel_station_price_source"), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(256), nullable=True)
    meta = Column(JSON, nullable=True)


class FuelStationPriceAudit(Base):
    __tablename__ = "fuel_station_price_audit"
    __table_args__ = (
        Index("ix_fuel_station_price_audit_station_ts", "station_id", "ts"),
        Index("ix_fuel_station_price_audit_product_ts", "product_code", "ts"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    product_code = Column(String(32), nullable=False)
    action = Column(String(16), nullable=False)
    actor = Column(Text, nullable=True)
    source = Column(String(16), nullable=False)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    request_id = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


class CommercialRecommendationAction(Base):
    __tablename__ = "commercial_recommendation_actions"
    __table_args__ = (
        Index("ix_commercial_recommendation_actions_rec_ts", "rec_id", "ts"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    rec_id = Column(String(128), nullable=False, index=True)
    action_type = Column(String(16), nullable=False)
    actor = Column(String(256), nullable=True)
    ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meta = Column(JSON, nullable=True)


class FuelIngestJob(Base):
    __tablename__ = "fuel_ingest_jobs"
    __table_args__ = (Index("ix_fuel_ingest_jobs_provider_received", "provider_code", "received_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider_code = Column(String(64), nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    batch_ref = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(ExistingEnum(FuelIngestJobStatus, name="fuel_ingest_job_status"), nullable=False)
    mode = Column(ExistingEnum(FuelIngestMode, name="fuel_ingest_mode"), nullable=True)
    cursor = Column(String(256), nullable=True)
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)
    total_count = Column(Integer, nullable=False, default=0)
    inserted_count = Column(Integer, nullable=False, default=0)
    deduped_count = Column(Integer, nullable=False, default=0)
    error = Column(String(512), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)


class FleetOfflineProfile(Base):
    __tablename__ = "fleet_offline_profiles"
    __table_args__ = (Index("ix_fleet_offline_profiles_client_status", "client_id", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    daily_amount_limit = Column(Numeric, nullable=True)
    daily_txn_limit = Column(Integer, nullable=True)
    allowed_products = Column(JSON, nullable=True)
    allowed_stations = Column(JSON, nullable=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    status = Column(ExistingEnum(FleetOfflineProfileStatus, name="fleet_offline_profile_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FleetOfflineReconciliationRun(Base):
    __tablename__ = "fleet_offline_reconciliation_runs"
    __table_args__ = (Index("ix_fleet_offline_reconciliation_client_period", "client_id", "period_key"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    period_key = Column(String(32), nullable=False, index=True)
    status = Column(
        ExistingEnum(FleetOfflineReconciliationStatus, name="fleet_offline_reconciliation_status"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FleetOfflineDiscrepancy(Base):
    __tablename__ = "fleet_offline_discrepancies"
    __table_args__ = (Index("ix_fleet_offline_discrepancies_run", "run_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    run_id = Column(GUID(), ForeignKey("fleet_offline_reconciliation_runs.id"), nullable=False, index=True)
    provider_tx_id = Column(String(128), nullable=True, index=True)
    tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True, index=True)
    reason = Column(
        ExistingEnum(FleetOfflineDiscrepancyReason, name="fleet_offline_discrepancy_reason"),
        nullable=False,
    )
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelUnmatchedRecord(Base):
    __tablename__ = "fuel_unmatched_records"
    __table_args__ = (
        Index("ix_fuel_unmatched_records_provider", "provider_code", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider_code = Column(String(64), nullable=False, index=True)
    provider_tx_id = Column(String(128), nullable=True, index=True)
    batch_id = Column(GUID(), nullable=True, index=True)
    reason = Column(String(128), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelLimitBreach(Base):
    __tablename__ = "fuel_limit_breaches"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(ExistingEnum(FuelLimitBreachScopeType, name="fuel_limit_breach_scope_type"), nullable=False)
    scope_id = Column(GUID(), nullable=False, index=True)
    period = Column(ExistingEnum(FuelLimitPeriod, name="fuel_limit_period"), nullable=False)
    limit_id = Column(GUID(), nullable=False, index=True)
    breach_type = Column(ExistingEnum(FuelLimitBreachType, name="fuel_limit_breach_type"), nullable=False)
    threshold = Column(Numeric, nullable=False)
    observed = Column(Numeric, nullable=False)
    delta = Column(Numeric, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True, index=True)
    status = Column(ExistingEnum(FuelLimitBreachStatus, name="fuel_limit_breach_status"), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FleetNotificationChannel(Base):
    __tablename__ = "fleet_notification_channels"
    __table_args__ = (Index("ix_fleet_notification_channels_client_type_status", "client_id", "channel_type", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    channel_type = Column(
        ExistingEnum(FleetNotificationChannelType, name="fleet_notification_channel_type"), nullable=False
    )
    target = Column(String(512), nullable=False)
    status = Column(
        ExistingEnum(FleetNotificationChannelStatus, name="fleet_notification_channel_status"), nullable=False
    )
    secret_ref = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FleetTelegramBinding(Base):
    __tablename__ = "fleet_telegram_bindings"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "chat_id",
            "scope_type",
            "scope_id",
            name="uq_fleet_telegram_bindings_client_chat_scope",
        ),
        Index("ix_fleet_telegram_bindings_client_status", "client_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(ExistingEnum(FleetTelegramBindingScopeType, name="fleet_telegram_scope_type"), nullable=False)
    scope_id = Column(GUID(), nullable=True)
    chat_id = Column(BigInteger, nullable=False)
    chat_title = Column(Text, nullable=True)
    chat_type = Column(ExistingEnum(FleetTelegramChatType, name="fleet_telegram_chat_type"), nullable=False)
    status = Column(ExistingEnum(FleetTelegramBindingStatus, name="fleet_telegram_binding_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id = Column(GUID(), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)


class FleetTelegramLinkToken(Base):
    __tablename__ = "fleet_telegram_link_tokens"
    __table_args__ = (Index("ix_fleet_telegram_link_tokens_client_status", "client_id", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(ExistingEnum(FleetTelegramBindingScopeType, name="fleet_telegram_scope_type"), nullable=False)
    scope_id = Column(GUID(), nullable=True)
    token = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(FleetTelegramLinkTokenStatus, name="fleet_telegram_link_token_status"), nullable=False)
    issued_by_user_id = Column(GUID(), nullable=True)
    used_by_chat_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FleetNotificationPolicy(Base):
    __tablename__ = "fleet_notification_policies"
    __table_args__ = (Index("ix_fleet_notification_policies_client_event_active", "client_id", "event_type", "active"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(ExistingEnum(FleetNotificationPolicyScopeType, name="fleet_notification_scope_type"), nullable=False)
    scope_id = Column(GUID(), nullable=True)
    event_type = Column(ExistingEnum(FleetNotificationEventType, name="fleet_notification_event_type"), nullable=False)
    severity_min = Column(ExistingEnum(FleetNotificationSeverity, name="fleet_notification_severity"), nullable=False)
    channels = Column(JSON, nullable=False)
    cooldown_seconds = Column(Integer, nullable=False, default=300, server_default="300")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    action_on_critical = Column(
        ExistingEnum(FuelLimitEscalationAction, name="fuel_limit_escalation_action"),
        nullable=True,
    )
    hard_breach_only = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FleetActionPolicyScopeType(str, Enum):
    CLIENT = "client"
    GROUP = "group"
    CARD = "card"


class FleetActionTriggerType(str, Enum):
    LIMIT_BREACH = "LIMIT_BREACH"
    ANOMALY = "ANOMALY"


class FleetActionBreachKind(str, Enum):
    SOFT = "SOFT"
    HARD = "HARD"
    ANY = "ANY"


class FleetActionPolicyAction(str, Enum):
    NONE = "NONE"
    NOTIFY_ONLY = "NOTIFY_ONLY"
    AUTO_BLOCK_CARD = "AUTO_BLOCK_CARD"
    ESCALATE_CASE = "ESCALATE_CASE"


class FleetPolicyExecutionStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    APPLIED = "APPLIED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class FleetActionPolicy(Base):
    __tablename__ = "fleet_action_policies"
    __table_args__ = (
        Index("ix_fleet_action_policies_client_trigger_active", "client_id", "trigger_type", "active"),
        Index("ix_fleet_action_policies_scope_active", "scope_type", "scope_id", "active"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(
        ExistingEnum(FleetActionPolicyScopeType, name="fleet_action_policy_scope_type"),
        nullable=False,
    )
    scope_id = Column(GUID(), nullable=True)
    trigger_type = Column(ExistingEnum(FleetActionTriggerType, name="fleet_action_trigger_type"), nullable=False)
    trigger_severity_min = Column(
        ExistingEnum(FleetNotificationSeverity, name="fleet_notification_severity"), nullable=False
    )
    breach_kind = Column(
        ExistingEnum(FleetActionBreachKind, name="fleet_action_policy_breach_kind"), nullable=True
    )
    action = Column(ExistingEnum(FleetActionPolicyAction, name="fleet_action_policy_action"), nullable=False)
    cooldown_seconds = Column(Integer, nullable=False, default=300, server_default="300")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FleetPolicyExecution(Base):
    __tablename__ = "fleet_policy_executions"
    __table_args__ = (Index("ix_fleet_policy_executions_client_created", "client_id", "created_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(GUID(), ForeignKey("fleet_action_policies.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    event_id = Column(GUID(), nullable=False)
    action = Column(String(64), nullable=False)
    status = Column(
        ExistingEnum(FleetPolicyExecutionStatus, name="fleet_policy_execution_status"), nullable=False
    )
    reason = Column(Text, nullable=True)
    dedupe_key = Column(String(256), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FleetNotificationOutbox(Base):
    __tablename__ = "fleet_notification_outbox"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    event_ref_type = Column(String(64), nullable=False)
    event_ref_id = Column(GUID(), nullable=False)
    payload_redacted = Column(JSON, nullable=True)
    channels_attempted = Column(JSON, nullable=True)
    status = Column(
        ExistingEnum(FleetNotificationOutboxStatus, name="fleet_notification_outbox_status"), nullable=False
    )
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    delivery_message_id = Column(String(256), nullable=True)
    last_status = Column(String(32), nullable=True)
    last_response_status = Column(Integer, nullable=True)
    last_response_body = Column(Text, nullable=True)
    dedupe_key = Column(String(256), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True, index=True)
    owner_type = Column(String(32), nullable=False)
    owner_id = Column(GUID(), nullable=False, index=True)
    url = Column(Text, nullable=False)
    secret = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    allowed_events = Column(JSON, nullable=True)
    retry_policy = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class WebhookDeliveryAttempt(Base):
    __tablename__ = "webhook_delivery_attempts"
    __table_args__ = (
        Index("ix_webhook_delivery_attempts_endpoint_event", "endpoint_id", "event_id"),
        Index("ix_webhook_delivery_attempts_dedupe", "dedupe_key"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    event_id = Column(GUID(), nullable=False, index=True)
    endpoint_id = Column(GUID(), nullable=False, index=True)
    attempt_no = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)
    http_status = Column(Integer, nullable=True)
    response_body_snippet = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    dedupe_key = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class WebhookNonceRecord(Base):
    __tablename__ = "webhook_nonce_store"

    nonce = Column(String(64), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class NotificationDeliveryLog(Base):
    __tablename__ = "notification_delivery_logs"
    __table_args__ = (Index("ix_notification_delivery_logs_channel_status", "channel", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True, index=True)
    channel = Column(String(32), nullable=False)
    provider = Column(String(64), nullable=False)
    message_id = Column(String(128), nullable=False)
    recipient = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False)
    error_code = Column(String(64), nullable=True)
    payload_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class FleetPushSubscription(Base):
    __tablename__ = "fleet_push_subscriptions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    employee_id = Column(GUID(), nullable=True, index=True)
    endpoint = Column(String(1024), nullable=False)
    p256dh = Column(String(256), nullable=False)
    auth = Column(String(256), nullable=False)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")


class FuelAnomaly(Base):
    __tablename__ = "fuel_anomalies"
    __table_args__ = (
        Index("ix_fuel_anomalies_client_status_ts", "client_id", "status", "occurred_at"),
        Index("ix_fuel_anomalies_card_ts", "card_id", "occurred_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    card_id = Column(GUID(), ForeignKey("fuel_cards.id"), nullable=True, index=True)
    group_id = Column(GUID(), ForeignKey("fuel_card_groups.id"), nullable=True, index=True)
    tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True, index=True)
    anomaly_type = Column(ExistingEnum(FuelAnomalyType, name="fuel_anomaly_type"), nullable=False)
    severity = Column(ExistingEnum(FleetNotificationSeverity, name="fleet_notification_severity"), nullable=False)
    score = Column(Numeric, nullable=False)
    baseline = Column(JSON, nullable=True)
    details = Column(JSON, nullable=True)
    status = Column(ExistingEnum(FuelAnomalyStatus, name="fuel_anomaly_status"), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class FuelLimitEscalation(Base):
    __tablename__ = "fuel_limit_escalations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    breach_id = Column(GUID(), ForeignKey("fuel_limit_breaches.id"), nullable=False, index=True)
    action = Column(
        ExistingEnum(FuelLimitEscalationAction, name="fuel_limit_escalation_action"), nullable=False
    )
    status = Column(ExistingEnum(FuelLimitEscalationStatus, name="fuel_limit_escalation_status"), nullable=False)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelLimit(Base):
    __tablename__ = "fuel_limits"
    __table_args__ = (
        Index("ix_fuel_limits_scope_active", "tenant_id", "client_id", "scope_type", "scope_id", "active"),
        Index("ix_fuel_limits_validity", "valid_from", "valid_to"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    scope_type = Column(ExistingEnum(FuelLimitScopeType, name="fuel_limit_scope_type"), nullable=False)
    scope_id = Column(String(64), nullable=True)
    fuel_type_code = Column(ExistingEnum(FuelType, name="fuel_type"), nullable=True)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=True, index=True)
    station_network_id = Column(
        GUID(),
        ForeignKey("fuel_station_networks.id"),
        nullable=True,
        index=True,
    )
    limit_type = Column(ExistingEnum(FuelLimitType, name="fuel_limit_type"), nullable=False)
    period = Column(ExistingEnum(FuelLimitPeriod, name="fuel_limit_period"), nullable=False)
    value = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=True)
    amount_limit = Column(Numeric, nullable=True)
    volume_limit_liters = Column(Numeric, nullable=True)
    categories = Column(JSON, nullable=True)
    stations_allowlist = Column(JSON, nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    meta = Column(JSON, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    effective_from = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    time_window_start = Column(Time, nullable=True)
    time_window_end = Column(Time, nullable=True)
    timezone = Column(String(64), nullable=False, default="Europe/Moscow", server_default="Europe/Moscow")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelRiskProfile(Base):
    __tablename__ = "fuel_risk_profiles"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(String(64), ForeignKey("risk_policies.id"), nullable=False)
    thresholds_override = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelRiskShadowEvent(Base):
    __tablename__ = "fuel_risk_shadow_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False, index=True)
    decision = Column(String(32), nullable=False)
    score = Column(Integer, nullable=True)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelAnomalyEvent(Base):
    __tablename__ = "fuel_anomaly_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelAnalyticsEvent(Base):
    __tablename__ = "fuel_analytics_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False, index=True)
    signal_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelMisuseSignal(Base):
    __tablename__ = "fuel_misuse_signals"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False, index=True)
    signal = Column(String(64), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelStationOutlier(Base):
    __tablename__ = "fuel_station_outliers"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    value = Column(BigInteger, nullable=True)
    baseline = Column(BigInteger, nullable=True)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelFraudSignal(Base):
    __tablename__ = "fuel_fraud_signals"
    __table_args__ = (
        Index("ix_fuel_fraud_signals_client_ts", "client_id", "ts"),
        Index("ix_fuel_fraud_signals_vehicle_ts", "vehicle_id", "ts"),
        Index("ix_fuel_fraud_signals_station_ts", "station_id", "ts"),
        Index("ix_fuel_fraud_signals_signal_ts", "signal_type", "ts"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    signal_type = Column(ExistingEnum(FuelFraudSignalType, name="fuel_fraud_signal_type"), nullable=False)
    severity = Column(Integer, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True, index=True)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=True, index=True)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True, index=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True, index=True)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=True, index=True)
    network_id = Column(GUID(), ForeignKey("fuel_networks.id"), nullable=True, index=True)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StationReputationDaily(Base):
    __tablename__ = "station_reputation_daily"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    network_id = Column(GUID(), ForeignKey("fuel_networks.id"), nullable=False, index=True)
    station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    decline_count = Column(Integer, nullable=False, default=0, server_default="0")
    risk_block_count = Column(Integer, nullable=False, default=0, server_default="0")
    avg_liters = Column(Integer, nullable=True)
    avg_amount = Column(Integer, nullable=True)
    outlier_score = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "FuelCard",
    "FuelCardGroup",
    "FuelCardGroupStatus",
    "FuelCardStatus",
    "FuelCardStatusEvent",
    "FuelCardStatusEventActorType",
    "FleetActionBreachKind",
    "FleetActionPolicy",
    "FleetActionPolicyAction",
    "FleetActionPolicyScopeType",
    "FleetActionTriggerType",
    "FuelIngestJob",
    "FuelIngestJobStatus",
    "FuelLimit",
    "FuelLimitBreach",
    "FuelLimitBreachScopeType",
    "FuelLimitBreachStatus",
    "FuelLimitBreachType",
    "FuelLimitEscalation",
    "FuelLimitEscalationAction",
    "FuelLimitEscalationStatus",
    "FuelLimitPeriod",
    "FuelLimitCheckStatus",
    "FuelLimitScopeType",
    "FuelLimitType",
    "FuelAnomaly",
    "FuelAnomalyStatus",
    "FuelAnomalyType",
    "FleetNotificationChannel",
    "FleetNotificationChannelStatus",
    "FleetNotificationChannelType",
    "FleetNotificationEventType",
    "FleetNotificationOutbox",
    "FleetNotificationOutboxStatus",
    "FleetNotificationPolicy",
    "FleetNotificationPolicyScopeType",
    "FleetNotificationSeverity",
    "FleetPushSubscription",
    "NotificationDeliveryLog",
    "FleetPolicyExecution",
    "FleetPolicyExecutionStatus",
    "FuelMerchant",
    "FuelNetwork",
    "FuelNetworkStatus",
    "FuelProvider",
    "FuelProviderStatus",
    "FuelStationNetwork",
    "FuelStation",
    "FuelStationStatus",
    "FuelRiskProfile",
    "FuelRiskShadowEvent",
    "FuelAnomalyEvent",
    "FuelMisuseSignal",
    "FuelStationOutlier",
    "FuelFraudSignal",
    "FuelFraudSignalType",
    "WebhookDeliveryAttempt",
    "WebhookEndpoint",
    "WebhookNonceRecord",
    "StationReputationDaily",
    "FuelTransaction",
    "FuelTransactionStatus",
    "FuelType",
]
