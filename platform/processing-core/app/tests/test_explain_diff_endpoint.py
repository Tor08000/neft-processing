from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.routers.explain_v2 import router as explain_v2_router
from app.models.unified_explain import UnifiedExplainSnapshot
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=(UnifiedExplainSnapshot.__table__,)) as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    with router_client_context(
        router=explain_v2_router,
        prefix="/api/core",
        db_session=db_session,
    ) as test_client:
        yield test_client


def _insert_snapshot(db_session: Session, *, snapshot_json: dict, snapshot_hash: str, subject_id: str) -> str:
    snapshot_id = str(uuid4())
    db_session.add(
        UnifiedExplainSnapshot(
            id=snapshot_id,
            tenant_id=1,
            subject_type="operation",
            subject_id=subject_id,
            snapshot_hash=snapshot_hash,
            snapshot_json=snapshot_json,
        )
    )
    db_session.commit()
    return snapshot_id


def test_explain_diff_reason_added(make_jwt, client: TestClient, db_session: Session):
    left_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-left",
        subject_id="op-1",
        snapshot_json={
            "decision": "DECLINE",
            "risk_score": 0.82,
            "reasons": [{"code": "velocity_high", "weight": 0.34}],
            "evidence": [{"id": "doc-1"}],
        },
    )
    right_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-right",
        subject_id="op-1",
        snapshot_json={
            "decision": "APPROVE",
            "risk_score": 0.47,
            "reasons": [
                {"code": "velocity_high", "weight": 0.34},
                {"code": "trusted_device", "weight": 0.21},
            ],
            "evidence": [{"id": "doc-1"}, {"id": "doc-2"}],
        },
    )

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    resp = client.get(
        "/api/core/explain/diff",
        headers=_auth_headers(token),
        params={
            "kind": "operation",
            "id": "op-1",
            "left_snapshot": left_id,
            "right_snapshot": right_id,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["reasons_diff"][0]["reason_code"] == "trusted_device"
    assert payload["reasons_diff"][0]["status"] == "added"


def test_explain_diff_reason_weakened(make_jwt, client: TestClient, db_session: Session):
    left_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-left-weakened",
        subject_id="op-2",
        snapshot_json={
            "decision": "DECLINE",
            "risk_score": 0.7,
            "reasons": [{"code": "velocity_high", "weight": 0.34}],
        },
    )
    right_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-right-weakened",
        subject_id="op-2",
        snapshot_json={
            "decision": "REVIEW",
            "risk_score": 0.55,
            "reasons": [{"code": "velocity_high", "weight": 0.12}],
        },
    )

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    resp = client.get(
        "/api/core/explain/diff",
        headers=_auth_headers(token),
        params={
            "kind": "operation",
            "id": "op-2",
            "left_snapshot": left_id,
            "right_snapshot": right_id,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["reasons_diff"][0]["status"] == "weakened"


def test_explain_diff_no_diff(make_jwt, client: TestClient, db_session: Session):
    left_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-left-nodiff",
        subject_id="op-3",
        snapshot_json={
            "decision": "REVIEW",
            "risk_score": 0.6,
            "reasons": [{"code": "velocity_high", "weight": 0.34}],
            "evidence": [{"id": "doc-1"}],
        },
    )
    right_id = _insert_snapshot(
        db_session,
        snapshot_hash="snap-right-nodiff",
        subject_id="op-3",
        snapshot_json={
            "decision": "REVIEW",
            "risk_score": 0.6,
            "reasons": [{"code": "velocity_high", "weight": 0.34}],
            "evidence": [{"id": "doc-1"}],
        },
    )

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    resp = client.get(
        "/api/core/explain/diff",
        headers=_auth_headers(token),
        params={
            "kind": "operation",
            "id": "op-3",
            "left_snapshot": left_id,
            "right_snapshot": right_id,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["reasons_diff"] == []
    assert payload["evidence_diff"] == []


def test_explain_diff_invalid_snapshot(make_jwt, client: TestClient):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    resp = client.get(
        "/api/core/explain/diff",
        headers=_auth_headers(token),
        params={
            "kind": "operation",
            "id": "op-4",
            "left_snapshot": str(uuid4()),
            "right_snapshot": str(uuid4()),
        },
    )

    assert resp.status_code == 404
