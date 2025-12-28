from fastapi.testclient import TestClient
import pytest

from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_crm_clients_crud(admin_auth_headers):
    client = TestClient(app)
    payload = {
        "id": "crm-client-1",
        "tenant_id": 1,
        "legal_name": "ООО Ромашка",
        "tax_id": "7700000000",
        "country": "RU",
        "timezone": "Europe/Moscow",
        "status": "ACTIVE",
        "meta": {"segment": "enterprise"},
    }
    response = client.post("/api/v1/admin/crm/clients", json=payload, headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == "crm-client-1"

    list_response = client.get(
        "/api/v1/admin/crm/clients", params={"tenant_id": 1}, headers=admin_auth_headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        "/api/v1/admin/crm/clients/crm-client-1",
        params={"tenant_id": 1},
        json={"status": "SUSPENDED"},
        headers=admin_auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "SUSPENDED"
