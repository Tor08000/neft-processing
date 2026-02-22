Core API service (FastAPI)


## Client Portal API namespace

Canonical client endpoints are exposed under:

- `/api/core/client/*`

Current baseline endpoints:

- `GET /api/core/client/me`
- `GET /api/core/client/health`

Compatibility aliases for `/api/core/client/v1/*` may exist for legacy integrations, but new integrations should use `/api/core/client/*`.

## Operational scenarios (refund / reversal / dispute)

Admin endpoints (prefixed with `/api/core/v1/admin`):

- `POST /refunds` — create refund with idempotency and settlement boundary detection.
- `POST /reversals` — request capture reversal, creating adjustment when settlement is closed.
- `POST /disputes/open` — open dispute (optionally place hold).
- `POST /disputes/{id}/review` — move dispute to review.
- `POST /disputes/{id}/accept` — accept dispute, posting refund/fee and creating adjustment if needed.
- `POST /disputes/{id}/reject` — reject dispute and release hold.
- `POST /disputes/{id}/close` — finalize accepted/rejected dispute.

Admin JWT roles:

- Auth-host issues the `PLATFORM_ADMIN` role for platform administrators.
- Core API treats both `ADMIN` and `PLATFORM_ADMIN` as administrator roles for `/api/v1/admin/*` endpoints.

Smoke tests:

```bash
pytest platform/processing-core/app/tests/test_refunds.py -q
pytest platform/processing-core/app/tests/test_reversals.py -q
pytest platform/processing-core/app/tests/test_disputes.py -q
```

⚠️ Monorepo note  
Each service has isolated test dependencies. Run tests from the service root or via scoped pytest paths.

## Granting ADMIN role for auth-host

Auth endpoints require an `ADMIN` role in the JWT. You can grant it directly in Postgres (works from Windows CMD as well):

```cmd
docker compose exec postgres psql -U neft -d neft -c "insert into public.user_roles(user_id, role_code) select id, 'ADMIN' from public.users where email='admin2@neft.local' on conflict do nothing;"
```

## GUID/UUID conventions

- Use `app.db.types.GUID()` for all new primary keys and foreign keys to ensure PostgreSQL uses native UUID and SQLite stores `VARCHAR(36)`.
- Generate identifiers with `app.db.types.new_uuid_str()`; ORM values are returned as strings for easier JSON/Pydantic interop.
- SQLite tests should work without UUID extensions because GUID stores strings transparently.

## Migration and test commands

Run migration checks (for example via Docker Compose):

```bash
docker compose build --no-cache core-api
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c ./app/alembic.ini heads"
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c ./app/alembic.ini upgrade head"
docker compose exec postgres psql -U neft -d neft -c "select to_regclass('public.billing_periods');"
```
Expected result: `heads` returns exactly one revision (a single Alembic head).

Run migrations locally (requires a reachable Postgres and DATABASE_URL):

```bash
export DATABASE_URL="postgresql+psycopg://neft:change-me@localhost:5432/neft"
export PYTHONPATH="platform/processing-core:shared/python"
alembic -c platform/processing-core/app/alembic.ini upgrade head
```

Windows CMD:

```cmd
set DATABASE_URL=postgresql+psycopg://neft:change-me@localhost:5432/neft
set PYTHONPATH=platform/processing-core;shared/python
alembic -c platform/processing-core/app/alembic.ini upgrade head
```

Run focused tests:

```bash
pytest -q platform/processing-core/app/tests/test_billing_periods.py
pytest -q tests/test_alembic_single_head.py
```

Fuel stations nearest tests on PostgreSQL (primary deterministic run path):

```bash
docker compose exec core-api pytest -q platform/processing-core/app/tests/test_fuel_stations_nearest_api.py
```

Fast local smoke path (SQLite, optional, does not replace PostgreSQL run):

```bash
pytest -q platform/processing-core/app/tests/test_fuel_stations_nearest_api.py
```

Clean integration test run via Docker Compose (from repo root):

```bash
make itest-clean
```
