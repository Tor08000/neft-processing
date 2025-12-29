from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class DriverBehaviorLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class StationTrustLevel(str, Enum):
    TRUSTED = "TRUSTED"
    WATCHLIST = "WATCHLIST"
    BLACKLIST = "BLACKLIST"


class FIDriverDaily(Base):
    __tablename__ = "fi_driver_daily"
    __table_args__ = (
        UniqueConstraint("tenant_id", "driver_id", "day", name="uq_fi_driver_daily_tenant_driver_day"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    driver_id = Column(GUID(), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    fuel_tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    fuel_volume_ml = Column(BigInteger, nullable=False, default=0, server_default="0")
    fuel_amount_minor = Column(BigInteger, nullable=False, default=0, server_default="0")
    night_fuel_tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    off_route_fuel_count = Column(Integer, nullable=False, default=0, server_default="0")
    route_deviation_count = Column(Integer, nullable=False, default=0, server_default="0")
    review_required_count = Column(Integer, nullable=False, default=0, server_default="0")
    risk_block_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FIVehicleDaily(Base):
    __tablename__ = "fi_vehicle_daily"
    __table_args__ = (
        UniqueConstraint("tenant_id", "vehicle_id", "day", name="uq_fi_vehicle_daily_tenant_vehicle_day"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    vehicle_id = Column(GUID(), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    fuel_volume_ml = Column(BigInteger, nullable=False, default=0, server_default="0")
    fuel_amount_minor = Column(BigInteger, nullable=False, default=0, server_default="0")
    distance_km_estimate = Column(Float, nullable=True)
    fuel_per_100km_ml = Column(Float, nullable=True)
    off_route_count = Column(Integer, nullable=False, default=0, server_default="0")
    tank_sanity_exceeded_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FIStationDaily(Base):
    __tablename__ = "fi_station_daily"
    __table_args__ = (
        UniqueConstraint("tenant_id", "station_id", "day", name="uq_fi_station_daily_tenant_station_day"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    network_id = Column(GUID(), nullable=True, index=True)
    station_id = Column(GUID(), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    distinct_cards_count = Column(Integer, nullable=False, default=0, server_default="0")
    distinct_drivers_count = Column(Integer, nullable=False, default=0, server_default="0")
    avg_volume_ml = Column(BigInteger, nullable=True)
    avg_amount_minor = Column(BigInteger, nullable=True)
    risk_block_count = Column(Integer, nullable=False, default=0, server_default="0")
    decline_count = Column(Integer, nullable=False, default=0, server_default="0")
    burst_events_count = Column(Integer, nullable=False, default=0, server_default="0")
    outlier_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FIDriverScore(Base):
    __tablename__ = "fi_driver_score"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    driver_id = Column(GUID(), nullable=False, index=True)
    computed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    window_days = Column(Integer, nullable=False, index=True)
    score = Column(Integer, nullable=False)
    level = Column(ExistingEnum(DriverBehaviorLevel, name="fi_driver_behavior_level"), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FIVehicleEfficiencyScore(Base):
    __tablename__ = "fi_vehicle_efficiency_score"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    vehicle_id = Column(GUID(), nullable=False, index=True)
    computed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    window_days = Column(Integer, nullable=False, index=True)
    efficiency_score = Column(Integer, nullable=True)
    baseline_ml_per_100km = Column(Float, nullable=True)
    actual_ml_per_100km = Column(Float, nullable=True)
    delta_pct = Column(Float, nullable=True)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FIStationTrustScore(Base):
    __tablename__ = "fi_station_trust_score"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    station_id = Column(GUID(), nullable=False, index=True)
    network_id = Column(GUID(), nullable=True, index=True)
    computed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    window_days = Column(Integer, nullable=False, index=True)
    trust_score = Column(Integer, nullable=False)
    level = Column(ExistingEnum(StationTrustLevel, name="fi_station_trust_level"), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "DriverBehaviorLevel",
    "StationTrustLevel",
    "FIDriverDaily",
    "FIVehicleDaily",
    "FIStationDaily",
    "FIDriverScore",
    "FIVehicleEfficiencyScore",
    "FIStationTrustScore",
]
