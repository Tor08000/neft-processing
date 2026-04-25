from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import bi as bi_dependencies
from app.api.v1.endpoints import bi_dashboards as bi_dashboards_endpoint
from app.api.v1.endpoints import bi as raw_bi
from app.db import get_db
from app.main import app
from app.models.bi import BiSyncRun, BiSyncRunStatus, BiSyncRunType
from app.schemas.bi_sync import BiSyncRunOut
from app.services.bi import clickhouse as clickhouse_service
from app.services.bi import sync_runtime


def _error_message(response) -> str | None:
    body = response.json()
    error = body.get("error")
    if isinstance(error, dict):
        return error.get("message")
    if isinstance(error, str):
        return error
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("message") or detail.get("error")
    if isinstance(detail, str):
        return detail
    message = body.get("message")
    return message if isinstance(message, str) else None


def _client_headers(make_jwt, *, tenant_id: int = 9201, client_id: str = "bi-disabled-client") -> dict[str, str]:
    token = make_jwt(
        roles=("CLIENT_OWNER",),
        client_id=client_id,
        extra={"tenant_id": tenant_id, "aud": "neft-client"},
    )
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(make_jwt, *, tenant_id: int = 9201) -> dict[str, str]:
    token = make_jwt(
        roles=("ADMIN",),
        extra={"tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


def test_bi_disabled_blocks_dashboard_and_raw_export_without_fake_empty_success(monkeypatch, make_jwt) -> None:
    monkeypatch.setattr(bi_dependencies.settings, "BI_CLICKHOUSE_ENABLED", False)
    monkeypatch.setattr(raw_bi.bi_exports.settings, "BI_CLICKHOUSE_ENABLED", False)

    with TestClient(app, headers=_client_headers(make_jwt)) as api_client:
        dashboard_response = api_client.get(
            "/api/core/bi/metrics/daily",
            params={
                "scope_type": "CLIENT",
                "scope_id": "bi-disabled-client",
                "from": "2026-04-01",
                "to": "2026-04-02",
            },
        )
        export_response = api_client.post(
            "/api/v1/bi/exports",
            json={
                "kind": "ORDERS",
                "scope_type": "CLIENT",
                "scope_id": "bi-disabled-client",
                "date_from": "2026-04-01",
                "date_to": "2026-04-02",
                "format": "CSV",
            },
        )

    assert dashboard_response.status_code == 404
    assert _error_message(dashboard_response) == "bi_disabled"
    assert export_response.status_code == 404
    assert _error_message(export_response) == "bi_disabled"


def test_bi_disabled_blocks_admin_sync_as_explicit_optional_not_configured(monkeypatch, make_jwt) -> None:
    monkeypatch.setattr(sync_runtime.settings, "BI_CLICKHOUSE_ENABLED", False)

    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, headers=_admin_headers(make_jwt)) as api_client:
            init_response = api_client.post("/api/core/v1/admin/bi/sync/init")
            run_response = api_client.post("/api/core/v1/admin/bi/sync/run")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert init_response.status_code == 409
    assert _error_message(init_response) == "bi_disabled"
    assert run_response.status_code == 409
    assert _error_message(run_response) == "bi_disabled"


def test_clickhouse_sync_disabled_returns_explicit_task_result(monkeypatch) -> None:
    monkeypatch.setattr(clickhouse_service.settings, "BI_CLICKHOUSE_ENABLED", False)

    result = clickhouse_service.sync_clickhouse(None)  # type: ignore[arg-type]

    assert result == {
        "synced": 0,
        "status": "disabled",
        "reason": "bi_disabled",
    }


def test_bi_sync_run_response_accepts_orm_instance() -> None:
    started_at = datetime.now(timezone.utc)
    run = BiSyncRun(
        id="sync-run-1",
        type=BiSyncRunType.INIT,
        status=BiSyncRunStatus.COMPLETED,
        rows_written=7,
        started_at=started_at,
        finished_at=started_at,
        error=None,
    )

    response = BiSyncRunOut.model_validate(run)

    assert response.id == "sync-run-1"
    assert response.type == BiSyncRunType.INIT
    assert response.status == BiSyncRunStatus.COMPLETED
    assert response.rows_written == 7


def test_bi_dashboard_tenant_resolver_accepts_uuid_admin_claim() -> None:
    token = {"tenant_id": "870aa9a0-7108-4cbd-af02-56370c8f8cfd"}

    assert bi_dashboards_endpoint._resolve_bi_tenant_id(token, None) == 1  # type: ignore[arg-type]
