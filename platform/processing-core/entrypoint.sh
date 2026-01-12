#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

schema_resolved="${DB_SCHEMA:-${SCHEMA:-processing_core}}"
if [ -z "$schema_resolved" ]; then
    schema_resolved="processing_core"
fi
export NEFT_DB_SCHEMA="${NEFT_DB_SCHEMA:-$schema_resolved}"
export DB_SCHEMA="${DB_SCHEMA:-$schema_resolved}"
export ALEMBIC_VERSION_TABLE_SCHEMA="${ALEMBIC_VERSION_TABLE_SCHEMA:-$schema_resolved}"
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

ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-/app/app/alembic.ini}
MIGRATION_LOG=${MIGRATION_LOG:-/tmp/alembic_migration.log}

if [ ! -f "$ALEMBIC_CONFIG" ]; then
    echo "[entrypoint] missing alembic config: $ALEMBIC_CONFIG" >&2
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint] DATABASE_URL is not set for alembic version repair" >&2
    exit 1
fi
PSQL_URL=$(printf '%s' "$DATABASE_URL" | sed 's/+psycopg//')

extract_heads() {
    printf "%s\n" "$1" | awk '/^Rev: / {print $2}' | tr -d '\r' | awk 'NF' | sort -u
}

run_diag_cmd() {
    echo "[entrypoint] diag: $*"
    set +e
    output=$("$@" 2>&1)
    status=$?
    set -e
    if [ -n "$output" ]; then
        printf "%s\n" "$output" | sed 's/^/[entrypoint]   /'
    fi
    return $status
}

get_found_versions() {
    table_reg=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT to_regclass('${schema_resolved}.alembic_version_core');" | tail -n 1)
    if [ -z "$table_reg" ]; then
        return 0
    fi
    psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT version_num FROM ${schema_resolved}.alembic_version_core ORDER BY 1;" \
        | tr -d '\r' | sed '/^[[:space:]]*$/d'
}

run_alembic_current_verbose() {
    echo "[entrypoint] alembic current -v"
    run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini current -v"
}

run_empty_stamp_diagnostics() {
    run_alembic_current_verbose
    run_diag_cmd psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT to_regclass('${schema_resolved}.alembic_version');"
    run_diag_cmd psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT to_regclass('public.alembic_version');"

    schema_table=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT to_regclass('${schema_resolved}.alembic_version');" | tail -n 1)
    if [ -n "$schema_table" ]; then
        run_diag_cmd psql "$PSQL_URL" -v ON_ERROR_STOP=1 -c \
            "SELECT * FROM ${schema_resolved}.alembic_version;"
    fi

    public_table=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -tA -c \
        "SELECT to_regclass('public.alembic_version');" | tail -n 1)
    if [ -n "$public_table" ]; then
        run_diag_cmd psql "$PSQL_URL" -v ON_ERROR_STOP=1 -c \
            "SELECT * FROM public.alembic_version;"
    fi
}

run_alembic_stamp() {
    head="$1"
    stamp_log=$(mktemp)
    set +e
    alembic -q -c "$ALEMBIC_CONFIG" stamp "$head" >"$stamp_log" 2>&1
    stamp_status=$?
    set -e
    cat "$stamp_log" >>"$MIGRATION_LOG"
    echo "[entrypoint] alembic stamp exit code for $head: $stamp_status"
    echo "[entrypoint] alembic stamp last 30 lines for $head:"
    tail -n 30 "$stamp_log" | sed 's/^/[entrypoint]   /'
    rm -f "$stamp_log"
    return $stamp_status
}

echo "[entrypoint] checking alembic heads via ($ALEMBIC_CONFIG)"
heads_output=$(cd /app && alembic -c /app/app/alembic.ini heads --verbose 2>&1)
heads_status=$?
echo "[entrypoint] alembic heads raw output (first 5 lines):"
printf "%s\n" "$heads_output" | head -n 5 | sed 's/^/[entrypoint]   /'
echo "[entrypoint] alembic heads raw output line count: $(printf "%s\n" "$heads_output" | wc -l | tr -d ' ')"
if [ "$heads_status" -ne 0 ]; then
    echo "[entrypoint] alembic heads failed with status $heads_status" >&2
    run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini current"
    run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini history --verbose | tail -n 50"
    run_diag_cmd ls -la /app/app/alembic.ini
    run_diag_cmd sh -c "ls -la /app/app/alembic/versions | tail -n 50"
    run_diag_cmd grep -E "script_location|version_locations" -n /app/app/alembic.ini
    echo "[entrypoint] alembic heads failed output: $heads_output" >&2
    exit 1
