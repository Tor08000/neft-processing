from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.billing_summary import BillingSummaryStatus
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelStationNetwork
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.billing.daily import finalize_billing_day, run_billing_daily
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import settle_fuel_tx
from app.services.invoicing.monthly import run_invoice_monthly


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_refs(db):
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
    monkeypatch.setattr(settings, "NEFT_BILLING_DAILY_ENABLED", True)

    card, vehicle, station = _seed_refs(session)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
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

    billing_date = datetime.now(timezone.utc).date()
    summaries = run_billing_daily(target_date=billing_date, session=session)
    for summary in summaries:
        summary.status = BillingSummaryStatus.FINALIZED
    session.commit()
    finalize_billing_day(
        billing_date,
        session=session,
        now=datetime.now(timezone.utc) + timedelta(days=2),
    )

    outcome = run_invoice_monthly(target_month=billing_date.replace(day=1), session=session)
    assert outcome.invoices
    invoice_id = outcome.invoices[0].id

    tx_node = session.query(LegalNode).filter(LegalNode.ref_id == tx_id).one()
    card_node = session.query(LegalNode).filter(LegalNode.ref_id == str(card.id)).one()
    vehicle_node = session.query(LegalNode).filter(LegalNode.ref_id == str(vehicle.id)).one()
    station_node = session.query(LegalNode).filter(LegalNode.ref_id == str(station.id)).one()
    risk_node = session.query(LegalNode).filter(LegalNode.node_type == LegalNodeType.RISK_DECISION).one()
    invoice_node = session.query(LegalNode).filter(LegalNode.ref_id == str(invoice_id)).one()

    edge_types = {
        (edge.src_node_id, edge.dst_node_id): edge.edge_type
        for edge in session.query(LegalEdge).all()
    }
    assert edge_types[(tx_node.id, card_node.id)] == LegalEdgeType.RELATES_TO
    assert edge_types[(tx_node.id, vehicle_node.id)] == LegalEdgeType.RELATES_TO
    assert edge_types[(tx_node.id, station_node.id)] == LegalEdgeType.RELATES_TO
    assert edge_types[(tx_node.id, risk_node.id)] == LegalEdgeType.GATED_BY_RISK
    assert edge_types[(tx_node.id, invoice_node.id)] == LegalEdgeType.RELATES_TO
