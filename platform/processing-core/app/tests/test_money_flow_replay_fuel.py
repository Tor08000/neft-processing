from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base
from app.domains.ledger.models import LedgerAccountBalanceV1, LedgerAccountV1, LedgerEntryV1, LedgerLineV1
from app.models.billing_period import BillingPeriodType
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod
from app.models.clearing_batch import ClearingBatch
from app.models.client_actions import ReconciliationRequest
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus, FuelTransaction, FuelTransactionStatus
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.services.billing_periods import BillingPeriodService, period_bounds_for_dates
from app.services.fuel.settlement import settle_fuel_tx
from app.services.money_flow.replay import MoneyReplayMode, MoneyReplayScope, run_money_flow_replay

FUEL_REPLAY_TEST_TABLES = [
    AuditLog.__table__,
    BillingPeriod.__table__,
    ClearingBatch.__table__,
    ReconciliationRequest.__table__,
    FuelNetwork.__table__,
    FuelStation.__table__,
    FuelCard.__table__,
    FuelTransaction.__table__,
    MoneyFlowLink.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerEntry.__table__,
    InternalLedgerTransaction.__table__,
    LedgerAccountV1.__table__,
    LedgerEntryV1.__table__,
    LedgerLineV1.__table__,
    LedgerAccountBalanceV1.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
]


def _build_session_factory() -> tuple[sessionmaker, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    for table in FUEL_REPLAY_TEST_TABLES:
        table.create(bind=engine)
    return SessionLocal, engine


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch):
    SessionLocal, engine = _build_session_factory()
    monkeypatch.setattr("app.services.fuel.settlement.apply_fuel_transaction_mileage", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.fuel.settlement.fuel_linker.auto_link_fuel_tx", lambda *args, **kwargs: None)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(FUEL_REPLAY_TEST_TABLES):
            table.drop(bind=engine)
        engine.dispose()


def _seed_fuel_refs(db):
    network = FuelNetwork(id=str(uuid4()), name="Net", provider_code="NET", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(
        network_id=network.id,
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="RU",
        city="SPB",
        lat="0",
        lon="0",
        status=FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
    )
    db.add_all([network, station, card])
    db.commit()
    return card, station, network


def _seed_authorized_fuel_tx(db: Session, *, card: FuelCard, station: FuelStation, network: FuelNetwork) -> FuelTransaction:
    transaction = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=card.id,
        vehicle_id=None,
        driver_id=None,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
        fuel_type="DIESEL",
        volume_ml=10000,
        unit_price_minor=500,
        amount_total_minor=5000,
        currency="RUB",
        status=FuelTransactionStatus.AUTHORIZED,
        external_ref=str(uuid4()),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def test_replay_fuel_dry_run_deterministic(session):
    card, station, network = _seed_fuel_refs(session)
    period_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2025, 1, 31, tzinfo=timezone.utc)
    period = BillingPeriodService(session).get_or_create(
        period_type=BillingPeriodType.MONTHLY,
        start_at=period_start,
        end_at=period_end,
        tz=settings.NEFT_BILLING_TZ,
    )

    fuel_tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=card.id,
        vehicle_id=None,
        driver_id=None,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
        fuel_type="DIESEL",
        volume_ml=15000,
        unit_price_minor=500,
        amount_total_minor=7500,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    session.add(fuel_tx)
    session.commit()

    first = run_money_flow_replay(
        session,
        client_id="client-1",
        billing_period_id=str(period.id),
        mode=MoneyReplayMode.DRY_RUN,
        scope=MoneyReplayScope.FUEL,
    )
    second = run_money_flow_replay(
        session,
        client_id="client-1",
        billing_period_id=str(period.id),
        mode=MoneyReplayMode.DRY_RUN,
        scope=MoneyReplayScope.FUEL,
    )

    assert first.recompute_hash == second.recompute_hash
    assert first.summary == {"tx_count": 1, "volume_ml": 15000, "amount_minor": 7500}


def test_replay_fuel_compare_no_diff_after_settle(session):
    card, station, network = _seed_fuel_refs(session)
    transaction = _seed_authorized_fuel_tx(session, card=card, station=station, network=network)
    tx_id = str(transaction.id)
    settle_fuel_tx(session, transaction_id=tx_id)

    period_start, period_end = period_bounds_for_dates(
        date_from=transaction.occurred_at.date(),
        date_to=transaction.occurred_at.date(),
        tz=settings.NEFT_BILLING_TZ,
    )
    period = BillingPeriodService(session).get_or_create(
        period_type=BillingPeriodType.DAILY,
        start_at=period_start,
        end_at=period_end,
        tz=settings.NEFT_BILLING_TZ,
    )

    links = (
        session.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == tx_id)
        .all()
    )
    assert any(link.link_type == MoneyFlowLinkType.POSTS for link in links)
    assert any(link.link_type == MoneyFlowLinkType.RELATES for link in links)

    replay = run_money_flow_replay(
        session,
        client_id="client-1",
        billing_period_id=str(period.id),
        mode=MoneyReplayMode.COMPARE,
        scope=MoneyReplayScope.FUEL,
    )
    assert replay.diff is not None
    assert replay.diff.missing_links_count == 0
    assert replay.diff.missing_ledger_postings == 0
    assert replay.diff.mismatched_totals == []
