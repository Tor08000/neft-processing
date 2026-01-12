#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

DB_SCHEMA=$(python - <<'PY'
import os
from app.db.schema import resolve_db_schema

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")
print(resolution.schema)
if not db_url:
    raise SystemExit("[entrypoint] DATABASE_URL is not set")
PY
)
schema_resolved=$DB_SCHEMA
echo "[entrypoint] schema_resolved=${schema_resolved}"

python - <<'PY'
import os
from sqlalchemy.engine import make_url

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise SystemExit("[entrypoint] DATABASE_URL is not set")
try:
    parsed = make_url(db_url)
    safe_url = parsed._replace(password="***").render_as_string(hide_password=False)
except Exception:
    safe_url = db_url
print(f"[entrypoint] DATABASE_URL={safe_url}")
PY

wait_for_postgres() {
    python - <<'PY'
import os
import sys
import time

from sqlalchemy.engine import make_url
import psycopg

dsn = os.getenv("DATABASE_URL")
schema = os.getenv("NEFT_DB_SCHEMA", "processing_core").strip() or "processing_core"
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
interval = int(os.getenv("DB_WAIT_INTERVAL", "2"))

if not dsn:
    print("[entrypoint] DATABASE_URL is not set", file=sys.stderr, flush=True)
    sys.exit(1)

def _normalize_postgres_dsn(raw: str) -> str:
    if "postgresql" not in raw or "://" not in raw:
        return raw

    try:
        url = make_url(raw)
    except Exception:
        return raw

    if not url.drivername.startswith("postgresql"):
        return raw

    safe_url = url.set(drivername="postgresql")
    return safe_url.render_as_string(hide_password=False)

dsn = _normalize_postgres_dsn(dsn)
connect_kwargs = {
    "connect_timeout": 5,
    "prepare_threshold": 0,
    "options": f"-c search_path={schema},public",
}
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        with psycopg.connect(dsn, **connect_kwargs) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] postgres is not ready after {timeout}s: {last_error}", file=sys.stderr, flush=True)
sys.exit(1)
PY
}

echo "[entrypoint] waiting for postgres..."
wait_for_postgres

python - <<'PY'
import os
import sys

import psycopg
from sqlalchemy.engine import make_url

from app.db.schema import resolve_db_schema

db_url = os.getenv("DATABASE_URL")
schema = os.getenv("NEFT_DB_SCHEMA", "processing_core").strip() or "processing_core"
if not db_url:
    raise SystemExit("[entrypoint] DATABASE_URL is not set")

url = make_url(db_url)
if url.drivername.endswith("+psycopg"):
    url = url.set(drivername="postgresql")
dsn = url.render_as_string(hide_password=False)

with psycopg.connect(dsn, prepare_threshold=0, options=f"-c search_path={schema},public") as conn:
    with conn.cursor() as cur:
        cur.execute("select current_schema(), current_setting('search_path')")
        current_schema, search_path = cur.fetchone()
        print(
            "[entrypoint] pre-migration search_path check: "
            f"schema_resolved={schema} current_schema={current_schema} search_path={search_path}",
            flush=True,
        )
PY

ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-app/alembic.ini}
MIGRATION_LOG=${MIGRATION_LOG:-/tmp/alembic_migration.log}

if [ ! -f "$ALEMBIC_CONFIG" ]; then
    echo "[entrypoint] missing alembic config: $ALEMBIC_CONFIG" >&2
    exit 1
fi

echo "[entrypoint] checking alembic heads via ($ALEMBIC_CONFIG)"
heads_output=$(alembic -c "$ALEMBIC_CONFIG" heads 2>&1)
heads_count=$(printf "%s\n" "$heads_output" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')
if [ "$heads_count" -ne 1 ]; then
    echo "[entrypoint] migration validation failed; multiple heads detected" >&2
    echo "$heads_output" >&2
    echo "[entrypoint] create merge revision with: alembic merge <head1> <head2>" >&2
    echo "[entrypoint] migration validation failed; run scripts\\check_migrations.cmd" >&2
    if [ "${ENTRYPOINT_MIGRATION_KEEPALIVE}" = "1" ]; then
        echo "[entrypoint] ENTRYPOINT_MIGRATION_KEEPALIVE=1; keeping container alive" >&2
        tail -f /dev/null
    fi
    exit 1
fi

echo "[entrypoint] pre-migration cleanup: schema_resolved=${schema_resolved} search_path=${schema_resolved},public"
echo "[entrypoint] dropping orphan types/domains (pre-migration cleanup)"
if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint] DATABASE_URL is not set for orphan cleanup" >&2
    exit 1
