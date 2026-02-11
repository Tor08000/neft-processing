from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func, text

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class LogisticsOrderType(str, Enum):
    DELIVERY = "DELIVERY"
    SERVICE = "SERVICE"
    TRIP = "TRIP"


class LogisticsOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LogisticsRouteStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class LogisticsStopType(str, Enum):
    START = "START"
    WAYPOINT = "WAYPOINT"
    FUEL = "FUEL"
    DELIVERY = "DELIVERY"
    END = "END"


class LogisticsStopStatus(str, Enum):
    PENDING = "PENDING"
    ARRIVED = "ARRIVED"
    DEPARTED = "DEPARTED"
    SKIPPED = "SKIPPED"


class LogisticsTrackingEventType(str, Enum):
    LOCATION = "LOCATION"
    STATUS_CHANGE = "STATUS_CHANGE"
    STOP_ARRIVAL = "STOP_ARRIVAL"
    STOP_DEPARTURE = "STOP_DEPARTURE"
    FUEL_STOP_LINKED = "FUEL_STOP_LINKED"


class LogisticsETAMethod(str, Enum):
    PLANNED = "PLANNED"
    SIMPLE_SPEED = "SIMPLE_SPEED"
    LAST_KNOWN = "LAST_KNOWN"
    HISTORICAL = "HISTORICAL"


class LogisticsDeviationEventType(str, Enum):
    OFF_ROUTE = "OFF_ROUTE"
    BACK_ON_ROUTE = "BACK_ON_ROUTE"
    STOP_OUT_OF_RADIUS = "STOP_OUT_OF_RADIUS"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"


class LogisticsDeviationSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LogisticsFuelRouteLinkType(str, Enum):
    AUTO_MATCH = "AUTO_MATCH"
    MANUAL = "MANUAL"
    PROVIDER = "PROVIDER"


class LogisticsNavigatorExplainType(str, Enum):
    ETA = "ETA"
    DEVIATION = "DEVIATION"


class LogisticsRiskSignalType(str, Enum):
    FUEL_OFF_ROUTE = "FUEL_OFF_ROUTE"
    FUEL_STOP_MISMATCH = "FUEL_STOP_MISMATCH"
    ROUTE_DEVIATION_HIGH = "ROUTE_DEVIATION_HIGH"
    ETA_ANOMALY = "ETA_ANOMALY"
    VELOCITY_ANOMALY = "VELOCITY_ANOMALY"


class LogisticsFuelLinkReason(str, Enum):
    TIME_WINDOW_MATCH = "TIME_WINDOW_MATCH"
    ROUTE_PROXIMITY_MATCH = "ROUTE_PROXIMITY_MATCH"
    STATION_ON_ROUTE = "STATION_ON_ROUTE"
    MANUAL_LINK = "MANUAL_LINK"


