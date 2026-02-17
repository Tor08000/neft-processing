# Runbook: stable core-api startup

## Build and run (Windows CMD)

```cmd
docker compose build core-api
docker compose up -d core-api
docker compose logs -f core-api
```

## Key startup checks

`core-api` entrypoint performs these steps before `uvicorn` boot:

1. waits for Postgres;
2. applies Alembic migrations;
3. runs post-migration validation checks;
4. starts API process.

If startup fails, first inspect logs for `ModuleNotFoundError` / `ImportError` and re-run dependency check:

```cmd
python scripts\check_imports.py
```

## Metrics mode

`METRICS_ENABLED` controls Prometheus metric registration in runtime modules:

- `METRICS_ENABLED=1` (default): metrics are registered and updated;
- `METRICS_ENABLED=0`: notification/EDO poll metrics are disabled with no-op stubs, service keeps running.

`prometheus-client` is included in `platform/processing-core/requirements.txt` for the default enabled mode.

## Self-test entry point

Use:

```cmd
selftest.cmd
```

It runs imports/dependencies validation and then executes core-api pytest inside docker compose.
