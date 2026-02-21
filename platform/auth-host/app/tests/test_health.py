from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

service_root = Path(__file__).resolve().parents[2]
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

from app.alembic_runtime import DbReadiness
from app.main import app


def test_health_endpoint(monkeypatch) -> None:
    async def _noop() -> None:
        return None

    monkeypatch.setattr("app.main.ensure_users_table", _noop)
    from types import SimpleNamespace

    monkeypatch.setenv("DEV_SEED_USERS", "0")
    monkeypatch.setattr("app.main.get_settings", lambda: SimpleNamespace(bootstrap_enabled=False, APP_ENV="dev"))
    monkeypatch.setattr(
        "app.healthcheck.check_db_readiness",
        lambda _dsn: DbReadiness(
            available=True,
            missing_tables=(),
            revision_matches_head=True,
            db_revision="head",
            expected_head="head",
        ),
    )

    with TestClient(app) as client:
        response_v1 = client.get("/api/v1/auth/health")
        response_prefixed = client.get("/api/auth/health")

    assert response_v1.status_code == 200
    assert response_prefixed.status_code == 200
    assert response_v1.json() == {"status": "ok", "service": "auth-host"}
    assert response_prefixed.json() == {"status": "ok", "service": "auth-host"}