fi

expected_heads=$(extract_heads "$heads_output")
if [ -z "$expected_heads" ]; then
    echo "[entrypoint] alembic heads parsed empty; running diagnostics" >&2
    run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini current"
    run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini history --verbose | tail -n 50"
    run_diag_cmd ls -la /app/app/alembic.ini
    run_diag_cmd sh -c "ls -la /app/app/alembic/versions | tail -n 50"
    run_diag_cmd grep -E "script_location|version_locations" -n /app/app/alembic.ini

    set +e
    heads_check=$(cd /app && alembic -c /app/app/alembic.ini heads --verbose 2>&1)
    heads_check_status=$?
    set -e
    if [ "$heads_check_status" -ne 0 ]; then
        echo "[entrypoint] alembic heads failed during diagnostics: $heads_check" >&2
        exit 1
    fi

    expected_heads=""
    table_reg=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SELECT to_regclass('${schema_resolved}.alembic_version_core');" | tail -n 1)
    if [ -n "$table_reg" ]; then
        fallback_versions=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SELECT version_num FROM \"${schema_resolved}\".alembic_version_core ORDER BY 1;")
        fallback_versions=$(printf "%s\n" "$fallback_versions" | sed '/^[[:space:]]*$/d')
        if [ -n "$fallback_versions" ]; then
            expected_heads=$fallback_versions
            echo "[entrypoint] fallback: using existing alembic_version_core rows as heads: $(printf "%s\n" "$expected_heads" | tr '\n' ' ')"
        fi
    fi

    if [ -z "$expected_heads" ]; then
        fallback_heads=$(python - <<'PY'
import ast
import glob
import re

revisions = []
down_revisions = set()

for path in glob.glob("/app/app/alembic/versions/*.py"):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    rev_match = re.search(r"^revision\s*=\s*(.+)$", text, re.M)
    down_match = re.search(r"^down_revision\s*=\s*(.+)$", text, re.M)
    if not rev_match:
        continue
    revision = ast.literal_eval(rev_match.group(1).strip())
    revisions.append(revision)
    if not down_match:
        continue
    down_raw = ast.literal_eval(down_match.group(1).strip())
    if down_raw is None:
        continue
    if isinstance(down_raw, (list, tuple, set)):
        down_revisions.update(down_raw)
    else:
        down_revisions.add(down_raw)

heads = sorted({rev for rev in revisions if rev not in down_revisions})
for head in heads:
    print(head)
PY
)
        fallback_heads=$(printf "%s\n" "$fallback_heads" | sed '/^[[:space:]]*$/d')
        if [ -n "$fallback_heads" ]; then
            expected_heads=$fallback_heads
            echo "[entrypoint] fallback: derived heads from alembic/versions: $(printf "%s\n" "$expected_heads" | tr '\n' ' ')"
        fi
    fi

    if [ -z "$expected_heads" ]; then
        echo "[entrypoint] unable to resolve alembic heads after diagnostics and fallbacks" >&2
        exit 1
    fi
fi

echo "[entrypoint] parsed heads: [$(printf "%s\n" "$expected_heads" | tr '\n' ' ')]"

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
DECLARE eligible int := 0;
DECLARE dropped int := 0;
DECLARE skipped int := 0;
DECLARE skip_reason text;
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

    IF has_table THEN
      skip_reason := 'table exists';
      skipped := skipped + 1;
      RAISE DEBUG 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    IF r.type_kind NOT IN ('d', 'e') THEN
      skip_reason := format('unsupported typtype=%s', r.type_kind);
      skipped := skipped + 1;
      RAISE DEBUG 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    eligible := eligible + 1;
    BEGIN
      IF r.type_kind = 'd' THEN
        EXECUTE format('DROP DOMAIN IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name);
      ELSE
        EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name);
      END IF;
      dropped := dropped + 1;
      RAISE DEBUG 'orphan cleanup drop: schema=% type=% typtype=% reason=dropped', r.schema_name, r.type_name, r.type_kind;
    EXCEPTION WHEN OTHERS THEN
      skip_reason := SQLERRM;
      skipped := skipped + 1;
      RAISE NOTICE 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
    END;
  END LOOP;

  RAISE NOTICE 'pre-migration cleanup: orphan types/domains found_total %, eligible_to_drop %, dropped %, skipped_with_reason %', total, eligible, dropped, skipped;
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

