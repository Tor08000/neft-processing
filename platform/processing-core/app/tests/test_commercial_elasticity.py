from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.commercial_elasticity import router as elasticity_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.fuel import FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.station_elasticity import StationElasticity
from app.services.commercial_elasticity import compute_period_elasticity, elasticity_compute


def _setup_session() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    Operation.__table__.create(bind=engine)
    StationElasticity.__table__.create(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE station_prices (
                    station_id TEXT NOT NULL,
                    product_code TEXT,
                    price FLOAT NOT NULL,
                    valid_from DATETIME NOT NULL,
                    valid_to DATETIME
                )
                """
            )
        )
    return session_local


def test_compute_period_elasticity_math() -> None:
    e = compute_period_elasticity(prev_price=50, cur_price=55, prev_q=1000, cur_q=900)
    assert e is not None
    assert round(e, 1) == -1.0
    assert compute_period_elasticity(prev_price=50, cur_price=50.1, prev_q=1000, cur_q=900) is None


def test_elasticity_compute_without_product_dim_sets_note(monkeypatch) -> None:
    session_local = _setup_session()
    now = datetime.now(tz=timezone.utc)
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="P", status=FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(network_id=str(network.id), station_code="S-1", name="Main", city="Moscow", lat=55.7, lon=37.6, status=FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)

        db.execute(
            text(
                """
                INSERT INTO station_prices(station_id, product_code, price, valid_from, valid_to)
                VALUES (:sid, 'AI95', 50, :v1, :v2), (:sid, 'AI95', 55, :v2, :v3)
                """
            ),
            {"sid": str(station.id), "v1": now - timedelta(days=10), "v2": now - timedelta(days=5), "v3": now},
        )

        for idx in range(25):
            ts1 = now - timedelta(days=9, hours=idx)
            ts2 = now - timedelta(days=4, hours=idx)
            db.add(
                Operation(
                    operation_id=f"op-a-{idx}",
                    created_at=ts1,
                    operation_type=OperationType.CAPTURE,
                    status=OperationStatus.CAPTURED,
                    merchant_id="m1",
                    terminal_id="t1",
                    fuel_station_id=str(station.id),
                    client_id="c1",
                    card_id="card1",
                    amount=10000,
                    captured_amount=10000,
                    currency="RUB",
                    authorized=True,
                    product_code="AI95",
                    quantity=20,
                )
            )
            db.add(
                Operation(
                    operation_id=f"op-b-{idx}",
                    created_at=ts2,
                    operation_type=OperationType.CAPTURE,
                    status=OperationStatus.CAPTURED,
                    merchant_id="m1",
                    terminal_id="t1",
                    fuel_station_id=str(station.id),
                    client_id="c1",
                    card_id="card1",
                    amount=8000,
                    captured_amount=8000,
                    currency="RUB",
                    authorized=True,
                    product_code="AI95",
                    quantity=16,
                )
            )
        db.commit()

        monkeypatch.setattr("app.services.commercial_elasticity.detect_product_dimension", lambda: False)
        result = elasticity_compute(db, window_days=30)
        assert result["rows"] >= 1

        saved = db.query(StationElasticity).filter(StationElasticity.station_id == str(station.id), StationElasticity.window_days == 30).first()
        assert saved is not None
        assert saved.notes == "PRODUCT_DIM_MISSING"


def test_elasticity_endpoint_returns_items(monkeypatch) -> None:
    session_local = _setup_session()
    now = datetime.now(tz=timezone.utc)
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="P", status=FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(network_id=str(network.id), station_code="S-2", name="A", city="A city", lat=1.0, lon=1.0, status=FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)
        db.add(
            StationElasticity(
                station_id=str(station.id),
                product_code="",
                window_days=90,
                elasticity_score=-0.8,
                elasticity_abs=0.8,
                confidence_score=0.9,
                sample_points=4,
                total_volume=450,
                notes="PRODUCT_DIM_MISSING",
                updated_at=now,
            )
        )
        db.commit()

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(elasticity_router, prefix="")

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    resp = client.get("/api/v1/commercial/elasticity/stations?window_days=90&sort_by=elasticity_abs&order=desc&limit=20")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"][0]["station_id"] == str(station.id)
