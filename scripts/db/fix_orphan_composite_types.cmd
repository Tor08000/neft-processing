@echo off
setlocal
if "%1"=="" (
  set TARGET=core-api
) else (
  set TARGET=%1
)

echo [fix-orphan-composite-types] dropping orphan composite types on %TARGET% ...
docker compose exec -T %TARGET% sh -lc "python - <<'PY'
import os
from sqlalchemy import create_engine, text

schema = (os.environ.get('NEFT_DB_SCHEMA', 'processing_core') or 'processing_core').strip() or 'processing_core'
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise SystemExit('DATABASE_URL is required')

schema_sql = schema.replace(\"'\", \"''\")
cleanup_sql = f\"\"\"
DO $$
DECLARE
    record_type RECORD;
BEGIN
    FOR record_type IN
        SELECT t.typname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = '{schema_sql}'
          AND t.typtype = 'c'
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = '{schema_sql}'
              AND c.relname = record_type.typname
              AND c.relkind = 'r'
        ) THEN
            EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', '{schema_sql}', record_type.typname);
        END IF;
    END LOOP;
END $$;
\"\"\"

engine = create_engine(database_url, future=True)
with engine.begin() as conn:
    conn.execute(text(cleanup_sql))

engine.dispose()
print(f\"[fix-orphan-composite-types] cleanup done for schema {schema}\")
PY"
endlocal
