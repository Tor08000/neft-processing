from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.commercial_margin import router as margin_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.fuel import FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.station_margin import StationMarginDay
from app.services.commercial_margin import discover_margin_mapping, margin_build_daily


def _setup_session() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    Operation.__table__.create(bind=engine)
    ClearingBatch.__table__.create(bind=engine)
    ClearingBatchOperation.__table__.create(bind=engine)
    StationMarginDay.__table__.create(bind=engine)
    return session_local


def test_margin_mapping_discovery_collects_candidates() -> None:
    session_local = _setup_session()
    with session_local() as db:
        mapping, report = discover_margin_mapping(db)
    assert mapping.settlement_table == "clearing_batch_operation"
    assert mapping.revenue_table == "operations"
    assert "clearing_batch_operation" in report["candidate_tables"]


def test_margin_builder_computes_station_day() -> None:
    session_local = _setup_session()
    target_day = date(2026, 2, 14)
    ts = datetime(2026, 2, 14, 8, 30, tzinfo=timezone.utc)
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="P", status=FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(network_id=str(network.id), station_code="S-1", name="Main", city="Moscow", lat=55.7, lon=37.6, status=FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)

        batch = ClearingBatch(merchant_id="m1", tenant_id=1, date_from=target_day, date_to=target_day, total_amount=1500, operations_count=2)
        db.add(batch)
        db.commit()
        db.refresh(batch)

        op1 = Operation(
            operation_id="op-1",
            created_at=ts,
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
        )
        op2 = Operation(
            operation_id="op-2",
            created_at=ts,
            operation_type=OperationType.CAPTURE,
            status=OperationStatus.CAPTURED,
            merchant_id="m1",
            terminal_id="t1",
            fuel_station_id=str(station.id),
            client_id="c1",
            card_id="card1",
            amount=5000,
            captured_amount=5000,
            currency="RUB",
            authorized=True,
        )
        db.add_all([op1, op2])
        db.commit()

        db.add_all([
            ClearingBatchOperation(batch_id=batch.id, operation_id="op-1", amount=7000),
            ClearingBatchOperation(batch_id=batch.id, operation_id="op-2", amount=3000),
        ])
        db.commit()

        margin_build_daily(db, days_back=1, today=target_day)
        row = db.query(StationMarginDay).filter(StationMarginDay.day == target_day, StationMarginDay.station_id == str(station.id)).one()
        assert row.revenue_sum == 150.0
        assert row.cost_sum == 100.0
        assert row.gross_margin == 50.0
        assert row.tx_count == 2


def test_margin_endpoint_returns_sorted() -> None:
    session_local = _setup_session()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="P", status=FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        s1 = FuelStation(network_id=str(network.id), station_code="A", name="A", city="A city", lat=1.0, lon=1.0, status=FuelStationStatus.ACTIVE)
        s2 = FuelStation(network_id=str(network.id), station_code="B", name="B", city="B city", lat=2.0, lon=2.0, status=FuelStationStatus.ACTIVE)
        db.add_all([s1, s2])
        db.commit()
        db.refresh(s1)
        db.refresh(s2)
        db.add_all([
            StationMarginDay(day=date(2026, 2, 14), station_id=str(s1.id), revenue_sum=120, cost_sum=80, gross_margin=40, tx_count=3),
            StationMarginDay(day=date(2026, 2, 14), station_id=str(s2.id), revenue_sum=200, cost_sum=100, gross_margin=100, tx_count=5),
        ])
        db.commit()

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(margin_router, prefix="")

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    resp = client.get("/api/v1/commercial/margin/stations?date_from=2026-02-14&date_to=2026-02-14&sort_by=gross_margin&order=desc&limit=20")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"][0]["station_id"] == str(s2.id)
    assert payload["items"][1]["station_id"] == str(s1.id)
