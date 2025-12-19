# Core API schema verification (Windows CMD)

This runbook verifies that `core-api` migrations are applied correctly and that the `operations.accounts` and `operations.posting_result` columns are queryable through both the gateway and direct API. All commands below are intended for **Windows CMD** (not PowerShell).

## Prerequisites
- Docker Desktop running with Linux containers
- The repository checked out at `C:\neft-processing`
- `.env.example` copied to `.env` if you need to override defaults

## A) Rebuild and restart core-api with migrations
```cmd
cd C:\neft-processing
docker compose up -d --build core-api
docker compose ps core-api
docker compose logs --tail=120 core-api
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"
```

Expected results:
- `core-api` is **healthy** in `docker compose ps core-api`
- `alembic ... current` matches the latest head that includes `posting_result`
- `heads` output shows the same revision as `current`

## B) DB schema check inside Postgres
```cmd
docker compose exec -T postgres psql -U neft -d neft -c "select column_name,data_type,udt_name from information_schema.columns where table_schema='public' and table_name='operations' and column_name in ('accounts','posting_result') order by column_name;"
```

Expected results:
- Two rows returned: `accounts` (JSON/JSONB) and `posting_result` (JSON/JSONB).

## C) API health through gateway and direct core-api
```cmd
curl -i "http://localhost/api/v1/health"
curl -i "http://localhost/api/v1/operations?limit=1&offset=0"
curl -i "http://localhost/api/v1/transactions?limit=1&offset=0"

curl -i "http://localhost:8001/api/v1/health"
curl -i "http://localhost:8001/api/v1/operations?limit=1&offset=0"
curl -i "http://localhost:8001/api/v1/transactions?limit=1&offset=0"
```

Expected results:
- Health endpoints return `200 OK`
- Operations/transactions list endpoints return `200 OK` (empty lists are acceptable)

## D) Happy-path demo data (no 500s)
Run the Windows CMD-safe seed script (no manual copy/paste needed):
```cmd
cd C:\neft-processing
call docs\runbooks\demo_seed_cmd.bat
```

Expected results:
- client created (ID printed by the script)
- card created (merchant/terminal created automatically)
- authorize response returns `200 OK` with JSON (approved status and an `operation_id`)

## E) Gateway upstream sanity check
```cmd
docker compose exec -T gateway sh -lc "getent hosts core-api && wget -S -O- http://core-api:8000/health 2>&1 | head -n 20"
```

Expected results:
- `core-api` resolves to an IP address
- `wget` returns a `200 OK` from `http://core-api:8000/health`