fi
PSQL_URL=$(printf '%s' "$DATABASE_URL" | sed 's/+psycopg//')
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<SQL
DO $$
DECLARE r record;
DECLARE has_table boolean;
DECLARE total int := 0;
DECLARE dropped int := 0;
BEGIN
  FOR r IN (
    SELECT n.nspname AS schema_name,
           t.typname AS type_name,
           t.typtype AS type_kind
    FROM pg_type t
    JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname = '${schema_resolved}'
      AND t.typname NOT LIKE '\_%'
  ) LOOP
    total := total + 1;
    SELECT EXISTS (
      SELECT 1
      FROM pg_class c
      JOIN pg_namespace n2 ON n2.oid=c.relnamespace
      WHERE n2.nspname=r.schema_name
        AND c.relname=r.type_name
        AND c.relkind IN ('r','p')
    ) INTO has_table;

    IF NOT has_table THEN
      IF r.type_kind = 'd' THEN
        EXECUTE format('DROP DOMAIN IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name);
      ELSE
        EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name);
      END IF;
      dropped := dropped + 1;
    END IF;
  END LOOP;

  RAISE NOTICE 'pre-migration cleanup: orphan types/domains found %, dropped %', total, dropped;
END $$;
SQL
echo "[entrypoint] pre-migration cleanup completed"

echo "[entrypoint] applying migrations via alembic ($ALEMBIC_CONFIG)"
if ! alembic -c "$ALEMBIC_CONFIG" upgrade head >"$MIGRATION_LOG" 2>&1; then
    echo "[entrypoint] migration validation failed; last log lines:" >&2
    tail -n 200 "$MIGRATION_LOG" >&2 || true
    echo "[entrypoint] migration validation failed; run scripts\\check_migrations.cmd" >&2
    echo "[entrypoint] migration log saved to $MIGRATION_LOG" >&2
    if [ "${ENTRYPOINT_MIGRATION_KEEPALIVE}" = "1" ]; then
        echo "[entrypoint] ENTRYPOINT_MIGRATION_KEEPALIVE=1; keeping container alive" >&2
        tail -f /dev/null
    fi
    exit 1
fi

python - <<'PY'
from app.db import reset_engine

reset_engine()
print("[entrypoint] engine cache reset", flush=True)
PY

python - <<'PY'
import os
import sys

import psycopg
from sqlalchemy.engine import make_url

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[entrypoint] DATABASE_URL is not set for schema repair", file=sys.stderr, flush=True)
    sys.exit(1)

schema = resolve_db_schema().schema
url = make_url(db_url)
if url.drivername.endswith("+psycopg"):
    url = url.set(drivername="postgresql")
dsn = url.render_as_string(hide_password=False)

