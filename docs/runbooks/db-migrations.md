# Core API database migrations

This runbook describes how to verify and run Alembic migrations for `core-api`.

## Locations

- Alembic config: `platform/processing-core/app/alembic.ini`
- Migration scripts: `platform/processing-core/app/alembic/versions/`
- Alembic env module: `platform/processing-core/app/alembic/env.py`

## Running migrations

```bash
# From repo root
cd platform/processing-core
PYTHONPATH=$(pwd) alembic -c app/alembic.ini upgrade head
```

## Inspecting state inside the container

```bash
docker compose exec -T core-api sh -lc "python - <<'PY'\nfrom app.diagnostics.db_state import collect_inventory\ninv = collect_inventory()\nprint(inv)\nPY"
```

The helper logs:

- server address/port and database name
- current user and search_path
- available schemas and tables (first 30 shown)
- values from `alembic_version`

## Typical checks

- `alembic_version` exists in the target schema (`DB_SCHEMA`, defaults to `public`).
- `alembic current` and `alembic heads` point to the same revision.
- Required tables (`operations`, `limit_configs`, `accounts`, `ledger_entries`) exist in the same schema as `alembic_version`.

> ⚠️ `users` and `user_roles` can appear even when `core-api` migrations never ran.
> They are created by the auth service bootstrap in `platform/auth-host/app/db.py` on startup
> and should not be used as proof that Alembic DDL succeeded.

## Debugging tips

- Ensure `DATABASE_URL` is set and valid. An invalid DSN now raises a clear startup error.
- If you need a clean slate locally: `docker compose down -v` to drop the Postgres volume, then rerun migrations.
- Use `scripts/diag-db.cmd` (Windows) or the snippet above to confirm which database the container is connected to before and after migrations.
