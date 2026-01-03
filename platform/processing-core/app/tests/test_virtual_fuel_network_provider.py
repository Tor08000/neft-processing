from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.fuel.jobs import poll_provider
from app.integrations.fuel.models import (
    FuelProviderAuthType,
    FuelProviderConnection,
    FuelProviderConnectionStatus,
)
from app.integrations.fuel.providers.virtual_network.store import VirtualNetworkStore
from app.models.cases import Case, CaseComment, CaseEvent, CaseEventType, CaseQueue, CaseSnapshot, CaseStatus
from app.models.decision_memory import DecisionMemoryRecord
from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationOutbox,
    FleetNotificationSeverity,
    FuelAnomaly,
    FuelAnomalyType,
    FuelCard,
    FuelCardStatus,
    FuelLimit,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
)

CONFIG_TEMPLATE = """
seed: 7
deterministic: true
stations:
  - station_id: "VN-0001"
    name: "Virtual Station Center"
    brand: "VirtualFuel"
    geo:
      lat: "55.7558"
      lon: "37.6176"
    region: "Moscow"
    city: "Moscow"
prices:
  VN-0001:
    AI95: "60.20"
"""


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def virtual_network_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tmp_path.joinpath("config.yaml").write_text(CONFIG_TEMPLATE, encoding="utf-8")
    monkeypatch.setenv("VIRTUAL_FUEL_NETWORK_DIR", str(tmp_path))
    return tmp_path


def _create_card(db: Session, *, client_id: str, alias: str) -> FuelCard:
    card = FuelCard(
        tenant_id=1,
        client_id=client_id,
        card_token=f"token-{alias}",
        card_alias=alias,
        status=FuelCardStatus.ACTIVE,
        currency="RUB",
    )
    db.add(card)
    db.flush()
    return card


def _create_connection(db: Session, *, client_id: str) -> FuelProviderConnection:
    connection = FuelProviderConnection(
        client_id=client_id,
        provider_code="virtual_fuel_network",
        status=FuelProviderConnectionStatus.ACTIVE,
        auth_type=FuelProviderAuthType.API_KEY,
        config={},
    )
    db.add(connection)
    db.flush()
    return connection


def _seed_network_refs(db: Session) -> None:
    network = db.query(FuelNetwork).filter(FuelNetwork.provider_code == "virtual_fuel_network").one_or_none()
    if not network:
        network = FuelNetwork(
            name="Virtual Fuel Network",
            provider_code="virtual_fuel_network",
            status=FuelNetworkStatus.ACTIVE,
        )
        db.add(network)
        db.flush()
    db.add(
        FuelStation(
            network_id=network.id,
            name="Virtual Station Center",
            station_code="VN-0001",
            status=FuelStationStatus.ACTIVE,
        )
    )
    db.commit()


def _append_transactions(store: VirtualNetworkStore, rows: list[dict]) -> None:
    store.append_transactions(rows)


