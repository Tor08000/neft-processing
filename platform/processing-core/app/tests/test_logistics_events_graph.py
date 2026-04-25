import os
from typing import Tuple
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models.audit_log import ActorType, AuditLog
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType
from app.services.audit_service import RequestContext
from app.services.logistics import events
from app.tests._logistics_route_harness import logistics_fuel_session_context, logistics_session_context


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    with logistics_session_context() as ctx:
        yield ctx


@pytest.fixture()
def fuel_db_session() -> Tuple[Session, sessionmaker]:
    with logistics_fuel_session_context() as ctx:
        yield ctx


def _ctx() -> RequestContext:
    return RequestContext(actor_type=ActorType.SYSTEM, tenant_id=1)


def _node(db: Session, *, node_type: LegalNodeType, ref_id: str) -> LegalNode:
    return (
        db.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == node_type)
        .filter(LegalNode.ref_id == ref_id)
        .one()
    )


def _edge(db: Session, *, src_node_id: str, dst_node_id: str, relation: str) -> LegalEdge:
    return (
        db.query(LegalEdge)
        .filter(LegalEdge.tenant_id == 1)
        .filter(LegalEdge.edge_type == LegalEdgeType.RELATES_TO)
        .filter(LegalEdge.src_node_id == src_node_id)
        .filter(LegalEdge.dst_node_id == dst_node_id)
        .filter(LegalEdge.meta["relation"].as_string() == relation)
        .one()
    )


def _audit_rows(db: Session, *, event_type: str) -> list[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.event_type == event_type).all()


def test_deviation_event_registers_audit_and_graph_artifacts(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    ctx = _ctx()
    order_id = str(uuid4())
    deviation_id = str(uuid4())

    events.audit_event(
        db,
        event_type=events.LOGISTICS_OFF_ROUTE_DETECTED,
        entity_type="logistics_deviation_event",
        entity_id=deviation_id,
        payload={"order_id": order_id, "event_type": "OFF_ROUTE"},
        request_ctx=ctx,
    )
    events.register_deviation_event_node(
        db,
        tenant_id=1,
        order_id=order_id,
        deviation_id=deviation_id,
        request_ctx=ctx,
    )

    domain_audit = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == events.LOGISTICS_OFF_ROUTE_DETECTED)
        .filter(AuditLog.entity_type == "logistics_deviation_event")
        .filter(AuditLog.entity_id == deviation_id)
        .one()
    )
    assert domain_audit.tenant_id == 1
    assert domain_audit.after["order_id"] == order_id

    order_node = _node(db, node_type=LegalNodeType.LOGISTICS_ORDER, ref_id=order_id)
    deviation_node = _node(db, node_type=LegalNodeType.FRAUD_SIGNAL, ref_id=deviation_id)
    assert deviation_node.ref_table == "logistics_deviation_events"

    edge = _edge(
        db,
        src_node_id=str(order_node.id),
        dst_node_id=str(deviation_node.id),
        relation="ORDER_RELATES_TO_LOGISTICS_DEVIATION",
    )
    assert edge.edge_type == LegalEdgeType.RELATES_TO
    assert any(
        row.after.get("meta", {}).get("relation") == "ORDER_RELATES_TO_LOGISTICS_DEVIATION"
        for row in _audit_rows(db, event_type="LEGAL_EDGE_CREATED")
    )


def test_risk_signal_registers_audit_and_graph_artifacts(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    ctx = _ctx()
    order_id = str(uuid4())
    signal_id = str(uuid4())

    events.audit_event(
        db,
        event_type=events.LOGISTICS_RISK_SIGNAL_EMITTED,
        entity_type="logistics_risk_signal",
        entity_id=signal_id,
        payload={"order_id": order_id, "signal_type": "FUEL_OFF_ROUTE", "severity": 90},
        request_ctx=ctx,
    )
    events.register_risk_signal_node(
        db,
        tenant_id=1,
        order_id=order_id,
        signal_id=signal_id,
        request_ctx=ctx,
    )

    domain_audit = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == events.LOGISTICS_RISK_SIGNAL_EMITTED)
        .filter(AuditLog.entity_type == "logistics_risk_signal")
        .filter(AuditLog.entity_id == signal_id)
        .one()
    )
    assert domain_audit.after["signal_type"] == "FUEL_OFF_ROUTE"

    order_node = _node(db, node_type=LegalNodeType.LOGISTICS_ORDER, ref_id=order_id)
    signal_node = _node(db, node_type=LegalNodeType.FRAUD_SIGNAL, ref_id=signal_id)
    assert signal_node.ref_table == "logistics_risk_signals"

    edge = _edge(
        db,
        src_node_id=str(order_node.id),
        dst_node_id=str(signal_node.id),
        relation="ORDER_RELATES_TO_LOGISTICS_RISK_SIGNAL",
    )
    assert edge.edge_type == LegalEdgeType.RELATES_TO
    assert any(
        row.after.get("meta", {}).get("relation") == "ORDER_RELATES_TO_LOGISTICS_RISK_SIGNAL"
        for row in _audit_rows(db, event_type="LEGAL_EDGE_CREATED")
    )


def test_fuel_link_registers_audit_and_stop_to_fuel_graph_relation(
    fuel_db_session: Tuple[Session, sessionmaker],
):
    db, _ = fuel_db_session
    ctx = _ctx()
    stop_id = str(uuid4())
    fuel_tx_id = str(uuid4())
    link_id = str(uuid4())

    events.audit_event(
        db,
        event_type=events.LOGISTICS_FUEL_LINK_CREATED,
        entity_type="fuel_route_link",
        entity_id=link_id,
        payload={"fuel_tx_id": fuel_tx_id, "stop_id": stop_id},
        request_ctx=ctx,
    )
    events.register_fuel_link_node(
        db,
        tenant_id=1,
        fuel_tx_id=fuel_tx_id,
        link_id=link_id,
        stop_id=stop_id,
        request_ctx=ctx,
    )

    domain_audit = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == events.LOGISTICS_FUEL_LINK_CREATED)
        .filter(AuditLog.entity_type == "fuel_route_link")
        .filter(AuditLog.entity_id == link_id)
        .one()
    )
    assert domain_audit.after["stop_id"] == stop_id
    assert domain_audit.after["fuel_tx_id"] == fuel_tx_id

    stop_node = _node(db, node_type=LegalNodeType.LOGISTICS_STOP, ref_id=stop_id)
    fuel_node = _node(db, node_type=LegalNodeType.FUEL_TRANSACTION, ref_id=fuel_tx_id)
    edge = _edge(
        db,
        src_node_id=str(stop_node.id),
        dst_node_id=str(fuel_node.id),
        relation="STOP_RELATES_TO_FUEL_TX",
    )
    assert edge.edge_type == LegalEdgeType.RELATES_TO
    assert (
        db.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.ref_id == link_id)
        .count()
        == 0
    )
    assert any(
        row.after.get("meta", {}).get("relation") == "STOP_RELATES_TO_FUEL_TX"
        for row in _audit_rows(db, event_type="LEGAL_EDGE_CREATED")
    )
