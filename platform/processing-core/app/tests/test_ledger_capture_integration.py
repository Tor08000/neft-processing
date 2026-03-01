from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.domains.ledger.models import LedgerAccountBalanceV1, LedgerAccountV1, LedgerEntryV1, LedgerLineV1
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FleetOfflineProfile,
    FuelCard,
    FuelCardGroup,
    FuelCardStatus,
    FuelNetwork,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.schemas.fuel import DeclineCode
from app.services.fuel.settlement import FuelSettlementError, settle_fuel_tx


@pytest.fixture(autouse=True)
def _setup_db():
    tables = [
        FuelNetwork.__table__,
        FuelStation.__table__,
        FuelCardGroup.__table__,
        FleetOfflineProfile.__table__,
        FleetVehicle.__table__,
        InternalLedgerAccount.__table__,
        InternalLedgerTransaction.__table__,
        FuelCard.__table__,
        FuelTransaction.__table__,
        LedgerAccountV1.__table__,
        LedgerAccountBalanceV1.__table__,
        LedgerEntryV1.__table__,
        LedgerLineV1.__table__,
        InternalLedgerEntry.__table__,
    ]
    Base.metadata.drop_all(bind=engine, tables=tables)
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _patch_side_effects(monkeypatch):
    monkeypatch.setattr("app.services.fuel.settlement._write_money_flow_links", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.fuel.settlement.apply_fuel_transaction_mileage", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.fuel.settlement.fuel_linker.auto_link_fuel_tx", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.fuel.settlement.events.audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.internal_ledger.InternalLedgerService._emit_audit_event", lambda *args, **kwargs: None)


def _seed_tx(db) -> str:
    network = FuelNetwork(id=str(uuid4()), name="NET-1", provider_code=f"net-{uuid4()}", status="ACTIVE")
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        name="Station",
        country="RU",
        region="SPB",
        city="SPB",
        station_code=f"ST-{uuid4()}",
        status="ACTIVE",
    )
    vehicle = FleetVehicle(
        id=str(uuid4()),
        tenant_id=1,
        client_id=str(uuid4()),
        plate_number=f"A{str(uuid4())[:5]}",
        tank_capacity_liters=60,
        status=FleetVehicleStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id=vehicle.client_id,
        card_token=f"card-{uuid4()}",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
    )
    tx = FuelTransaction(
        id=str(uuid4()),
        tenant_id=1,
        client_id=vehicle.client_id,
        card_id=card.id,
        vehicle_id=vehicle.id,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_ml=2000,
        unit_price_minor=500,
        amount_total_minor=1000,
        currency="RUB",
        status=FuelTransactionStatus.AUTHORIZED,
    )
    db.add_all([network, station, vehicle, card, tx])
    db.commit()
    return str(tx.id)


def _tx(db, tx_id: str) -> FuelTransaction:
    return db.query(FuelTransaction).filter(FuelTransaction.id == tx_id).one()


def test_capture_creates_balanced_ledger_entry_with_three_lines(session):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 100}
    session.commit()

    result = settle_fuel_tx(session, transaction_id=tx_id)

    entry = session.query(LedgerEntryV1).filter(LedgerEntryV1.id == str(result.ledger_transaction_id)).one()
    lines = session.query(LedgerLineV1).filter(LedgerLineV1.entry_id == entry.id).order_by(LedgerLineV1.line_no).all()
    assert len(lines) == 3
    debit = sum(Decimal(str(line.amount)) for line in lines if line.direction == "DEBIT")
    credit = sum(Decimal(str(line.amount)) for line in lines if line.direction == "CREDIT")
    assert debit == credit == Decimal("10.00")


def test_capture_replay_is_idempotent_and_returns_same_entry(session):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 0}
    session.commit()

    first = settle_fuel_tx(session, transaction_id=tx_id)
    second = settle_fuel_tx(session, transaction_id=tx_id)

    assert first.ledger_transaction_id == second.ledger_transaction_id
    count = session.query(LedgerEntryV1).filter(LedgerEntryV1.idempotency_key == f"fuel:capture:{tx_id}").count()
    assert count == 1


def test_capture_fee_split_amounts_are_correct(session):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 200}
    session.commit()

    result = settle_fuel_tx(session, transaction_id=tx_id)
    lines = session.query(LedgerLineV1).filter(LedgerLineV1.entry_id == str(result.ledger_transaction_id)).all()
    partner_credit = next(Decimal(str(line.amount)) for line in lines if line.direction == "CREDIT" and line.line_no == 2)
    fee_credit = next(Decimal(str(line.amount)) for line in lines if line.direction == "CREDIT" and line.line_no == 3)
    assert partner_credit == Decimal("8.00")
    assert fee_credit == Decimal("2.00")


def test_capture_rejects_negative_fee(session):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": -1}
    session.commit()

    with pytest.raises(FuelSettlementError) as exc:
        settle_fuel_tx(session, transaction_id=tx_id)
    assert exc.value.decline_code == DeclineCode.INVALID_REQUEST


def test_capture_rejects_fee_greater_than_gross(session):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 1001}
    session.commit()

    with pytest.raises(FuelSettlementError) as exc:
        settle_fuel_tx(session, transaction_id=tx_id)
    assert exc.value.decline_code == DeclineCode.INVALID_REQUEST


def test_capture_rolls_back_when_ledger_fails(session, monkeypatch):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 0}
    session.commit()

    def _boom(*args, **kwargs):
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "ledger.unbalanced", status_code=409)

    monkeypatch.setattr("app.services.fuel.settlement._post_capture_ledger_v1", _boom)

    with pytest.raises(FuelSettlementError):
        settle_fuel_tx(session, transaction_id=tx_id)

    session.rollback()
    current = _tx(session, tx_id)
    assert current.status == FuelTransactionStatus.AUTHORIZED
    assert session.query(InternalLedgerEntry).count() == 0


def test_capture_returns_409_for_ledger_idempotency_mismatch(session, monkeypatch):
    tx_id = _seed_tx(session)
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": str(uuid4()), "platform_fee_minor": 0}
    session.commit()

    def _mismatch(*args, **kwargs):
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "ledger idempotency mismatch", status_code=409)

    monkeypatch.setattr("app.services.fuel.settlement._post_capture_ledger_v1", _mismatch)

    with pytest.raises(FuelSettlementError) as exc:
        settle_fuel_tx(session, transaction_id=tx_id)
    assert exc.value.status_code == 409


def test_capture_dimensions_include_required_fields(session):
    tx_id = _seed_tx(session)
    partner_id = str(uuid4())
    tx = _tx(session, tx_id)
    tx.meta = {"partner_id": partner_id, "platform_fee_minor": 0, "merchant_id": "m-1", "contract_id": "ctr-1"}
    session.commit()

    result = settle_fuel_tx(session, transaction_id=tx_id)
    entry = session.query(LedgerEntryV1).filter(LedgerEntryV1.id == str(result.ledger_transaction_id)).one()
    dims = entry.dimensions or {}
    assert dims.get("client_id") == tx.client_id
    assert dims.get("partner_id") == partner_id
    assert dims.get("fuel_tx_id") == tx_id