def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def _ensure_enum(cur, schema: str, name: str, values: list[str]) -> None:
    joined = ", ".join(_quote_literal(value) for value in values)
    schema_sql = schema.replace('"', '""')
    name_sql = name.replace('"', '""')
    cur.execute(
        f"""
        DO $$
        BEGIN
            CREATE TYPE "{schema_sql}"."{name_sql}" AS ENUM ({joined});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

operation_type_values = [
    "AUTH",
    "HOLD",
    "COMMIT",
    "REVERSE",
    "REFUND",
    "DECLINE",
    "CAPTURE",
    "REVERSAL",
]
operation_status_values = [
    "PENDING",
    "AUTHORIZED",
    "HELD",
    "COMPLETED",
    "REVERSED",
    "REFUNDED",
    "DECLINED",
    "CANCELLED",
    "CAPTURED",
    "OPEN",
]
product_type_values = [
    "DIESEL",
    "AI92",
    "AI95",
    "AI98",
    "GAS",
    "OTHER",
]
risk_result_values = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
]

with psycopg.connect(
    dsn,
    prepare_threshold=0,
    options=f"-c search_path={schema},public",
) as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        cur.execute(f'SET search_path TO "{schema}", public')
        cur.execute("select current_schema(), current_setting('search_path')")
        current_schema, search_path = cur.fetchone()
        cur.execute("select to_regclass(%s)", (f"{schema}.operations",))
        processing_core_reg = cur.fetchone()[0]
        cur.execute(
            """
            SELECT n.nspname, c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'operations'
            ORDER BY n.nspname
            """
        )
        pg_class_hits = cur.fetchall()
        cur.execute(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'operations'
            ORDER BY table_schema
            """
        )
        operations_schemas = [row[0] for row in cur.fetchall()]
        print(
            "[entrypoint] repair diagnostics: "
            f"current_schema={current_schema} search_path={search_path} "
            f"{schema}.operations={processing_core_reg} "
            f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
            flush=True,
        )
        if processing_core_reg is not None:
            sys.exit(0)

        _ensure_enum(cur, schema, "operationtype", operation_type_values)
        _ensure_enum(cur, schema, "operationstatus", operation_status_values)
        _ensure_enum(cur, schema, "producttype", product_type_values)
        _ensure_enum(cur, schema, "riskresult", risk_result_values)

        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".operations (
                id uuid PRIMARY KEY NOT NULL,
                operation_id varchar(64) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                operation_type "{schema}".operationtype NOT NULL,
                status "{schema}".operationstatus NOT NULL,
                merchant_id varchar(64) NOT NULL,
                terminal_id varchar(64) NOT NULL,
                client_id varchar(64) NOT NULL,
                card_id varchar(64) NOT NULL,
                tariff_id varchar(64) NULL,
                product_id varchar(64) NULL,
                amount bigint NOT NULL,
                amount_settled bigint NULL DEFAULT 0,
                currency varchar(3) NOT NULL DEFAULT 'RUB',
                product_type "{schema}".producttype NULL,
                quantity numeric(18, 3) NULL,
                unit_price numeric(18, 3) NULL,
                captured_amount bigint NOT NULL DEFAULT 0,
                refunded_amount bigint NOT NULL DEFAULT 0,
                daily_limit bigint NULL,
                limit_per_tx bigint NULL,
                used_today bigint NULL,
                new_used_today bigint NULL,
                limit_profile_id varchar(64) NULL,
                limit_check_result json NULL,
                authorized boolean NOT NULL DEFAULT false,
                response_code varchar(8) NOT NULL DEFAULT '00',
                response_message varchar(255) NOT NULL DEFAULT 'OK',
                auth_code varchar(32) NULL,
                parent_operation_id varchar(64) NULL,
                reason varchar(255) NULL,
                mcc varchar(8) NULL,
                product_code varchar(32) NULL,
                product_category varchar(32) NULL,
                tx_type varchar(16) NULL,
                accounts jsonb NULL,
                posting_result jsonb NULL,
                risk_score double precision NULL,
                risk_result "{schema}".riskresult NULL,
                risk_payload json NULL,
                CONSTRAINT uq_operations_operation_id UNIQUE (operation_id)
            )
            """
        )
        cur.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_operation_id "
            f'ON "{schema}".operations (operation_id)'
        )
        for index_name, columns in {
            "ix_operations_card_id": "card_id",
            "ix_operations_client_id": "client_id",
            "ix_operations_merchant_id": "merchant_id",
            "ix_operations_terminal_id": "terminal_id",
            "ix_operations_created_at": "created_at",
            "ix_operations_operation_id": "operation_id",
            "ix_operations_operation_type": "operation_type",
            "ix_operations_status": "status",
        }.items():
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f'ON "{schema}".operations ({columns})'
            )

        cur.execute("select to_regclass(%s)", (f"{schema}.operations",))
        repaired_reg = cur.fetchone()[0]
        print(
            "[entrypoint] repair completed: "
            f"{schema}.operations={repaired_reg}",
            flush=True,
        )
PY

python - <<'PY'
import os
import sys

import psycopg
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from app.db.schema import resolve_db_schema
from app.alembic.helpers import ALEMBIC_VERSION_TABLE

resolution = resolve_db_schema()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[entrypoint] DATABASE_URL is not set for post-migration verification", file=sys.stderr, flush=True)
    sys.exit(1)

cfg = Config(os.getenv("ALEMBIC_CONFIG", "app/alembic.ini"))
cfg.set_main_option("sqlalchemy.url", db_url)
expected_heads = set(ScriptDirectory.from_config(cfg).get_heads())

url = make_url(db_url)
if url.drivername.endswith("+psycopg"):
    url = url.set(drivername="postgresql")
dsn = url.render_as_string(hide_password=False)

def _quote_schema(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'

connect_kwargs = {
    "prepare_threshold": 0,
    "options": f"-c search_path={resolution.schema},public",
}

def _collect_state(cur):
    regclasses: dict[str, str | None] = {}
    cur.execute("select current_schema(), current_setting('search_path')")
    current_schema, search_path = cur.fetchone()
    cur.execute("select to_regclass(%s)", (f"{resolution.schema}.operations",))
    processing_core_reg = cur.fetchone()[0]
    cur.execute("select to_regclass(%s)", ("public.operations",))
    public_reg = cur.fetchone()[0]
    cur.execute(
        """
        SELECT n.nspname, c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname IN ('operations', %s)
        ORDER BY n.nspname
        """
    , (ALEMBIC_VERSION_TABLE,))
    pg_class_hits = cur.fetchall()
    cur.execute(
        """
        SELECT table_schema
        FROM information_schema.tables
        WHERE table_name = 'operations'
        ORDER BY table_schema
        """
    )
    operations_schemas = [row[0] for row in cur.fetchall()]
    for table in (ALEMBIC_VERSION_TABLE, "operations"):
        qualified = f"{_quote_schema(resolution.schema)}.{table}"
        cur.execute("select to_regclass(%s)", (qualified,))
        regclasses[table] = cur.fetchone()[0]

    version_reg = regclasses[ALEMBIC_VERSION_TABLE]
    versions = []
    if version_reg is not None:
        cur.execute(f'SELECT version_num FROM "{resolution.schema}".{ALEMBIC_VERSION_TABLE}')
        versions = [row[0] for row in cur.fetchall()]

    return (
        regclasses,
        versions,
        current_schema,
        search_path,
        processing_core_reg,
        public_reg,
        pg_class_hits,
        operations_schemas,
    )

with psycopg.connect(dsn, **connect_kwargs) as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        (
            regclasses,
            versions,
            current_schema,
            search_path,
            processing_core_reg,
            public_reg,
            pg_class_hits,
            operations_schemas,
        ) = _collect_state(cur)

missing = [table for table, reg in regclasses.items() if reg is None]

if ALEMBIC_VERSION_TABLE in missing:
    print(
        "[entrypoint] alembic version table missing; attempting to stamp heads: "
        f"schema_resolved={resolution.schema} search_path={search_path} current_schema={current_schema} "
        f"pg_class_hits={pg_class_hits}",
        file=sys.stderr,
        flush=True,
    )
    try:
        command.stamp(cfg, "heads")
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        print(f"[entrypoint] alembic stamp failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    with psycopg.connect(dsn, **connect_kwargs) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            (
                regclasses,
                versions,
                current_schema,
                search_path,
                processing_core_reg,
                public_reg,
                pg_class_hits,
                operations_schemas,
            ) = _collect_state(cur)
    missing = [table for table, reg in regclasses.items() if reg is None]

if missing:
    print(
        "[entrypoint] required tables missing after migrations: "
        f"schema_resolved={resolution.schema} regclass={regclasses} missing={missing} "
        f"current_schema={current_schema} search_path={search_path} "
        f"{resolution.schema}.operations={processing_core_reg} public.operations={public_reg} "
        f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

unique_versions = set(versions)
if unique_versions != expected_heads:
    print(
        "[entrypoint] alembic_version_core mismatch: "
        f"schema_resolved={resolution.schema} regclass={regclasses} "
        f"expected={sorted(expected_heads)} found={sorted(unique_versions)} "
        f"current_schema={current_schema} search_path={search_path} "
        f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

print(
    "[entrypoint] migration check passed: "
    f"schema_resolved={resolution.schema} regclass={regclasses} heads={sorted(expected_heads)} "
    f"current_schema={current_schema} search_path={search_path} "
    f"{resolution.schema}.operations={processing_core_reg} public.operations={public_reg} "
    f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
    flush=True,
)
PY

run_pytest=0
if [ "${NEFT_MODE}" = "test" ]; then
    run_pytest=1
fi
if [ "${NEFT_TEST_MODE}" = "1" ]; then
    run_pytest=1
fi
if [ "$#" -gt 0 ]; then
    for arg in "$@"; do
        case "$arg" in
            pytest|py.test|*pytest*)
                run_pytest=1
                ;;
        esac
    done
fi

if [ "$run_pytest" -eq 1 ]; then
    if [ "$#" -eq 0 ]; then
        set -- pytest
    fi
    echo "[entrypoint] test mode detected; running: $*"
    exec "$@"
fi

if [ "${ENTRYPOINT_SKIP_APP}" = "1" ]; then
    echo "[entrypoint] ENTRYPOINT_SKIP_APP=1 is set; exiting after migrations"
    exit 0
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