echo "[entrypoint] post-migration version validation starting"
expected_heads_sorted=$(printf "%s\n" "$expected_heads" | sort -u)
found_versions=$(get_found_versions)
found_versions_sorted=$(printf "%s\n" "$found_versions" | sort -u)
echo "[entrypoint] found versions: [$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]"
if [ -z "$found_versions" ]; then
    echo "[entrypoint] alembic_version_core empty; stamping expected heads"
    for head in $expected_heads; do
        if ! alembic -c "$ALEMBIC_CONFIG" history --verbose | grep -q "$head"; then
            echo "[entrypoint] alembic history missing revision $head; refusing to stamp" >&2
            run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini heads --verbose"
            run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini history --verbose | tail -n 50"
            exit 1
        fi
        echo "[entrypoint] stamping alembic head $head"
        if ! run_alembic_stamp "$head"; then
            echo "[entrypoint] alembic stamp failed for head $head; last log lines:" >&2
            tail -n 200 "$MIGRATION_LOG" >&2 || true
            exit 1
        fi
    done
    run_alembic_current_verbose
    found_versions=$(get_found_versions)
    found_versions_sorted=$(printf "%s\n" "$found_versions" | sort -u)
    echo "[entrypoint] found versions after stamp: [$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]"
    if [ -z "$found_versions" ]; then
        echo "[entrypoint] alembic_version_core empty after stamp; running diagnostics" >&2
        run_empty_stamp_diagnostics
    fi
fi

if [ -z "$found_versions" ]; then
    echo "[entrypoint] alembic_version_core still empty after stamp; refusing to start" >&2
    exit 1
fi

if [ "$expected_heads_sorted" != "$found_versions_sorted" ]; then
    echo "[entrypoint] alembic_version_core mismatch: expected=[$(printf "%s\n" "$expected_heads_sorted" | tr '\n' ' ')] found=[$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]" >&2
    echo "[entrypoint] attempting to stamp expected heads after mismatch" >&2
    for head in $expected_heads; do
        if ! alembic -c "$ALEMBIC_CONFIG" history --verbose | grep -q "$head"; then
            echo "[entrypoint] alembic history missing revision $head; refusing to stamp" >&2
            run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini heads --verbose"
            run_diag_cmd sh -c "cd /app && alembic -c /app/app/alembic.ini history --verbose | tail -n 50"
            exit 1
        fi
        echo "[entrypoint] stamping alembic head $head"
        if ! run_alembic_stamp "$head"; then
            echo "[entrypoint] alembic stamp failed for head $head; last log lines:" >&2
            tail -n 200 "$MIGRATION_LOG" >&2 || true
            exit 1
        fi
    done
    run_alembic_current_verbose
    found_versions=$(get_found_versions)
    found_versions_sorted=$(printf "%s\n" "$found_versions" | sort -u)
    echo "[entrypoint] found versions after mismatch stamp: [$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]"
    if [ -z "$found_versions" ]; then
        echo "[entrypoint] alembic_version_core empty after mismatch stamp; running diagnostics" >&2
        run_empty_stamp_diagnostics
    fi
fi

if [ -z "$found_versions" ]; then
    echo "[entrypoint] alembic_version_core empty after retry; refusing to start" >&2
    exit 1
fi

if [ "$expected_heads_sorted" != "$found_versions_sorted" ]; then
    echo "[entrypoint] alembic_version_core mismatch after stamp: expected=[$(printf "%s\n" "$expected_heads_sorted" | tr '\n' ' ')] found=[$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]" >&2
    exit 1
fi

echo "[entrypoint] version validation OK: heads=[$(printf "%s\n" "$found_versions_sorted" | tr '\n' ' ')]"

required_state=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SET search_path TO \"${schema_resolved}\",public; SELECT to_regclass('${schema_resolved}.operations'), to_regclass('${schema_resolved}.alembic_version_core');" | tail -n 1)
IFS='|' read -r required_operations required_version_table <<EOF
$required_state
EOF
if [ -z "$required_operations" ] || [ -z "$required_version_table" ]; then
    echo "[entrypoint] required tables missing after migrations: ${schema_resolved}.operations=${required_operations} ${schema_resolved}.alembic_version_core=${required_version_table}" >&2
    exit 1
fi

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
