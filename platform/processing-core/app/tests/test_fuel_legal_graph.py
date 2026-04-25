from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.config import settings
from app.models.billing_period import BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelStationNetwork
from app.models.operation import ProductType
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.billing_periods import BillingPeriodService, period_bounds_for_dates
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import settle_fuel_tx
from app.services.invoicing.monthly import run_invoice_monthly
from app.tests._fuel_runtime_test_harness import FUEL_BILLING_FEED_TEST_TABLES, fuel_runtime_session_context


@pytest.fixture
def session():
    with fuel_runtime_session_context(tables=FUEL_BILLING_FEED_TEST_TABLES) as db:
        yield db


def _ensure_threshold_set(db) -> None:
    if db.get(RiskThresholdSet, "fuel-legal-graph-thresholds"):
        payment_thresholds_present = True
    else:
        payment_thresholds_present = False
    if not payment_thresholds_present:
        db.add(
            RiskThresholdSet(
                id="fuel-legal-graph-thresholds",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=90,
                review_threshold=70,
                allow_threshold=0,
            )
        )
    if db.get(RiskThresholdSet, "fuel-legal-graph-invoice-thresholds"):
        db.commit()
        return
    db.add(
        RiskThresholdSet(
            id="fuel-legal-graph-invoice-thresholds",
            subject_type=RiskSubjectType.INVOICE,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.INVOICE,
            block_threshold=90,
            review_threshold=70,
            allow_threshold=0,
        )
    )
    db.commit()


def _seed_refs(db):
    _ensure_threshold_set(db)
    network = FuelNetwork(id=str(uuid4()), name="NET-1", provider_code="net-1", status="ACTIVE")
    station_network = FuelStationNetwork(id=str(uuid4()), name="Main Network", meta={"brand": "Main"})
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        station_network_id=station_network.id,
        name="Station",
        country="RU",
        region="SPB",
        city="SPB",
        station_code="ST-1",
        status="ACTIVE",
    )
    vehicle = FleetVehicle(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        plate_number="A123BC",
        tank_capacity_liters=60,
        status=FleetVehicleStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
    )
    db.add_all([network, station_network, station, vehicle, card])
    db.commit()
    return card, vehicle, station


def test_fuel_legal_graph_edges(session, monkeypatch):
    monkeypatch.setattr(settings, "NEFT_INVOICE_MONTHLY_ENABLED", True)

    card, vehicle, station = _seed_refs(session)
    occurred_at = datetime(2024, 6, 15, 12, tzinfo=timezone.utc)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=occurred_at,
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    tx_id = result.response.transaction_id
    settle_fuel_tx(session, transaction_id=tx_id)

    billing_date = date(2024, 6, 15)
    period_from = billing_date.replace(day=1)
    period_to = date(2024, 6, 30)
    period_start, period_end = period_bounds_for_dates(date_from=period_from, date_to=period_to, tz="UTC")
    period = BillingPeriodService(session).get_or_create(
        period_type=BillingPeriodType.MONTHLY,
        start_at=period_start,
        end_at=period_end,
        tz="UTC",
    )
    session.add(
        BillingSummary(
            billing_date=billing_date,
            billing_period_id=period.id,
            client_id="client-1",
            merchant_id="net-1",
            product_type=ProductType.DIESEL,
            currency="RUB",
            total_amount=500,
            total_quantity=Decimal("5.0"),
            operations_count=1,
            commission_amount=0,
            status=BillingSummaryStatus.FINALIZED,
        )
    )
    session.commit()

    outcome = run_invoice_monthly(target_month=period_from, session=session)
    assert outcome.invoices
    invoice_id = outcome.invoices[0].id

    tx_node = (
        session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.FUEL_TRANSACTION)
        .filter(LegalNode.ref_id == tx_id)
        .one()
    )
    card_node = (
        session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.CARD)
        .filter(LegalNode.ref_id == str(card.id))
        .one()
    )
    vehicle_node = (
        session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.VEHICLE)
        .filter(LegalNode.ref_id == str(vehicle.id))
        .one()
    )
    station_node = (
        session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.FUEL_STATION)
        .filter(LegalNode.ref_id == str(station.id))
        .one()
    )
    risk_node_ids = {
        node.id
        for node in session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.RISK_DECISION)
        .all()
    }
    invoice_node = (
        session.query(LegalNode)
        .filter(LegalNode.tenant_id == 1)
        .filter(LegalNode.node_type == LegalNodeType.INVOICE)
        .filter(LegalNode.ref_id == str(invoice_id))
        .one()
    )

    edge_types = {
        (edge.src_node_id, edge.dst_node_id): edge.edge_type
        for edge in session.query(LegalEdge).all()
    }
    assert edge_types[(tx_node.id, card_node.id)] == LegalEdgeType.RELATES_TO
    assert edge_types[(tx_node.id, vehicle_node.id)] == LegalEdgeType.RELATES_TO
    assert edge_types[(tx_node.id, station_node.id)] == LegalEdgeType.RELATES_TO
    assert any(
        edge_types.get((tx_node.id, risk_node_id)) == LegalEdgeType.GATED_BY_RISK
        for risk_node_id in risk_node_ids
    )
    assert edge_types[(tx_node.id, invoice_node.id)] == LegalEdgeType.RELATES_TO
