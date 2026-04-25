import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import services
from app.api.dependencies.admin import require_admin_user
from app.models.risk_rule import RiskRule, RiskRuleAudit, RiskRuleVersion
from app.routers.admin.risk_rules import router as admin_risk_rules_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


ADMIN_RISK_RULES_TEST_TABLES = (
    RiskRule.__table__,
    RiskRuleVersion.__table__,
    RiskRuleAudit.__table__,
)


def _admin_risk_rules_test_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin_user)])
    router.include_router(admin_risk_rules_router)
    return router


@pytest.fixture
def db_session() -> Session:
    with scoped_session_context(tables=ADMIN_RISK_RULES_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(db_session: Session, admin_auth_headers: dict):
    with router_client_context(
        router=_admin_risk_rules_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: services.admin_auth.require_admin},
    ) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def _rule_payload(
    name: str = "rule-1",
    scope: str = "GLOBAL",
    subject: str | None = None,
    enabled: bool = True,
):
    return {
        "description": "test rule",
        "dsl": {
            "name": name,
            "scope": scope,
            "subject_id": subject,
            "selector": {"merchant_ids": ["M-1"]},
            "metric": "always",
            "value": 1,
            "action": "LOW",
            "priority": 10,
            "enabled": enabled,
            "reason": "demo",
        },
    }


def test_create_and_list_rules(client: TestClient):
    create_resp = client.post("/api/v1/admin/risk/rules", json=_rule_payload())
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["dsl"]["name"] == "rule-1"
    assert created["version"] == 1

    list_resp = client.get("/api/v1/admin/risk/rules", params={"scope": "GLOBAL"})
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]


def test_update_rule_and_toggle(client: TestClient):
    created = client.post("/api/v1/admin/risk/rules", json=_rule_payload("to-update"))
    rule_id = created.json()["id"]

    update_payload = _rule_payload("to-update", enabled=False)
    update_payload["dsl"]["action"] = "MEDIUM"

    update_resp = client.put(f"/api/v1/admin/risk/rules/{rule_id}", json=update_payload)
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["dsl"]["action"] == "MEDIUM"
    assert updated["enabled"] is False
    assert updated["version"] == 2

    disable_resp = client.post(f"/api/v1/admin/risk/rules/{rule_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["enabled"] is False

    enable_resp = client.post(f"/api/v1/admin/risk/rules/{rule_id}/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["enabled"] is True


def test_validation_rejects_missing_subject_for_scoped_rule(client: TestClient):
    payload = _rule_payload(scope="CLIENT")
    resp = client.post("/api/v1/admin/risk/rules", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "subject_id is required for scoped rules"


def test_validation_requires_window_for_aggregated_metrics(client: TestClient):
    payload = _rule_payload(name="window-check")
    payload["dsl"].update({"metric": "count", "value": 2})
    payload["dsl"].pop("selector", None)
    resp = client.post("/api/v1/admin/risk/rules", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "window must be provided for aggregated metrics"


def test_unauthorized_access_denied(db_session: Session):
    with router_client_context(
        router=_admin_risk_rules_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: services.admin_auth.require_admin},
    ) as api_client:
        resp = api_client.get("/api/v1/admin/risk/rules")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Missing bearer token"}
