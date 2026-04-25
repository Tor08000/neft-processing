import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models import fleet as fleet_models
from app.models import logistics as logistics_models
from app.services.logistics import repository
from app.services.logistics.orders import create_order
from app.tests._logistics_route_harness import admin_logistics_client_context


@pytest.fixture()
def admin_client() -> Tuple[TestClient, sessionmaker]:
    with admin_logistics_client_context() as ctx:
        yield ctx


def test_eta_recompute_endpoint_is_repeatable(
    monkeypatch: pytest.MonkeyPatch,
    admin_client: Tuple[TestClient, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=False),
    )

    client, SessionLocal = admin_client
    with SessionLocal() as db:
        vehicle = fleet_models.FleetVehicle(
            tenant_id=1,
            client_id="client-1",
            plate_number="ADMINETA1",
            status=fleet_models.FleetVehicleStatus.ACTIVE,
        )
        driver = fleet_models.FleetDriver(
            tenant_id=1,
            client_id="client-1",
            full_name="Admin ETA Driver",
            status=fleet_models.FleetDriverStatus.ACTIVE,
        )
        db.add_all([vehicle, driver])
        db.commit()
        db.refresh(vehicle)
        db.refresh(driver)

        order = create_order(
            db,
            tenant_id=1,
            client_id="client-1",
            order_type=logistics_models.LogisticsOrderType.TRIP,
            status=logistics_models.LogisticsOrderStatus.PLANNED,
            vehicle_id=str(vehicle.id),
            driver_id=str(driver.id),
            planned_end_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )

    recompute = client.post(f"/api/core/v1/admin/logistics/orders/{order.id}/eta/recompute")
    assert recompute.status_code == 200
    payload = recompute.json()
    assert payload["order_id"] == str(order.id)
    assert payload["method"] == logistics_models.LogisticsETAMethod.PLANNED.value
    assert payload["eta_confidence"] == 40
    assert "snapshot_id" not in payload.get("inputs", {})

    recompute_again = client.post(f"/api/core/v1/admin/logistics/orders/{order.id}/eta/recompute")
    assert recompute_again.status_code == 200

    with SessionLocal() as db:
        snapshot = repository.get_latest_eta_snapshot(db, order_id=str(order.id))
        assert snapshot is not None
        assert str(snapshot.order_id) == str(order.id)
