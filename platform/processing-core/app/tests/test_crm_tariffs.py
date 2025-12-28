from fastapi.testclient import TestClient
import pytest

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_crm_tariff_crud(admin_auth_headers):
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/admin/crm/tariffs",
        json={
            "id": "FUEL_BASIC",
            "name": "Fuel Basic",
            "status": "ACTIVE",
            "billing_period": "MONTHLY",
            "base_fee_minor": 10000,
            "currency": "RUB",
            "features": {"fuel": True, "risk": True},
        },
        headers=admin_auth_headers,
    )
    assert create_resp.status_code == 200
    list_resp = client.get("/api/v1/admin/crm/tariffs", headers=admin_auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["id"] == "FUEL_BASIC"
