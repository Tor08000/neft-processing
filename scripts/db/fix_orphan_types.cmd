@echo off
setlocal
if "%1"=="" (
  set TARGET=core-api
) else (
  set TARGET=%1
)

set SCHEMA=processing_core

for %%T in (client_onboarding_state) do (
  set TYPE_NAME=%%T
  echo [fix-orphan-types] checking %SCHEMA%.%%T on %TARGET% ...
  docker compose exec -T %TARGET% sh -lc "TYPE_NAME=%%T python - <<'PY'
import os
from sqlalchemy import create_engine, text

schema = os.environ.get('NEFT_DB_SCHEMA', 'processing_core')
type_name = os.environ.get('TYPE_NAME')
if not type_name:
    raise SystemExit('TYPE_NAME is required')

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise SystemExit('DATABASE_URL is required')

engine = create_engine(database_url, future=True)
with engine.begin() as conn:
    type_exists = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = :schema
              AND t.typname = :type_name
              AND t.typtype = 'c'
            """
        ),
        {"schema": schema, "type_name": type_name},
    ).first()
    table_exists = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table_name
            """
        ),
        {"schema": schema, "table_name": type_name},
    ).first()

    if type_exists and not table_exists:
        schema_sql = schema.replace('"', '""')
        type_sql = type_name.replace('"', '""')
        conn.exec_driver_sql(f'DROP TYPE IF EXISTS "{schema_sql}"."{type_sql}" CASCADE')
        print(f'dropped orphan type {schema}.{type_name}')
    else:
        print(f'no orphan type for {schema}.{type_name}')

engine.dispose()
PY"
)
endlocal
