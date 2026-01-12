#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

schema_resolved="${DB_SCHEMA:-${SCHEMA:-processing_core}}"
if [ -z "$schema_resolved" ]; then
    schema_resolved="processing_core"
fi
export NEFT_DB_SCHEMA="${NEFT_DB_SCHEMA:-$schema_resolved}"
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

echo "[entrypoint] ensuring alembic_version_core length"
if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint] DATABASE_URL is not set for alembic version repair" >&2
    exit 1
fi
PSQL_URL=$(printf '%s' "$DATABASE_URL" | sed 's/+psycopg//')
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<EOF
DO \$\$
DECLARE
  current_len integer;
BEGIN
  IF to_regclass('${schema_resolved}.alembic_version_core') IS NULL THEN
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', '${schema_resolved}');
    EXECUTE format(
      'CREATE TABLE %I.alembic_version_core (version_num varchar(128) NOT NULL, CONSTRAINT alembic_version_core_pkey PRIMARY KEY (version_num))',
      '${schema_resolved}'
    );
    RAISE NOTICE 'alembic_version_core created with version_num varchar(128)';
  END IF;

  SELECT character_maximum_length
    INTO current_len
    FROM information_schema.columns
   WHERE table_schema = '${schema_resolved}'
     AND table_name = 'alembic_version_core'
     AND column_name = 'version_num';

  IF current_len IS NULL THEN
    RAISE NOTICE 'alembic_version_core.version_num missing; skipping length check';
    RETURN;
  END IF;

  RAISE NOTICE 'alembic_version_core.version_num length=%', current_len;

  IF current_len < 128 THEN
    EXECUTE format(
      'ALTER TABLE %I.alembic_version_core ALTER COLUMN version_num TYPE varchar(128)',
      '${schema_resolved}'
    );
    RAISE NOTICE 'alembic_version_core.version_num length altered to 128';
  ELSE
    RAISE NOTICE 'alembic_version_core.version_num length already >= 128';
  END IF;
END \$\$;
EOF
echo "[entrypoint] alembic_version_core length check complete"

echo "[entrypoint] pre-migration cleanup: schema_resolved=${schema_resolved} search_path=${schema_resolved},public"
echo "[entrypoint] dropping orphan types/domains (pre-migration cleanup)"
if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint] DATABASE_URL is not set for orphan cleanup" >&2
    exit 1
fi
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<EOF
DO \$\$
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
END
\$\$;
EOF
echo "[entrypoint] cleanup completed"

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

echo "[entrypoint] post-migration schema repair starting..."
echo "[entrypoint] schema_resolved=${schema_resolved}"
post_migration_state=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SET search_path TO \"${schema_resolved}\",public; select current_schema(), current_setting('search_path');" | tail -n 1)
post_migration_current_schema=$(printf '%s' "$post_migration_state" | awk -F'|' '{print $1}')
post_migration_search_path=$(printf '%s' "$post_migration_state" | awk -F'|' '{print $2}')
echo "[entrypoint] schema_resolved=${schema_resolved} current_schema=${post_migration_current_schema} search_path=${post_migration_search_path}"
repair_diagnostics=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SET search_path TO \"${schema_resolved}\",public; select current_schema(), current_setting('search_path'), to_regclass('${schema_resolved}.operations'), to_regclass('${schema_resolved}.alembic_version_core'), (SELECT array_agg((n.nspname, c.relname)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = 'operations'), (SELECT array_agg(table_schema) FROM information_schema.tables WHERE table_name = 'operations');" | tail -n 1)
IFS='|' read -r diag_current_schema diag_search_path processing_core_reg alembic_version_reg pg_class_hits operations_schemas <<EOF
$repair_diagnostics
EOF
echo "[entrypoint] repair diagnostics: current_schema=${diag_current_schema} search_path=${diag_search_path} ${schema_resolved}.operations=${processing_core_reg} ${schema_resolved}.alembic_version_core=${alembic_version_reg} pg_class_hits=${pg_class_hits} operations_schemas=${operations_schemas}"
if [ -n "$processing_core_reg" ]; then
    echo "[entrypoint] repair completed: ${schema_resolved}.operations=${processing_core_reg}"
    echo "[entrypoint] post-migration schema repair completed"
