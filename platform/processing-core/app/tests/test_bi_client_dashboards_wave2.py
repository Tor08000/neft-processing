from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import bi as bi_dependencies
from app.db import Base, get_db
from app.main import app
from app.domains.documents.models import ClientDocument, DocumentEdoState, DocumentStatus, EdoStatus
from app.models.bi import (
    BiExportBatch,
    BiExportFormat,
    BiExportKind,
    BiExportStatus,
    BiMartClientSpend,
    BiMartVersion,
    BiScopeType,
)
from app.models.fleet import FleetDriver, FleetDriverStatus
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
)


@pytest.fixture(autouse=True)
def enable_bi_clickhouse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi_dependencies.settings, "BI_CLICKHOUSE_ENABLED", True)
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_bi_schema(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("ATTACH DATABASE ':memory:' AS bi")
        cursor.close()

    Base.metadata.create_all(
        bind=engine,
        tables=[
            ClientDocument.__table__,
            DocumentEdoState.__table__,
            BiExportBatch.__table__,
            BiMartClientSpend.__table__,
            BiMartVersion.__table__,
            FuelNetwork.__table__,
            FuelStation.__table__,
            FleetDriver.__table__,
            FuelCard.__table__,
            FuelTransaction.__table__,
        ],
    )

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield testing_session_local
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _client_headers(make_jwt, *, client_id: str, tenant_id: int) -> dict[str, str]:
    token = make_jwt(
        roles=("CLIENT_USER",),
        client_id=client_id,
        extra={"tenant_id": tenant_id, "aud": "neft-client"},
    )
    return {"Authorization": f"Bearer {token}"}


def test_client_documents_summary_route_returns_frontend_contract(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8201
    client_id = "wave2-documents-client"
    period_from = date(2026, 4, 1)
    period_to = date(2026, 4, 4)

    pending_id = str(uuid4())
    failed_id = str(uuid4())
    signed_id = str(uuid4())
    issued_id = str(uuid4())

    with db_session_factory() as db:
        db.add_all(
            [
                ClientDocument(
                    id=signed_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    document_type="INVOICE",
                    period_from=period_from,
                    period_to=period_to,
                    version=1,
                    direction="OUTBOUND",
                    title="Signed invoice",
                    status=DocumentStatus.SIGNED.value,
                    sender_type="NEFT",
                    date=period_from,
                ),
                ClientDocument(
                    id=pending_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    document_type="INVOICE",
                    period_from=period_from,
                    period_to=period_to,
                    version=2,
                    direction="OUTBOUND",
                    title="Pending act",
                    status=DocumentStatus.READY_TO_SIGN.value,
                    sender_type="NEFT",
                    date=date(2026, 4, 2),
                ),
                ClientDocument(
                    id=failed_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    document_type="INVOICE",
                    period_from=period_from,
                    period_to=period_to,
                    version=3,
                    direction="OUTBOUND",
                    title="Failed invoice",
                    status=DocumentStatus.SENT.value,
                    sender_type="NEFT",
                    date=date(2026, 4, 3),
                ),
                ClientDocument(
                    id=issued_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    document_type="INVOICE",
                    period_from=period_from,
                    period_to=period_to,
                    version=4,
                    direction="OUTBOUND",
                    title="Issued UPD",
                    status=DocumentStatus.DELIVERED.value,
                    sender_type="NEFT",
                    date=period_to,
                ),
                DocumentEdoState(
                    id=str(uuid4()),
                    document_id=signed_id,
                    client_id=client_id,
                    edo_status=EdoStatus.SIGNED.value,
                ),
                DocumentEdoState(
                    id=str(uuid4()),
                    document_id=failed_id,
                    client_id=client_id,
                    edo_status=EdoStatus.ERROR.value,
                ),
                DocumentEdoState(
                    id=str(uuid4()),
                    document_id=issued_id,
                    client_id=client_id,
                    edo_status=EdoStatus.DELIVERED.value,
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/documents/summary",
            params={"from": period_from.isoformat(), "to": period_to.isoformat()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "issued": 4,
        "signed": 1,
        "edo_pending": 2,
        "edo_failed": 1,
        "attention": [
            {"id": failed_id, "title": "Failed invoice", "status": "ERROR"},
            {"id": pending_id, "title": "Pending act", "status": "READY_TO_SIGN"},
        ],
    }


def test_client_exports_summary_route_returns_frontend_contract(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8202
    client_id = "wave2-exports-client"
    period_from = date(2026, 5, 1)
    period_to = date(2026, 5, 3)

    export_ok = str(uuid4())
    export_mismatch = str(uuid4())
    export_pending = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiMartVersion(
                id=str(uuid4()),
                mart_name="bi_daily_metrics",
                version="v2",
                is_active=True,
            )
        )
        db.add_all(
            [
                BiExportBatch(
                    id=export_ok,
                    tenant_id=tenant_id,
                    kind=BiExportKind.DAILY_METRICS,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    date_from=period_from,
                    date_to=period_to,
                    format=BiExportFormat.JSONL,
                    status=BiExportStatus.DELIVERED,
                    sha256="abc123",
                    created_at=datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc),
                ),
                BiExportBatch(
                    id=export_mismatch,
                    tenant_id=tenant_id,
                    kind=BiExportKind.DAILY_METRICS,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    date_from=period_from,
                    date_to=period_to,
                    format=BiExportFormat.CSV,
                    status=BiExportStatus.FAILED,
                    created_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
                ),
                BiExportBatch(
                    id=export_pending,
                    tenant_id=tenant_id,
                    kind=BiExportKind.ORDERS,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    date_from=period_from,
                    date_to=period_to,
                    format=BiExportFormat.CSV,
                    status=BiExportStatus.CREATED,
                    created_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/exports/summary",
            params={"from": period_from.isoformat(), "to": period_to.isoformat()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["ok"] == 1
    assert body["mismatch"] == 1
    assert body["items"] == [
        {
            "id": export_ok,
            "status": "OK",
            "checksum": "abc123",
            "mapping_version": "v2",
            "created_at": "2026-05-03T10:00:00Z",
        },
        {
            "id": export_mismatch,
            "status": "MISMATCH",
            "checksum": None,
            "mapping_version": "v2",
            "created_at": "2026-05-02T10:00:00Z",
        },
        {
            "id": export_pending,
            "status": "PENDING",
            "checksum": None,
            "mapping_version": None,
            "created_at": "2026-05-01T10:00:00Z",
        },
    ]


def test_client_spend_summary_route_returns_frontend_contract(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8203
    client_id = "wave2-spend-client"
    period_from = date(2026, 6, 1)
    period_to = date(2026, 6, 2)

    network_id = str(uuid4())
    station_a = str(uuid4())
    station_b = str(uuid4())
    card_a = str(uuid4())
    card_b = str(uuid4())
    driver_a = str(uuid4())
    driver_b = str(uuid4())

    with db_session_factory() as db:
        db.add_all(
            [
                BiMartClientSpend(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    period=period_from,
                    spend_total=1000,
                    spend_by_product={"DIESEL": 700, "AI95": 300},
                    fuel_spend=1000,
                    marketplace_spend=0,
                    avg_ticket=500,
                ),
                BiMartClientSpend(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    period=period_to,
                    spend_total=2000,
                    spend_by_product={"DIESEL": 800, "AI95": 1200},
                    fuel_spend=2000,
                    marketplace_spend=0,
                    avg_ticket=1000,
                ),
                FuelNetwork(id=network_id, name="Main network", provider_code="main", status=FuelNetworkStatus.ACTIVE),
                FuelStation(id=station_a, network_id=network_id, name="АЗС-1", status=FuelStationStatus.ACTIVE),
                FuelStation(id=station_b, network_id=network_id, name="АЗС-2", status=FuelStationStatus.ACTIVE),
                FleetDriver(
                    id=driver_a,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    full_name="Driver A",
                    status=FleetDriverStatus.ACTIVE,
                ),
                FleetDriver(
                    id=driver_b,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    full_name="Driver B",
                    status=FleetDriverStatus.ACTIVE,
                ),
                FuelCard(
                    id=card_a,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_token="card-a",
                    card_alias="Card A",
                    status=FuelCardStatus.ACTIVE,
                ),
                FuelCard(
                    id=card_b,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_token="card-b",
                    card_alias="Card B",
                    status=FuelCardStatus.ACTIVE,
                ),
                FuelTransaction(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_id=card_a,
                    driver_id=driver_a,
                    station_id=station_a,
                    network_id=network_id,
                    occurred_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
                    fuel_type="DIESEL",
                    volume_ml=1000,
                    unit_price_minor=70,
                    amount_total_minor=700,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                    merchant_name="Merchant A",
                ),
                FuelTransaction(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_id=card_b,
                    driver_id=driver_a,
                    station_id=station_b,
                    network_id=network_id,
                    occurred_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
                    fuel_type="AI-95",
                    volume_ml=1000,
                    unit_price_minor=50,
                    amount_total_minor=500,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                    merchant_name="Merchant A",
                ),
                FuelTransaction(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_id=card_a,
                    driver_id=driver_b,
                    station_id=station_a,
                    network_id=network_id,
                    occurred_at=datetime(2026, 6, 2, 11, 0, tzinfo=timezone.utc),
                    fuel_type="DIESEL",
                    volume_ml=1000,
                    unit_price_minor=30,
                    amount_total_minor=300,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                    merchant_name="Merchant B",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/spend/summary",
            params={"from": period_from.isoformat(), "to": period_to.isoformat()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "currency": "RUB",
        "total_spend": 3000,
        "avg_daily_spend": 1500,
        "trend": [
            {"date": "2026-06-01", "value": 1000},
            {"date": "2026-06-02", "value": 2000},
        ],
        "top_stations": [
            {"name": "АЗС-1", "amount": 1000},
            {"name": "АЗС-2", "amount": 500},
        ],
        "top_merchants": [
            {"name": "Merchant A", "amount": 1200},
            {"name": "Merchant B", "amount": 300},
        ],
        "top_cards": [
            {"name": "Card A", "amount": 1000},
            {"name": "Card B", "amount": 500},
        ],
        "top_drivers": [
            {"name": "Driver A", "amount": 1200},
            {"name": "Driver B", "amount": 300},
        ],
        "product_breakdown": [
            {"product": "AI95", "amount": 1500},
            {"product": "DIESEL", "amount": 1500},
        ],
        "export_available": False,
        "export_dataset": "spend",
    }