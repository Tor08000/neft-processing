from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation, FuelTransaction
from app.models.geo_metrics import GeoStationMetricsDaily
from app.services.geo_metrics import rebuild_geo_station_metrics_for_day


def _session_local() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    GeoStationMetricsDaily.__table__.create(bind=engine)
    return testing_session_local


def test_rebuild_geo_station_metrics_for_day() -> None:
    session_local = _session_local()
    target_day = date(2026, 2, 12)

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="GN1", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        s1 = FuelStation(network_id=str(network.id), station_code="S1", name="S1", status=fuel_models.FuelStationStatus.ACTIVE)
        s2 = FuelStation(network_id=str(network.id), station_code="S2", name="S2", status=fuel_models.FuelStationStatus.ACTIVE)
        db.add_all([s1, s2])
        db.commit()
        db.refresh(s1)
        db.refresh(s2)

        db.add_all(
            [
                FuelTransaction(
                    tenant_id=1,
                    client_id="c1",
                    card_id="00000000-0000-0000-0000-000000000001",
                    station_id=str(s1.id),
                    network_id=str(network.id),
                    occurred_at=datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc),
                    fuel_type=fuel_models.FuelType.AI95,
                    volume_ml=10000,
                    unit_price_minor=6000,
                    amount_total_minor=60000,
                    currency="RUB",
                    status=fuel_models.FuelTransactionStatus.SETTLED,
                    amount=Decimal("600.00"),
                    volume_liters=Decimal("10.000"),
                    meta={"risk_tags": ["STATION_RISK_RED"]},
                ),
                FuelTransaction(
                    tenant_id=1,
                    client_id="c1",
                    card_id="00000000-0000-0000-0000-000000000002",
                    station_id=str(s1.id),
                    network_id=str(network.id),
                    occurred_at=datetime(2026, 2, 12, 11, 0, tzinfo=timezone.utc),
                    fuel_type=fuel_models.FuelType.AI95,
                    volume_ml=5000,
                    unit_price_minor=6000,
                    amount_total_minor=30000,
                    currency="RUB",
                    status=fuel_models.FuelTransactionStatus.DECLINED,
                    meta={"risk_tags": ["STATION_RISK_YELLOW"]},
                ),
                FuelTransaction(
                    tenant_id=1,
                    client_id="c1",
                    card_id="00000000-0000-0000-0000-000000000003",
                    station_id=str(s2.id),
                    network_id=str(network.id),
                    occurred_at=datetime(2026, 2, 12, 12, 0, tzinfo=timezone.utc),
                    fuel_type=fuel_models.FuelType.DIESEL,
                    volume_ml=7000,
                    unit_price_minor=6500,
                    amount_total_minor=45500,
                    currency="RUB",
                    status=fuel_models.FuelTransactionStatus.SETTLED,
                    amount=Decimal("455.00"),
                    volume_liters=Decimal("7.000"),
                    meta={},
                ),
            ]
        )
        db.commit()

        rebuilt = rebuild_geo_station_metrics_for_day(db, target_day)
        assert rebuilt == 2

        rows = db.query(GeoStationMetricsDaily).filter(GeoStationMetricsDaily.day == target_day).all()
        assert len(rows) == 2
        by_station = {row.station_id: row for row in rows}

        s1_row = by_station[str(s1.id)]
        assert s1_row.tx_count == 2
        assert s1_row.captured_count == 1
        assert s1_row.declined_count == 1
        assert s1_row.amount_sum == Decimal("600.00")
        assert s1_row.liters_sum == Decimal("10.000")
        assert s1_row.risk_red_count == 1
        assert s1_row.risk_yellow_count == 1

        s2_row = by_station[str(s2.id)]
        assert s2_row.tx_count == 1
        assert s2_row.captured_count == 1
        assert s2_row.declined_count == 0
        assert s2_row.amount_sum == Decimal("455.00")