else
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', '${schema_resolved}');
END \$\$;

SET search_path TO "${schema_resolved}",public;

CREATE TABLE IF NOT EXISTS "${schema_resolved}".alembic_version_core (
    version_num varchar(128) NOT NULL,
    CONSTRAINT alembic_version_core_pkey PRIMARY KEY (version_num)
);

DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = '${schema_resolved}'
      AND t.typname = 'operationtype'
  ) THEN
    EXECUTE format('CREATE TYPE %I.operationtype AS ENUM (%s)', '${schema_resolved}',
      '''AUTH'',''HOLD'',''COMMIT'',''REVERSE'',''REFUND'',''DECLINE'',''CAPTURE'',''REVERSAL'''
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = '${schema_resolved}'
      AND t.typname = 'operationstatus'
  ) THEN
    EXECUTE format('CREATE TYPE %I.operationstatus AS ENUM (%s)', '${schema_resolved}',
      '''PENDING'',''AUTHORIZED'',''HELD'',''COMPLETED'',''REVERSED'',''REFUNDED'',''DECLINED'',''CANCELLED'',''CAPTURED'',''OPEN'''
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = '${schema_resolved}'
      AND t.typname = 'producttype'
  ) THEN
    EXECUTE format('CREATE TYPE %I.producttype AS ENUM (%s)', '${schema_resolved}',
      '''DIESEL'',''AI92'',''AI95'',''AI98'',''GAS'',''OTHER'''
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = '${schema_resolved}'
      AND t.typname = 'riskresult'
  ) THEN
    EXECUTE format('CREATE TYPE %I.riskresult AS ENUM (%s)', '${schema_resolved}',
      '''LOW'',''MEDIUM'',''HIGH'',''BLOCK'',''MANUAL_REVIEW'''
    );
  END IF;
END \$\$;

CREATE TABLE IF NOT EXISTS "${schema_resolved}".operations (
    id uuid PRIMARY KEY NOT NULL,
    operation_id varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    operation_type "${schema_resolved}".operationtype NOT NULL,
    status "${schema_resolved}".operationstatus NOT NULL,
    merchant_id varchar(64) NOT NULL,
    terminal_id varchar(64) NOT NULL,
    client_id varchar(64) NOT NULL,
    card_id varchar(64) NOT NULL,
    tariff_id varchar(64) NULL,
    product_id varchar(64) NULL,
    amount bigint NOT NULL,
    amount_settled bigint NULL DEFAULT 0,
    currency varchar(3) NOT NULL DEFAULT 'RUB',
    product_type "${schema_resolved}".producttype NULL,
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
    risk_result "${schema_resolved}".riskresult NULL,
    risk_payload json NULL,
    CONSTRAINT uq_operations_operation_id UNIQUE (operation_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_operation_id
  ON "${schema_resolved}".operations (operation_id);

CREATE INDEX IF NOT EXISTS ix_operations_card_id ON "${schema_resolved}".operations (card_id);
CREATE INDEX IF NOT EXISTS ix_operations_client_id ON "${schema_resolved}".operations (client_id);
CREATE INDEX IF NOT EXISTS ix_operations_merchant_id ON "${schema_resolved}".operations (merchant_id);
CREATE INDEX IF NOT EXISTS ix_operations_terminal_id ON "${schema_resolved}".operations (terminal_id);
CREATE INDEX IF NOT EXISTS ix_operations_created_at ON "${schema_resolved}".operations (created_at);
CREATE INDEX IF NOT EXISTS ix_operations_operation_id ON "${schema_resolved}".operations (operation_id);
CREATE INDEX IF NOT EXISTS ix_operations_operation_type ON "${schema_resolved}".operations (operation_type);
CREATE INDEX IF NOT EXISTS ix_operations_status ON "${schema_resolved}".operations (status);
EOF
repaired_state=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "select to_regclass('${schema_resolved}.operations'), to_regclass('${schema_resolved}.alembic_version_core');" | tail -n 1)
IFS='|' read -r repaired_reg repaired_alembic_reg <<EOF
$repaired_state
EOF
echo "[entrypoint] repair completed: ${schema_resolved}.operations=${repaired_reg} ${schema_resolved}.alembic_version_core=${repaired_alembic_reg}"
echo "[entrypoint] post-migration schema repair completed"
fi

python - <<'PY'
import os
import sys

import psycopg
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

db_url = os.getenv("DATABASE_URL")
schema = os.getenv("NEFT_DB_SCHEMA", "processing_core").strip() or "processing_core"
ALEMBIC_VERSION_TABLE = "alembic_version_core"
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
    "options": f"-c search_path={schema},public",
}