class LogisticsFuelLinkedBy(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"


class LogisticsFuelAlertType(str, Enum):
    OUT_OF_TIME_WINDOW = "OUT_OF_TIME_WINDOW"
    OUT_OF_ROUTE = "OUT_OF_ROUTE"
    HIGH_CONSUMPTION = "HIGH_CONSUMPTION"


class LogisticsFuelAlertSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class LogisticsFuelAlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    CLOSED = "CLOSED"


class LogisticsOrder(Base):
    __tablename__ = "logistics_orders"
    __table_args__ = (
        Index("ix_logistics_orders_client_status", "client_id", "status"),
        Index("ix_logistics_orders_vehicle_status", "vehicle_id", "status"),
        Index("ix_logistics_orders_driver_status", "driver_id", "status"),
        Index("ix_logistics_orders_planned_start_at", "planned_start_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    order_type = Column(ExistingEnum(LogisticsOrderType, name="logistics_order_type"), nullable=False)
    status = Column(ExistingEnum(LogisticsOrderStatus, name="logistics_order_status"), nullable=False)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True)
    planned_start_at = Column(DateTime(timezone=True), nullable=True)
    planned_end_at = Column(DateTime(timezone=True), nullable=True)
    actual_start_at = Column(DateTime(timezone=True), nullable=True)
    actual_end_at = Column(DateTime(timezone=True), nullable=True)
    origin_text = Column(String(256), nullable=True)
    destination_text = Column(String(256), nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LogisticsRoute(Base):
    __tablename__ = "logistics_routes"
    __table_args__ = (
        UniqueConstraint("order_id", "version", name="uq_logistics_routes_order_version"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(ExistingEnum(LogisticsRouteStatus, name="logistics_route_status"), nullable=False)
    distance_km = Column(Float, nullable=True)
    planned_duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsRouteSnapshot(Base):
    __tablename__ = "logistics_route_snapshots"
    __table_args__ = (
        Index("ix_logistics_route_snapshots_route", "route_id", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False, index=True)
    route_id = Column(GUID(), ForeignKey("logistics_routes.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    geometry = Column(JSON, nullable=False)
    distance_km = Column(Float, nullable=False)
    eta_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsNavigatorExplain(Base):
    __tablename__ = "logistics_navigator_explains"
    __table_args__ = (
        Index("ix_logistics_navigator_explains_snapshot", "route_snapshot_id", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    route_snapshot_id = Column(GUID(), ForeignKey("logistics_route_snapshots.id"), nullable=False, index=True)
    type = Column(
        ExistingEnum(LogisticsNavigatorExplainType, name="logistics_navigator_explain_type"), nullable=False
    )
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsStop(Base):
    __tablename__ = "logistics_stops"
    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_logistics_stops_route_sequence"),
        Index("ix_logistics_stops_route_id", "route_id"),
        Index("ix_logistics_stops_status", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    route_id = Column(GUID(), ForeignKey("logistics_routes.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    stop_type = Column(ExistingEnum(LogisticsStopType, name="logistics_stop_type"), nullable=False)
    name = Column(String(128), nullable=True)
    address_text = Column(String(256), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    planned_arrival_at = Column(DateTime(timezone=True), nullable=True)
    planned_departure_at = Column(DateTime(timezone=True), nullable=True)
    actual_arrival_at = Column(DateTime(timezone=True), nullable=True)
    actual_departure_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(ExistingEnum(LogisticsStopStatus, name="logistics_stop_status"), nullable=False)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True)
    meta = Column(JSON, nullable=True)


class LogisticsTrackingEvent(Base):
    __tablename__ = "logistics_tracking_events"
    __table_args__ = (
        Index("ix_logistics_tracking_events_order_ts_desc", "order_id", text("ts DESC")),
        Index("ix_logistics_tracking_events_vehicle_ts_desc", "vehicle_id", text("ts DESC")),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False, index=True)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True)
    event_type = Column(ExistingEnum(LogisticsTrackingEventType, name="logistics_tracking_event_type"), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    odometer_km = Column(Float, nullable=True)
    stop_id = Column(GUID(), ForeignKey("logistics_stops.id"), nullable=True)
    status_from = Column(String(32), nullable=True)
    status_to = Column(String(32), nullable=True)
    meta = Column(JSON, nullable=True)


class LogisticsETASnapshot(Base):
    __tablename__ = "logistics_eta_snapshots"
    __table_args__ = (
        Index("ix_logistics_eta_snapshots_order_computed_desc", "order_id", text("computed_at DESC")),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False, index=True)
    computed_at = Column(DateTime(timezone=True), nullable=False)
    eta_end_at = Column(DateTime(timezone=True), nullable=False)
    eta_confidence = Column(Integer, nullable=False)
    method = Column(ExistingEnum(LogisticsETAMethod, name="logistics_eta_method"), nullable=False)
    inputs = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsRouteConstraint(Base):
    __tablename__ = "logistics_route_constraints"
    __table_args__ = (UniqueConstraint("route_id", name="uq_logistics_route_constraints_route_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    route_id = Column(GUID(), ForeignKey("logistics_routes.id"), nullable=False)
    max_route_deviation_m = Column(Integer, nullable=False)
    max_stop_radius_m = Column(Integer, nullable=False)
    allowed_fuel_window_minutes = Column(Integer, nullable=False)
    allowed_regions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsDeviationEvent(Base):
    __tablename__ = "logistics_deviation_events"
    __table_args__ = (
        Index("ix_logistics_deviation_events_order_ts", "order_id", "ts"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False)
    route_id = Column(GUID(), ForeignKey("logistics_routes.id"), nullable=False)
    event_type = Column(
        ExistingEnum(LogisticsDeviationEventType, name="logistics_deviation_event_type"),
        nullable=False,
    )
    ts = Column(DateTime(timezone=True), nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    distance_from_route_m = Column(Integer, nullable=True)
    stop_id = Column(GUID(), ForeignKey("logistics_stops.id"), nullable=True)
    severity = Column(
        ExistingEnum(LogisticsDeviationSeverity, name="logistics_deviation_severity"),
        nullable=False,
    )
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsETAAccuracy(Base):
    __tablename__ = "logistics_eta_accuracy"
    __table_args__ = (Index("ix_logistics_eta_accuracy_order_ts", "order_id", "computed_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False)
    eta_end_at = Column(DateTime(timezone=True), nullable=False)
    actual_end_at = Column(DateTime(timezone=True), nullable=True)
    error_minutes = Column(Integer, nullable=True)
    method = Column(ExistingEnum(LogisticsETAMethod, name="logistics_eta_method"), nullable=False)
    confidence = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FuelRouteLink(Base):
    __tablename__ = "fuel_route_links"
    __table_args__ = (
        Index("ix_fuel_route_links_order", "order_id"),
        UniqueConstraint("fuel_tx_id", name="uq_fuel_route_links_fuel_tx_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False)
    route_id = Column(GUID(), ForeignKey("logistics_routes.id"), nullable=True)
    stop_id = Column(GUID(), ForeignKey("logistics_stops.id"), nullable=True)
    link_type = Column(
        ExistingEnum(LogisticsFuelRouteLinkType, name="logistics_fuel_link_type"),
        nullable=False,
    )
    distance_to_stop_m = Column(Integer, nullable=True)
    time_delta_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsRiskSignal(Base):
    __tablename__ = "logistics_risk_signals"
    __table_args__ = (
        Index("ix_logistics_risk_signals_order_ts", "order_id", "ts"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=False)
    order_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False)
    vehicle_id = Column(GUID(), ForeignKey("fleet_vehicles.id"), nullable=True)
    driver_id = Column(GUID(), ForeignKey("fleet_drivers.id"), nullable=True)
    signal_type = Column(
        ExistingEnum(LogisticsRiskSignalType, name="logistics_risk_signal_type"),
        nullable=False,
    )
    severity = Column(Integer, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsFuelLink(Base):
    __tablename__ = "logistics_fuel_links"
    __table_args__ = (
        UniqueConstraint("fuel_tx_id", name="uq_logistics_fuel_links_fuel_tx_id"),
        Index("ix_logistics_fuel_links_trip_id", "trip_id"),
        Index("ix_logistics_fuel_links_client_created", "client_id", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    trip_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=False)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False)
    score = Column(Integer, nullable=False)
    reason = Column(ExistingEnum(LogisticsFuelLinkReason, name="logistics_fuel_link_reason"), nullable=False)
    linked_by = Column(ExistingEnum(LogisticsFuelLinkedBy, name="logistics_fuel_linked_by"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsFuelAlert(Base):
    __tablename__ = "logistics_fuel_alerts"
    __table_args__ = (
        Index("ix_logistics_fuel_alerts_client_created", "client_id", "created_at"),
        Index("ix_logistics_fuel_alerts_trip_id", "trip_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    trip_id = Column(GUID(), ForeignKey("logistics_orders.id"), nullable=True)
    fuel_tx_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=False, index=True)
    type = Column(ExistingEnum(LogisticsFuelAlertType, name="logistics_fuel_alert_type"), nullable=False)
    severity = Column(ExistingEnum(LogisticsFuelAlertSeverity, name="logistics_fuel_alert_severity"), nullable=False)
    title = Column(String(256), nullable=False)
    details = Column(String(1024), nullable=True)
    evidence = Column(JSON, nullable=True)
    status = Column(ExistingEnum(LogisticsFuelAlertStatus, name="logistics_fuel_alert_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "LogisticsOrder",
    "LogisticsOrderType",
    "LogisticsOrderStatus",
    "LogisticsRoute",
    "LogisticsRouteStatus",
    "LogisticsStop",
    "LogisticsStopStatus",
    "LogisticsStopType",
    "LogisticsTrackingEvent",
    "LogisticsTrackingEventType",
    "LogisticsETASnapshot",
    "LogisticsETAMethod",
    "LogisticsRouteConstraint",
    "LogisticsDeviationEvent",
    "LogisticsDeviationEventType",
    "LogisticsDeviationSeverity",
    "LogisticsETAAccuracy",
    "FuelRouteLink",
    "LogisticsFuelRouteLinkType",
    "LogisticsNavigatorExplain",
    "LogisticsNavigatorExplainType",
    "LogisticsRiskSignal",
    "LogisticsRiskSignalType",
    "LogisticsRouteSnapshot",
    "LogisticsFuelLink",
    "LogisticsFuelLinkReason",
    "LogisticsFuelLinkedBy",
    "LogisticsFuelAlert",
    "LogisticsFuelAlertType",
    "LogisticsFuelAlertSeverity",
    "LogisticsFuelAlertStatus",
]
