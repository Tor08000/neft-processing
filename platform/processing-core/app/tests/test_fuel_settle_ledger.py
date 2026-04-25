from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domains.ledger.models import LedgerEntryV1
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelTransaction
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import reverse_fuel_tx, settle_fuel_tx
from app.tests._fuel_runtime_test_harness import (
    FUEL_SETTLEMENT_LEDGER_TEST_TABLES,
    fuel_runtime_session_context,
)


@pytest.fixture
def session():
    with fuel_runtime_session_context(tables=FUEL_SETTLEMENT_LEDGER_TEST_TABLES) as session:
        yield session


def _ensure_threshold_set(db) -> None:
    if db.get(RiskThresholdSet, "fuel-settle-ledger-thresholds"):
        return
    db.add(
        RiskThresholdSet(
            id="fuel-settle-ledger-thresholds",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=90,
            review_threshold=70,
            allow_threshold=0,
        )
    )
    db.commit()


def _seed_refs(db):
    _ensure_threshold_set(db)
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
    legacy_tx = session.query(FuelTransaction).filter(FuelTransaction.id == tx_id).one()
    assert legacy_tx.ledger_transaction_id is not None
    v1_entry = session.query(LedgerEntryV1).filter(LedgerEntryV1.id == settled.ledger_transaction_id).one()
    assert v1_entry.idempotency_key == f"fuel:capture:{tx_id}"
    entries = (
        session.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == legacy_tx.ledger_transaction_id)
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


def test_fuel_links_idempotent_on_settle_and_reverse(session):
    _seed_refs(session)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=500,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    tx_id = result.response.transaction_id

    settle_fuel_tx(session, transaction_id=tx_id)
    links = (
        session.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == tx_id)
        .all()
    )
    assert len(links) == 2
    assert any(link.link_type == MoneyFlowLinkType.POSTS for link in links)
    assert any(link.link_type == MoneyFlowLinkType.RELATES for link in links)

    settle_fuel_tx(session, transaction_id=tx_id)
    links_after_retry = (
        session.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == tx_id)
        .all()
    )
    assert len(links_after_retry) == 2

    reverse_fuel_tx(session, transaction_id=tx_id)
    links_after_reverse = (
        session.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == tx_id)
        .all()
    )
    assert len(links_after_reverse) == 3

    reverse_fuel_tx(session, transaction_id=tx_id)
    links_after_reverse_retry = (
        session.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == tx_id)
        .all()
    )
    assert len(links_after_reverse_retry) == 3
