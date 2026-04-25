import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.routers.admin.merchants import router as admin_merchants_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


ADMIN_MERCHANTS_TEST_TABLES = (
    Merchant.__table__,
    Terminal.__table__,
)


def _admin_merchants_test_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin_user)])
    router.include_router(admin_merchants_router)
    return router


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=ADMIN_MERCHANTS_TEST_TABLES) as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    with router_client_context(
        router=_admin_merchants_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: lambda: {"roles": ["ADMIN"], "sub": "admin-1"}},
    ) as api_client:
        yield api_client


def test_create_and_get_merchant(client: TestClient):
    create_resp = client.post(
        "/api/v1/admin/merchants",
        json={"id": "m-1", "name": "Merchant One", "status": "ACTIVE"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["id"] == "m-1"
    assert body["name"] == "Merchant One"

    get_resp = client.get("/api/v1/admin/merchants/m-1")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "ACTIVE"


def test_merchants_list_filters(client: TestClient, db_session: Session):
    db_session.add_all(
        [
            Merchant(id="m-1", name="Alpha", status="ACTIVE"),
            Merchant(id="m-2", name="Beta", status="INACTIVE"),
            Merchant(id="m-3", name="Gamma", status="ACTIVE"),
        ]
    )
    db_session.commit()

    list_resp = client.get(
        "/api/v1/admin/merchants",
        params={"status": "ACTIVE", "limit": 10, "offset": 0},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert all(item["status"] == "ACTIVE" for item in data["items"])

    name_filter = client.get(
        "/api/v1/admin/merchants", params={"name": "amm"}
    )
    assert name_filter.status_code == 200
    assert name_filter.json()["total"] == 1
    assert name_filter.json()["items"][0]["id"] == "m-3"


def test_create_and_list_terminals(client: TestClient, db_session: Session):
    db_session.add(Merchant(id="m-1", name="Alpha", status="ACTIVE"))
    db_session.commit()

    create_resp = client.post(
        "/api/v1/admin/terminals",
        json={
            "id": "t-1",
            "merchant_id": "m-1",
            "status": "ACTIVE",
            "location": "Moscow",
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["id"] == "t-1"

    list_resp = client.get(
        "/api/v1/admin/terminals",
        params={"merchant_id": "m-1", "location": "mos"},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["location"] == "Moscow"


def test_not_found_and_validation(client: TestClient, db_session: Session):
    not_found = client.get("/api/v1/admin/merchants/nonexistent")
    assert not_found.status_code == 404

    invalid = client.post(
        "/api/v1/admin/merchants",
        json={"id": "m-1", "name": "x" * 260, "status": "ACTIVE"},
    )
    assert invalid.status_code == 422

    db_session.add(Merchant(id="m-1", name="Alpha", status="ACTIVE"))
    db_session.commit()

    terminal_missing_merchant = client.post(
        "/api/v1/admin/terminals",
        json={"id": "t-1", "merchant_id": "unknown", "status": "ACTIVE"},
    )
    assert terminal_missing_merchant.status_code == 404

    terminal_not_found = client.get("/api/v1/admin/terminals/unknown")
    assert terminal_not_found.status_code == 404


def test_terminal_updates(client: TestClient, db_session: Session):
    db_session.add_all(
        [
            Merchant(id="m-1", name="Alpha", status="ACTIVE"),
            Merchant(id="m-2", name="Beta", status="ACTIVE"),
            Terminal(
                id="t-1",
                merchant_id="m-1",
                status="ACTIVE",
                location="Initial",
            ),
        ]
    )
    db_session.commit()

    put_resp = client.put(
        "/api/v1/admin/terminals/t-1",
        json={
            "merchant_id": "m-2",
            "status": "INACTIVE",
            "location": "Saint-Petersburg",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["merchant_id"] == "m-2"
    assert put_resp.json()["status"] == "INACTIVE"

    patch_resp = client.patch(
        "/api/v1/admin/terminals/t-1",
        json={"status": "ACTIVE"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "ACTIVE"

    delete_resp = client.delete("/api/v1/admin/terminals/t-1")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "INACTIVE"

    force_delete = client.delete("/api/v1/admin/merchants/m-2", params={"force": True})
    assert force_delete.status_code == 200
    after_delete = client.get("/api/v1/admin/merchants/m-2")
    assert after_delete.status_code == 404
