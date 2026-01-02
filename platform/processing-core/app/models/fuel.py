from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
)

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class FuelCardStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class FuelStationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelNetworkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FuelTransactionStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DECLINED = "DECLINED"
    REVERSED = "REVERSED"
    SETTLED = "SETTLED"


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
    issued_at = Column(DateTime(timezone=True), nullable=True)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
    currency = Column(String(3), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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


class FuelStationNetwork(Base):
    __tablename__ = "fuel_station_networks"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    name = Column(String(128), nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelStation(Base):
    __tablename__ = "fuel_stations"
    __table_args__ = (
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
    lat = Column(String(32), nullable=True)
    lon = Column(String(32), nullable=True)
    mcc = Column(String(8), nullable=True)
    station_code = Column(String(64), nullable=True, index=True)
    status = Column(ExistingEnum(FuelStationStatus, name="fuel_station_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelTransaction(Base):
    __tablename__ = "fuel_transactions"
    __table_args__ = (
        Index("ix_fuel_transactions_client_time", "client_id", "occurred_at"),
        Index("ix_fuel_transactions_card_time", "card_id", "occurred_at"),
        Index("ix_fuel_transactions_vehicle_time", "vehicle_id", "occurred_at"),
        Index("ix_fuel_transactions_status_time", "status", "occurred_at"),
        Index("ix_fuel_transactions_external_ref", "external_ref"),
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
    decline_code = Column(String(64), nullable=True)
    risk_decision_id = Column(GUID(), ForeignKey("risk_decisions.id"), nullable=True)
    ledger_transaction_id = Column(
        GUID(), ForeignKey("internal_ledger_transactions.id"), nullable=True
    )
    external_ref = Column(String(128), nullable=True)
    external_settlement_ref = Column(String(128), nullable=True)
    external_reverse_ref = Column(String(128), nullable=True)
    amount = Column(Numeric, nullable=True)
    volume_liters = Column(Numeric, nullable=True)
    category = Column(String(128), nullable=True)
    merchant_name = Column(String(256), nullable=True)
    station_external_id = Column(String(128), nullable=True)
    location = Column(String(256), nullable=True)
    raw_payload_redacted = Column(JSON, nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    meta = Column(JSON, nullable=True)
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
    policy_id = Column(GUID(), ForeignKey("risk_policies.id"), nullable=False)
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
    "FuelLimit",
    "FuelLimitPeriod",
    "FuelLimitScopeType",
    "FuelLimitType",
    "FuelNetwork",
    "FuelNetworkStatus",
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
    "StationReputationDaily",
    "FuelTransaction",
    "FuelTransactionStatus",
    "FuelType",
]
