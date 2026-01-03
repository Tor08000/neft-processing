# NEFT Platform — Status Snapshot (2026-01-03)

> **Scope:** This snapshot only reports what is confirmed by commands executed in this workspace. **No runtime commands were executed for this snapshot.**

## 1) Runtime status (AS-IS)

| Check | Expected command | Result | Evidence |
|---|---|---|---|
| Stack up | `docker compose up -d --build` | **NOT VERIFIED** | Command not executed. |
| Gateway health | `curl http://localhost/health` | **NOT VERIFIED** | Command not executed. |
| Core API health | `curl http://localhost/api/core/health` | **NOT VERIFIED** | Command not executed. |
| Auth health | `curl http://localhost/api/auth/health` | **NOT VERIFIED** | Command not executed. |
| AI health | `curl http://localhost/api/ai/health` | **NOT VERIFIED** | Command not executed. |
| Integration Hub health | `curl http://localhost/api/int/health` | **NOT VERIFIED** | Command not executed. |
| Metrics gateway | `curl http://localhost/metrics` | **NOT VERIFIED** | Command not executed. |
| Metrics core-api | `curl http://localhost:8001/metrics` | **NOT VERIFIED** | Command not executed. |
| Metrics integration-hub | `curl http://localhost:8010/metrics` | **NOT VERIFIED** | Command not executed. |

## 2) Database migration status

| Check | Expected command | Result | Evidence |
|---|---|---|---|
| processing-core head | `docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"` | **NOT VERIFIED** | Command not executed. |
| processing-core current | `docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"` | **NOT VERIFIED** | Command not executed. |
| auth-host head | `docker compose exec -T auth-host sh -lc "alembic -c alembic.ini heads"` | **NOT VERIFIED** | Command not executed. |
| auth-host current | `docker compose exec -T auth-host sh -lc "alembic -c alembic.ini current"` | **NOT VERIFIED** | Command not executed. |

## 3) Confirmed facts (code/config)

- Compose services and ports are defined in `docker-compose.yml`.
- Alembic heads are present in repo (see `docs/as-is/DB_SCHEMA_MAP.md`).
- Health/metrics endpoints are defined in service code (`gateway/nginx.conf`, `platform/*/app/main.py`).

