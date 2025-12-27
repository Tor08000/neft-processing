from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import reverse_fuel_tx, settle_fuel_tx


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
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
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
    db.add_all([network, station, vehicle, card])
    db.commit()


def test_settle_and_reverse_balanced_entries(session):
    _seed_refs(session)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=2.0,
        unit_price=500,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    tx_id = result.response.transaction_id
    assert tx_id

    settled = settle_fuel_tx(session, transaction_id=tx_id)
    entries = (
        session.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == settled.ledger_transaction_id)
        .all()
    )
    assert len(entries) == 2
    debit = sum(
        entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT
    )
    credit = sum(
        entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT
    )
    assert debit == credit

    reversed_result = reverse_fuel_tx(session, transaction_id=tx_id)
    reversal_entries = (
        session.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == reversed_result.ledger_transaction_id)
        .all()
    )
    assert len(reversal_entries) == 2
