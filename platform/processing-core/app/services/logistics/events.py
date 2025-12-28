from __future__ import annotations

from app.models.audit_log import AuditVisibility
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from datetime import date, datetime
from enum import Enum

from app.services.audit_service import AuditService, RequestContext
from app.services.legal_graph.registry import LegalGraphRegistry

LOGISTICS_ORDER_CREATED = "LOGISTICS_ORDER_CREATED"
LOGISTICS_ORDER_STARTED = "LOGISTICS_ORDER_STARTED"
LOGISTICS_ORDER_COMPLETED = "LOGISTICS_ORDER_COMPLETED"
LOGISTICS_ORDER_CANCELLED = "LOGISTICS_ORDER_CANCELLED"
LOGISTICS_ROUTE_CREATED = "LOGISTICS_ROUTE_CREATED"
LOGISTICS_ROUTE_ACTIVATED = "LOGISTICS_ROUTE_ACTIVATED"
LOGISTICS_STOP_ARRIVED = "LOGISTICS_STOP_ARRIVED"
LOGISTICS_STOP_DEPARTED = "LOGISTICS_STOP_DEPARTED"
LOGISTICS_TRACKING_EVENT_INGESTED = "LOGISTICS_TRACKING_EVENT_INGESTED"
LOGISTICS_ETA_COMPUTED = "LOGISTICS_ETA_COMPUTED"


def audit_event(
    db,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
    request_ctx: RequestContext | None,
) -> None:
    serialized_payload = _serialize_payload(payload)
    AuditService(db).audit(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=event_type,
        visibility=AuditVisibility.INTERNAL,
        after=serialized_payload,
        request_ctx=request_ctx,
    )


def register_order_node(db, *, tenant_id: int, order_id: str, request_ctx: RequestContext | None) -> None:
    LegalGraphRegistry(db, request_ctx=request_ctx).get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_ORDER,
        ref_id=order_id,
        ref_table="logistics_orders",
    )


def register_route_node(
    db,
    *,
    tenant_id: int,
    order_id: str,
    route_id: str,
    request_ctx: RequestContext | None,
) -> None:
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    order_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_ORDER,
        ref_id=order_id,
        ref_table="logistics_orders",
    )
    route_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_ROUTE,
        ref_id=route_id,
        ref_table="logistics_routes",
    )
    registry.link(
        tenant_id=tenant_id,
        src_node_id=str(order_node.node.id),
        dst_node_id=str(route_node.node.id),
        edge_type=LegalEdgeType.INCLUDES,
        meta={"relation": "ORDER_INCLUDES_ROUTE"},
    )


def register_stop_node(
    db,
    *,
    tenant_id: int,
    route_id: str,
    stop_id: str,
    request_ctx: RequestContext | None,
) -> None:
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    route_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_ROUTE,
        ref_id=route_id,
        ref_table="logistics_routes",
    )
    stop_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_STOP,
        ref_id=stop_id,
        ref_table="logistics_stops",
    )
    registry.link(
        tenant_id=tenant_id,
        src_node_id=str(route_node.node.id),
        dst_node_id=str(stop_node.node.id),
        edge_type=LegalEdgeType.INCLUDES,
        meta={"relation": "ROUTE_INCLUDES_STOP"},
    )


def link_stop_relations(
    db,
    *,
    tenant_id: int,
    stop_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    fuel_tx_id: str | None,
    request_ctx: RequestContext | None,
) -> None:
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    stop_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.LOGISTICS_STOP,
        ref_id=stop_id,
        ref_table="logistics_stops",
    )

    if vehicle_id:
        vehicle_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.VEHICLE,
            ref_id=vehicle_id,
            ref_table="fleet_vehicles",
        )
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(stop_node.node.id),
            dst_node_id=str(vehicle_node.node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "STOP_RELATES_TO_VEHICLE"},
        )
    if driver_id:
        driver_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.DRIVER,
            ref_id=driver_id,
            ref_table="fleet_drivers",
        )
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(stop_node.node.id),
            dst_node_id=str(driver_node.node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "STOP_RELATES_TO_DRIVER"},
        )
    if fuel_tx_id:
        fuel_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.FUEL_TRANSACTION,
            ref_id=fuel_tx_id,
            ref_table="fuel_transactions",
        )
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(stop_node.node.id),
            dst_node_id=str(fuel_node.node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "STOP_RELATES_TO_FUEL_TX"},
        )


def _serialize_payload(payload: dict) -> dict:
    return {key: _serialize_value(value) for key, value in payload.items()}


def _serialize_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]
    return value


__all__ = [
    "LOGISTICS_ORDER_CREATED",
    "LOGISTICS_ORDER_STARTED",
    "LOGISTICS_ORDER_COMPLETED",
    "LOGISTICS_ORDER_CANCELLED",
    "LOGISTICS_ROUTE_CREATED",
    "LOGISTICS_ROUTE_ACTIVATED",
    "LOGISTICS_STOP_ARRIVED",
    "LOGISTICS_STOP_DEPARTED",
    "LOGISTICS_TRACKING_EVENT_INGESTED",
    "LOGISTICS_ETA_COMPUTED",
    "audit_event",
    "register_order_node",
    "register_route_node",
    "register_stop_node",
    "link_stop_relations",
]