def _collect_state(cur):
    regclasses: dict[str, str | None] = {}
    cur.execute("select current_schema(), current_setting('search_path')")
    current_schema, search_path = cur.fetchone()
    cur.execute("select to_regclass(%s)", (f"{schema}.operations",))
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
        qualified = f"{_quote_schema(schema)}.{table}"
        cur.execute("select to_regclass(%s)", (qualified,))
        regclasses[table] = cur.fetchone()[0]

    version_reg = regclasses[ALEMBIC_VERSION_TABLE]
    versions = []
    if version_reg is not None:
        cur.execute(f'SELECT version_num FROM "{schema}".{ALEMBIC_VERSION_TABLE}')
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

def _ensure_alembic_version_length(cur, *, min_length: int = 128) -> None:
    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{schema}".{ALEMBIC_VERSION_TABLE} (
            version_num VARCHAR({min_length}) NOT NULL,
            CONSTRAINT {ALEMBIC_VERSION_TABLE}_pkey PRIMARY KEY (version_num)
        )
        """
    )
    cur.execute(
        """
        SELECT character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = 'version_num'
        """,
        (schema, ALEMBIC_VERSION_TABLE),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            f"""
            ALTER TABLE "{schema}".{ALEMBIC_VERSION_TABLE}
            ADD COLUMN version_num VARCHAR({min_length}) NOT NULL
            """
        )
        current_length = None
    else:
        current_length = row[0]
    if current_length is None or current_length < min_length:
        cur.execute(
            f'ALTER TABLE "{schema}".{ALEMBIC_VERSION_TABLE} '
            f'ALTER COLUMN version_num TYPE VARCHAR({min_length})'
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
        f"schema_resolved={schema} search_path={search_path} current_schema={current_schema} "
        f"pg_class_hits={pg_class_hits}",
        file=sys.stderr,
        flush=True,
    )
    try:
        with psycopg.connect(dsn, **connect_kwargs) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                _ensure_alembic_version_length(cur)
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
        f"schema_resolved={schema} regclass={regclasses} missing={missing} "
        f"current_schema={current_schema} search_path={search_path} "
        f"{schema}.operations={processing_core_reg} public.operations={public_reg} "
        f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

unique_versions = set(versions)
if unique_versions != expected_heads:
    print(
        "[entrypoint] alembic_version_core mismatch: "
        f"schema_resolved={schema} regclass={regclasses} "
        f"expected={sorted(expected_heads)} found={sorted(unique_versions)} "
        f"current_schema={current_schema} search_path={search_path} "
        f"pg_class_hits={pg_class_hits} operations_schemas={operations_schemas}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)

print(
    "[entrypoint] migration check passed: "
    f"schema_resolved={schema} regclass={regclasses} heads={sorted(expected_heads)} "
    f"current_schema={current_schema} search_path={search_path} "
    f"{schema}.operations={processing_core_reg} public.operations={public_reg} "
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
