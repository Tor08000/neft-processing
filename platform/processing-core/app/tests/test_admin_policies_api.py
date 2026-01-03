import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

TEST_DB_URL = os.getenv("DATABASE_URL")

if TEST_DB_URL and not TEST_DB_URL.startswith("sqlite"):
    pytest.skip("admin policies API tests expect isolated SQLite database", allow_module_level=True)

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.db import Base, engine, new_uuid_str  # noqa: E402
from app.main import app  # noqa: E402
from app.models.fuel import (  # noqa: E402
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationSeverity,
    FleetPolicyExecution,
    FleetPolicyExecutionStatus,
)
from app.models.risk_policy import RiskPolicy  # noqa: E402
from app.models.risk_types import RiskSubjectType  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


@pytest.fixture
def user_auth_headers(user_token: str):
    return {"Authorization": f"Bearer {user_token}", "X-CRM-Version": "1"}


@pytest.fixture
def seeded_policies():
    with Session(bind=engine) as db:
        fleet_policy = FleetActionPolicy(
            client_id="client-1",
            scope_type=FleetActionPolicyScopeType.CLIENT,
            scope_id=None,
            trigger_type=FleetActionTriggerType.LIMIT_BREACH,
            trigger_severity_min=FleetNotificationSeverity.HIGH,
            breach_kind=FleetActionBreachKind.HARD,
            action=FleetActionPolicyAction.AUTO_BLOCK_CARD,
            cooldown_seconds=300,
            active=True,
        )
        db.add(fleet_policy)
        risk_policy = RiskPolicy(
            id="risk-policy-1",
            subject_type=RiskSubjectType.PAYMENT,
            tenant_id=10,
            client_id="client-1",
            provider=None,
            currency=None,
            country=None,
            threshold_set_id="thresholds-1",
            model_selector="default",
            priority=10,
            active=False,
        )
        db.add(risk_policy)
        db.flush()
        execution = FleetPolicyExecution(
            client_id="client-1",
            policy_id=fleet_policy.id,
            event_type="LIMIT_BREACH",
            event_id=new_uuid_str(),
            action="AUTO_BLOCK_CARD",
            status=FleetPolicyExecutionStatus.APPLIED,
            reason=None,
            dedupe_key=f"client:client-1:policy:{fleet_policy.id}:event:{new_uuid_str()}",
            created_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        db.commit()
        db.refresh(fleet_policy)
        yield {"fleet_id": str(fleet_policy.id), "risk_id": risk_policy.id}


def test_list_policies_across_types(client: TestClient, seeded_policies: dict):
    resp = client.get("/api/v1/admin/policies")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    types = {item["type"] for item in payload["items"]}
    assert "fleet" in types
    assert "finance" in types


def test_filter_by_type(client: TestClient, seeded_policies: dict):
    resp = client.get("/api/v1/admin/policies", params={"type": "fleet"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["type"] == "fleet"


def test_policy_detail_endpoint(client: TestClient, seeded_policies: dict):
    resp = client.get(f"/api/v1/admin/policies/fleet/{seeded_policies['fleet_id']}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["header"]["id"] == seeded_policies["fleet_id"]
    assert payload["header"]["type"] == "fleet"


def test_admin_policies_requires_admin(user_auth_headers: dict, seeded_policies: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(user_auth_headers)
        resp = api_client.get("/api/v1/admin/policies")
        assert resp.status_code == 403
