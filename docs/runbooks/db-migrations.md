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

## Recovery: Alembic KeyError on old revision_id

If Alembic fails with `KeyError` for an old revision ID, this is usually a leftover from renamed
migrations. The safest recovery is to recreate the database. If you need to keep the data,
stamp the DB to the current merge head.

```sql
select version_num from alembic_version
```

```bash
alembic heads
alembic stamp <merge>
```

## Known root cause: wrong schema

- Migrations create all tables in `DB_SCHEMA` (see the schema argument in
  `app/alembic/versions/2025_11_01_init.py`). Running Alembic with `DB_SCHEMA` set to
  a non-public value (for example, `core`) puts all core tables into that schema while
  checks like `to_regclass('public.operations')` stay empty.
- Auth-host still seeds `public.users`/`public.user_roles`, so a schema mismatch shows up as
  "only users/user_roles exist" even though Alembic reported success.
- Fix: keep `DB_SCHEMA=public` unless you intentionally run multi-schema deployments, and
  always verify fingerprints below to confirm the schema in use.

## Debugging tips

- Turn on full SQL tracing: `DB_DEBUG_SQL=1` logs BEGIN/COMMIT/ROLLBACK and DDL statements from
  Alembic and diagnostics.
- Capture a fingerprint before/after `alembic upgrade head` to confirm the target host, DB and schema:

  ```bash
  DB_DEBUG_SQL=1 DB_FINGERPRINT_LABEL=pre \
    python - <<'PY'
from app.diagnostics.db_state import log_fingerprint_from_url
log_fingerprint_from_url(label="pre-upgrade")
PY
  ```

  The output includes `inet_server_addr`, `current_database`, `search_path`, `txid_current()`,
  `to_regclass` checks for `alembic_version`/`operations`, and a table listing for `public`.

- If the database looks empty after a migration attempt, also check the Postgres logs:

  ```bash
  docker compose logs --tail=200 postgres
  ```

- If you need a clean slate locally: `docker compose down -v` to drop the Postgres volume, then rerun migrations.
- Use `scripts/diag-db.cmd` (Windows) or the snippet above to confirm which database the container is connected to before and after migrations.
