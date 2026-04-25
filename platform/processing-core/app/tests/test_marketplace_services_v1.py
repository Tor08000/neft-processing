from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.models.marketplace_catalog import (
    MarketplaceService,
    MarketplaceServiceLocation,
    MarketplaceServiceMedia,
    MarketplaceServiceScheduleException,
    MarketplaceServiceScheduleRule,
    MarketplaceServiceStatus,
)
from app.routers.marketplace_catalog import router as catalog_router
from app.routers.partner.marketplace_services import router as partner_router
from app.security.client_auth import require_client_user
from app.security.rbac.principal import Principal, get_principal

CURRENT_PRINCIPAL: Principal | None = None
CURRENT_CLIENT_TOKEN: dict = {"client_id": str(uuid4())}
TEST_TABLES = [
    MarketplaceService.__table__,
    MarketplaceServiceMedia.__table__,
    MarketplaceServiceLocation.__table__,
    MarketplaceServiceScheduleRule.__table__,
    MarketplaceServiceScheduleException.__table__,
]


def _build_principal(partner_id: str) -> Principal:
    return Principal(
        user_id=UUID(str(uuid4())),
        roles={"partner_user"},
        scopes=set(),
        client_id=None,
        partner_id=UUID(partner_id),
        is_admin=False,
        raw_claims={"user_id": str(uuid4()), "roles": ["partner_user"], "partner_id": partner_id},
    )


@pytest.fixture()
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    for table in TEST_TABLES:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(partner_router, prefix="/api")
    app.include_router(catalog_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_principal() -> Principal:
        if CURRENT_PRINCIPAL is None:
            raise RuntimeError("principal_not_set")
        return CURRENT_PRINCIPAL

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = override_get_principal
    app.dependency_overrides[require_client_user] = lambda: CURRENT_CLIENT_TOKEN

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(TEST_TABLES):
        table.drop(bind=engine, checkfirst=True)
    engine.dispose()


@pytest.fixture()
def test_db_session(api_client) -> Session:
    _, SessionLocal = api_client
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _cleanup_services(test_db_session):
    test_db_session.query(MarketplaceServiceScheduleException).delete()
    test_db_session.query(MarketplaceServiceScheduleRule).delete()
    test_db_session.query(MarketplaceServiceLocation).delete()
    test_db_session.query(MarketplaceServiceMedia).delete()
    test_db_session.query(MarketplaceService).delete()
    test_db_session.commit()


def _create_service_payload() -> dict:
    return {
        "title": "Диагностика",
        "description": "Полная проверка",
        "category": "Auto",
        "tags": ["engine"],
        "attributes": {"brand": "Acme"},
        "duration_min": 60,
        "requirements": "Документы",
    }


def test_service_create_update_get(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/services", json=_create_service_payload())
    assert response.status_code == 201
    service_id = response.json()["id"]

    update_payload = {"title": "Диагностика+", "attributes": {"brand": "Acme", "model": "X"}}
    update_response = client.patch(f"/api/partner/services/{service_id}", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Диагностика+"

    get_response = client.get(f"/api/partner/services/{service_id}")
    assert get_response.status_code == 200
    assert get_response.json()["attributes"]["model"] == "X"


def test_status_transitions(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/services", json=_create_service_payload())
    service_id = response.json()["id"]

    submit_response = client.post(f"/api/partner/services/{service_id}/submit")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "PENDING_REVIEW"

    archive_response = client.post(f"/api/partner/services/{service_id}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "ARCHIVED"


def test_patch_active_forbidden(api_client: tuple[TestClient, sessionmaker], test_db_session: Session):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/services", json=_create_service_payload())
    service_id = response.json()["id"]

    service = test_db_session.query(MarketplaceService).filter(MarketplaceService.id == service_id).one()
    service.status = MarketplaceServiceStatus.ACTIVE
    test_db_session.commit()

    update_response = client.patch(f"/api/partner/services/{service_id}", json={"title": "Updated"})
    assert update_response.status_code == 409
    assert update_response.json()["detail"]["error"] == "INVALID_STATE"


def test_schedule_rules_validation(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/services", json=_create_service_payload())
    service_id = response.json()["id"]

    location_response = client.post(f"/api/partner/services/{service_id}/locations", json={"location_id": str(uuid4())})
    service_location_id = location_response.json()["id"]

    rule_payload = {"weekday": 1, "time_from": "09:00", "time_to": "12:00", "slot_duration_min": 60, "capacity": 2}
    rule_response = client.post(
        f"/api/partner/service-locations/{service_location_id}/schedule/rules",
        json=rule_payload,
    )
    assert rule_response.status_code == 201

    overlap_payload = {"weekday": 1, "time_from": "11:00", "time_to": "13:00", "slot_duration_min": 60, "capacity": 1}
    overlap_response = client.post(
        f"/api/partner/service-locations/{service_location_id}/schedule/rules",
        json=overlap_payload,
    )
    assert overlap_response.status_code == 409
    assert overlap_response.json()["detail"]["error"] == "schedule_overlap"


def test_public_catalog_active_only(api_client: tuple[TestClient, sessionmaker], test_db_session: Session):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    active_response = client.post("/api/partner/services", json=_create_service_payload())
    active_id = active_response.json()["id"]
    draft_response = client.post("/api/partner/services", json=_create_service_payload())
    draft_id = draft_response.json()["id"]

    service = test_db_session.query(MarketplaceService).filter(MarketplaceService.id == active_id).one()
    service.status = MarketplaceServiceStatus.ACTIVE
    test_db_session.commit()

    list_response = client.get("/api/marketplace/catalog/services")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    ids = {item["id"] for item in items}
    assert active_id in ids
    assert draft_id not in ids


def test_availability_rules_and_exceptions(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/services", json=_create_service_payload())
    service_id = response.json()["id"]

    location_response = client.post(f"/api/partner/services/{service_id}/locations", json={"location_id": str(uuid4())})
    service_location_id = location_response.json()["id"]

    rule_payload = {"weekday": 0, "time_from": "09:00", "time_to": "11:00", "slot_duration_min": 60, "capacity": 2}
    client.post(f"/api/partner/service-locations/{service_location_id}/schedule/rules", json=rule_payload)

    availability_response = client.get(
        f"/api/partner/services/{service_id}/availability?date_from=2024-01-01&date_to=2024-01-01"
    )
    assert availability_response.status_code == 200
    assert len(availability_response.json()["items"]) == 2

    exception_payload = {"date": "2024-01-01", "is_closed": True}
    client.post(f"/api/partner/service-locations/{service_location_id}/schedule/exceptions", json=exception_payload)

    availability_closed = client.get(
        f"/api/partner/services/{service_id}/availability?date_from=2024-01-01&date_to=2024-01-01"
    )
    assert availability_closed.status_code == 200
    assert availability_closed.json()["items"] == []

    exception_override_payload = {"date": "2024-01-08", "is_closed": False, "capacity_override": 5}
    client.post(f"/api/partner/service-locations/{service_location_id}/schedule/exceptions", json=exception_override_payload)

    availability_override = client.get(
        f"/api/partner/services/{service_id}/availability?date_from=2024-01-08&date_to=2024-01-08"
    )
    assert availability_override.status_code == 200
    assert availability_override.json()["items"][0]["capacity"] == 5