def test_virtual_network_golden_path(db_session: Session, virtual_network_dir: Path) -> None:
    client_id = str(uuid4())
    card = _create_card(db_session, client_id=client_id, alias="NEFT-00001234")
    connection = _create_connection(db_session, client_id=client_id)
    _seed_network_refs(db_session)

    db_session.add(
        FuelLimit(
            tenant_id=1,
            client_id=client_id,
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            limit_type=FuelLimitType.VOLUME,
            period=FuelLimitPeriod.DAILY,
            value=100,
            volume_limit_liters=Decimal("100"),
            active=True,
        )
    )
    db_session.add(
        FleetActionPolicy(
            client_id=client_id,
            scope_type=FleetActionPolicyScopeType.CLIENT,
            scope_id=None,
            trigger_type=FleetActionTriggerType.LIMIT_BREACH,
            trigger_severity_min=FleetNotificationSeverity.MEDIUM,
            breach_kind=FleetActionBreachKind.HARD,
            action=FleetActionPolicyAction.AUTO_BLOCK_CARD,
        )
    )
    db_session.add(
        FleetActionPolicy(
            client_id=client_id,
            scope_type=FleetActionPolicyScopeType.CLIENT,
            scope_id=None,
            trigger_type=FleetActionTriggerType.LIMIT_BREACH,
            trigger_severity_min=FleetNotificationSeverity.MEDIUM,
            breach_kind=FleetActionBreachKind.HARD,
            action=FleetActionPolicyAction.ESCALATE_CASE,
        )
    )
    db_session.commit()

    store = VirtualNetworkStore()
    now = datetime.now(timezone.utc)
    rows = [
        {
            "provider_tx_id": "VN-TX-1",
            "provider_card_id": card.card_alias,
            "occurred_at": (now - timedelta(minutes=20)).isoformat(),
            "amount": "2400",
            "currency": "RUB",
            "volume_liters": "40",
            "category": "FUEL",
            "merchant_name": "Virtual Station Center",
            "station_id": "VN-0001",
            "location": "Moscow",
            "raw_payload": {"card_alias": card.card_alias},
            "client_id": client_id,
        },
        {
            "provider_tx_id": "VN-TX-2",
            "provider_card_id": card.card_alias,
            "occurred_at": (now - timedelta(minutes=10)).isoformat(),
            "amount": "2400",
            "currency": "RUB",
            "volume_liters": "40",
            "category": "FUEL",
            "merchant_name": "Virtual Station Center",
            "station_id": "VN-0001",
            "location": "Moscow",
            "raw_payload": {"card_alias": card.card_alias},
            "client_id": client_id,
        },
        {
            "provider_tx_id": "VN-TX-3",
            "provider_card_id": card.card_alias,
            "occurred_at": now.isoformat(),
            "amount": "1800",
            "currency": "RUB",
            "volume_liters": "30",
            "category": "FUEL",
            "merchant_name": "Virtual Station Center",
            "station_id": "VN-0001",
            "location": "Moscow",
            "raw_payload": {"card_alias": card.card_alias},
            "client_id": client_id,
        },
    ]
    _append_transactions(store, rows)

    since = now - timedelta(hours=1)
    until = now + timedelta(hours=1)
    poll_provider(db_session, connection=connection, since=since, until=until)
    db_session.commit()

    tx_count = db_session.query(FuelTransaction).count()
    assert tx_count == 3

    card_after = db_session.query(FuelCard).filter(FuelCard.id == card.id).one()
    assert card_after.status == FuelCardStatus.BLOCKED

    outbox_count = db_session.query(FleetNotificationOutbox).count()
    assert outbox_count >= 1

    cases = db_session.query(Case).all()
    assert cases, "expected escalation case to be created"


def test_virtual_network_anomaly_injection(db_session: Session, virtual_network_dir: Path) -> None:
    client_id = str(uuid4())
    card = _create_card(db_session, client_id=client_id, alias="NEFT-009900")
    connection = _create_connection(db_session, client_id=client_id)
    _seed_network_refs(db_session)

    store = VirtualNetworkStore()
    now = datetime.now(timezone.utc)
    duplicate_id = "VN-DUP-1"
    rows = [
        {
            "provider_tx_id": duplicate_id,
            "provider_card_id": card.card_alias,
            "occurred_at": (now - timedelta(minutes=5)).isoformat(),
            "amount": "1200",
            "currency": "RUB",
            "volume_liters": "20",
            "category": "FUEL",
            "merchant_name": "Virtual Station Center",
            "station_id": "VN-0001",
            "location": "Moscow",
            "raw_payload": {"card_alias": card.card_alias, "virtual_anomalies": ["GEO_JUMP"]},
            "client_id": client_id,
        },
        {
            "provider_tx_id": duplicate_id,
            "provider_card_id": card.card_alias,
            "occurred_at": now.isoformat(),
            "amount": "1200",
            "currency": "RUB",
            "volume_liters": "20",
            "category": "FUEL",
            "merchant_name": "Virtual Station Center",
            "station_id": "VN-0001",
            "location": "Moscow",
            "raw_payload": {"card_alias": card.card_alias, "virtual_anomalies": ["OFF_HOURS"]},
            "client_id": client_id,
        },
    ]
    _append_transactions(store, rows)

    since = now - timedelta(hours=1)
    until = now + timedelta(hours=1)
    job = poll_provider(db_session, connection=connection, since=since, until=until)
    db_session.commit()

    assert job is not None
    assert job.deduped_count == 1

    anomalies = db_session.query(FuelAnomaly).all()
    anomaly_types = {anomaly.anomaly_type for anomaly in anomalies}
    assert FuelAnomalyType.GEO_DISTANCE in anomaly_types
    assert FuelAnomalyType.TIME_OF_DAY in anomaly_types
