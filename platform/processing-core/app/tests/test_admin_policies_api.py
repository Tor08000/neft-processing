from datetime import datetime, timezone

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import services
from app.api.dependencies.admin import require_admin_user
from app.db import new_uuid_str
from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationSeverity,
    FleetPolicyExecution,
    FleetPolicyExecutionStatus,
)
from app.models.risk_policy import RiskPolicy
from app.models.risk_types import RiskSubjectType
from app.routers.admin.policies import router as admin_policies_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


ADMIN_POLICIES_TEST_TABLES = (
    FleetActionPolicy.__table__,
    FleetPolicyExecution.__table__,
    RiskPolicy.__table__,
)


def _admin_policies_test_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin_user)])
    router.include_router(admin_policies_router)
    return router


@pytest.fixture
def db_session() -> Session:
    with scoped_session_context(tables=ADMIN_POLICIES_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(db_session: Session, admin_auth_headers: dict):
    with router_client_context(
        router=_admin_policies_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: services.admin_auth.require_admin},
    ) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


@pytest.fixture
def user_auth_headers(user_token: str):
    return {"Authorization": f"Bearer {user_token}", "X-CRM-Version": "1"}


@pytest.fixture
def seeded_policies(db_session: Session):
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
    db_session.add(fleet_policy)
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
    db_session.add(risk_policy)
    db_session.flush()
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
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(fleet_policy)
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


def test_admin_policies_requires_admin(
    db_session: Session, user_auth_headers: dict, seeded_policies: dict
):
    with router_client_context(
        router=_admin_policies_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: services.admin_auth.require_admin},
    ) as api_client:
        api_client.headers.update(user_auth_headers)
        resp = api_client.get("/api/v1/admin/policies")
        assert resp.status_code == 403
