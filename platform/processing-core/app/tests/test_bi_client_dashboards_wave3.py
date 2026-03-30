from __future__ import annotations

import base64
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
from app.models.bi import BiMartClientSpend
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
            BiMartClientSpend.__table__,
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


def test_client_spend_export_flow_returns_job_and_download_url(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8301
    client_id = "wave3-spend-client"
    period_from = date(2026, 7, 1)
    period_to = date(2026, 7, 2)

    network_id = str(uuid4())
    station_id = str(uuid4())
    card_id = str(uuid4())
    driver_id = str(uuid4())

    with db_session_factory() as db:
        db.add_all(
            [
                BiMartClientSpend(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    period=period_from,
                    spend_total=1200,
                    spend_by_product={"DIESEL": 1200},
                    fuel_spend=1200,
                    marketplace_spend=0,
                    avg_ticket=600,
                ),
                FuelNetwork(id=network_id, name="Main network", provider_code="main", status=FuelNetworkStatus.ACTIVE),
                FuelStation(id=station_id, network_id=network_id, name="???-1", status=FuelStationStatus.ACTIVE),
                FleetDriver(
                    id=driver_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    full_name="Driver A",
                    status=FleetDriverStatus.ACTIVE,
                ),
                FuelCard(
                    id=card_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_token="card-a",
                    card_alias="Card A",
                    status=FuelCardStatus.ACTIVE,
                ),
                FuelTransaction(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    client_id=client_id,
                    card_id=card_id,
                    driver_id=driver_id,
                    station_id=station_id,
                    network_id=network_id,
                    occurred_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
                    fuel_type="DIESEL",
                    volume_ml=1000,
                    unit_price_minor=120,
                    amount_total_minor=1200,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                    merchant_name="Merchant A",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        create_response = api_client.post(
            "/api/core/bi/exports",
            json={"dataset": "spend", "from": period_from.isoformat(), "to": period_to.isoformat()},
        )

        assert create_response.status_code == 200
        job = create_response.json()
        assert job["dataset"] == "spend"
        assert job["status"] == "DELIVERED"
        assert job["format"] == "CSV"
        assert job["ready"] is True

        job_response = api_client.get(f"/api/core/bi/exports/{job['id']}")
        assert job_response.status_code == 200
        assert job_response.json()["id"] == job["id"]
        assert job_response.json()["status"] == "DELIVERED"

        download_response = api_client.get(f"/api/core/bi/exports/{job['id']}/download")

    assert download_response.status_code == 200
    download_body = download_response.json()
    assert download_body["id"] == job["id"]
    assert download_body["status"] == "DELIVERED"
    assert download_body["sha256"]
    assert download_body["url"].startswith("data:text/csv;charset=utf-8;base64,")

    csv_payload = base64.b64decode(download_body["url"].split(",", 1)[1]).decode("utf-8")
    assert "section,metric,name,value" in csv_payload
    assert "summary,total_spend,,1200" in csv_payload
    assert "top_stations,amount,???-1,1200" in csv_payload
    assert "top_cards,amount,Card A,1200" in csv_payload
    assert "top_drivers,amount,Driver A,1200" in csv_payload
