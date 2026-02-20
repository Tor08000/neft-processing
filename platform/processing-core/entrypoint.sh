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
VERSION_TABLE_SCHEMA="processing_core"
VERSION_TABLE_NAME="alembic_version_core"
export ALEMBIC_VERSION_TABLE_SCHEMA="$VERSION_TABLE_SCHEMA"
echo "[entrypoint] schema_resolved=${schema_resolved} version_table=${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}"

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

if [ -z "${ALEMBIC_AUTO_REPAIR+x}" ]; then
    case "${APP_ENV:-}" in
        prod|production)
            ALEMBIC_AUTO_REPAIR=0
            ;;
        *)
            ALEMBIC_AUTO_REPAIR=1
            ;;
    esac
fi
export ALEMBIC_AUTO_REPAIR
echo "[entrypoint] ALEMBIC_AUTO_REPAIR=${ALEMBIC_AUTO_REPAIR}"

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
    printf "%s\n" "$1" | awk '$1 == "Rev:" {print $2}' | tr -d '\r' | awk 'NF' | sort -u
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
    table_reg=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SELECT to_regclass('${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}');" | tail -n 1)
    if [ -n "$table_reg" ]; then
        fallback_versions=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "SELECT version_num FROM \"${schema_resolved}\".${VERSION_TABLE_NAME} ORDER BY 1;")
        fallback_versions=$(printf "%s\n" "$fallback_versions" | sed '/^[[:space:]]*$/d')
        if [ -n "$fallback_versions" ]; then
            expected_heads=$fallback_versions
            echo "[entrypoint] fallback: using existing ${VERSION_TABLE_NAME} rows as heads: $(printf "%s\n" "$expected_heads" | tr '\n' ' ')"
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
if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint] DATABASE_URL is not set for orphan cleanup" >&2
    exit 1
fi

cleanup_mode="${NEFT_ORPHAN_CLEANUP_MODE:-off}"
case "$cleanup_mode" in
    off|dry-run|drop)
        ;;
    *)
        echo "[entrypoint] invalid NEFT_ORPHAN_CLEANUP_MODE='$cleanup_mode' (expected: off|dry-run|drop)" >&2
        exit 1
        ;;
esac

echo "[entrypoint] orphan cleanup mode=${cleanup_mode}"
echo "[entrypoint] orphan cleanup policy: enums are always protected during pre-migration cleanup"
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<EOF
DO \$\$
DECLARE r record;
DECLARE has_table boolean;
DECLARE used_by_column boolean;
DECLARE has_dependents boolean;
DECLARE total int := 0;
DECLARE eligible int := 0;
DECLARE dropped int := 0;
DECLARE skipped int := 0;
DECLARE skip_reason text;
DECLARE skipped_reasons jsonb := '{}'::jsonb;
DECLARE cleanup_mode text := '${cleanup_mode}';
DECLARE allow_drop boolean := cleanup_mode = 'drop';
BEGIN
  FOR r IN (
    SELECT n.nspname AS schema_name,
           t.typname AS type_name,
           t.typtype AS type_kind,
           t.oid AS type_oid
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
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE DEBUG 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    IF r.type_kind = 'e' THEN
      skip_reason := 'enum protected in pre-migration cleanup';
      skipped := skipped + 1;
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE NOTICE 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    IF r.type_kind NOT IN ('d') THEN
      skip_reason := format('unsupported typtype=%s', r.type_kind);
      skipped := skipped + 1;
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE DEBUG 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    SELECT EXISTS (
      SELECT 1
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n2 ON n2.oid = c.relnamespace
      WHERE a.atttypid = r.type_oid
        AND a.attnum > 0
        AND NOT a.attisdropped
    ) INTO used_by_column;

    IF used_by_column THEN
      skip_reason := 'type in use';
      skipped := skipped + 1;
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE NOTICE 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    SELECT EXISTS (
      SELECT 1
      FROM pg_depend d
      WHERE d.refobjid = r.type_oid
        AND d.deptype IN ('n', 'a', 'i')
        AND d.classid <> 'pg_type'::regclass
    ) INTO has_dependents;

    IF has_dependents THEN
      skip_reason := 'type has dependents';
      skipped := skipped + 1;
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE NOTICE 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      CONTINUE;
    END IF;

    eligible := eligible + 1;
    IF NOT allow_drop THEN
      skip_reason := format('mode=%s', cleanup_mode);
      skipped := skipped + 1;
      skipped_reasons := jsonb_set(
        skipped_reasons,
        ARRAY[skip_reason],
        to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
        true
      );
      RAISE NOTICE 'orphan cleanup candidate: schema=% type=% typtype=%', r.schema_name, r.type_name, r.type_kind;
    ELSE
      BEGIN
        IF r.type_kind = 'd' THEN
          EXECUTE format('DROP DOMAIN IF EXISTS %I.%I', r.schema_name, r.type_name);
        ELSE
          EXECUTE format('DROP TYPE IF EXISTS %I.%I', r.schema_name, r.type_name);
        END IF;
        dropped := dropped + 1;
        RAISE NOTICE 'orphan cleanup drop: schema=% type=% typtype=% reason=dropped', r.schema_name, r.type_name, r.type_kind;
      EXCEPTION WHEN OTHERS THEN
        skip_reason := SQLERRM;
        skipped := skipped + 1;
        skipped_reasons := jsonb_set(
          skipped_reasons,
          ARRAY[skip_reason],
          to_jsonb(COALESCE((skipped_reasons ->> skip_reason)::int, 0) + 1),
          true
        );
        RAISE NOTICE 'orphan cleanup skip: schema=% type=% typtype=% reason=%', r.schema_name, r.type_name, r.type_kind, skip_reason;
      END;
    END IF;
  END LOOP;

  RAISE NOTICE 'pre-migration cleanup: orphan types/domains found_total %, eligible_to_drop %, dropped %, skipped_with_reason %, skip_reasons %',
    total, eligible, dropped, skipped, skipped_reasons;

  IF allow_drop AND dropped > 0 THEN
    RAISE EXCEPTION 'cleanup dropped % types/domains, unsafe; rerun with NEFT_ORPHAN_CLEANUP_MODE=off', dropped;
  END IF;
END
\$\$;
EOF
echo "[entrypoint] cleanup completed"

echo "[entrypoint] ensuring alembic version consistency"
ALEMBIC_DECISION_FILE=${ALEMBIC_DECISION_FILE:-/tmp/alembic_decision.env}
export ALEMBIC_DECISION_FILE
python -m app.scripts.alembic_version_repair
if [ -f "$ALEMBIC_DECISION_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ALEMBIC_DECISION_FILE"
    set +a
fi
ALEMBIC_DECISION=${ALEMBIC_MODE:-UPGRADE}
echo "[entrypoint] decision mode=${ALEMBIC_DECISION}"

if [ "$ALEMBIC_DECISION" = "SKIP" ]; then
    PREFLIGHT_AUTH_MODE_FILE=${PREFLIGHT_AUTH_MODE_FILE:-/tmp/core_required_tables_auth_mode.txt}
    PREFLIGHT_MISSING_FILE=${PREFLIGHT_MISSING_FILE:-/tmp/core_required_tables_missing.txt}
    export PREFLIGHT_AUTH_MODE_FILE PREFLIGHT_MISSING_FILE

    python - <<'PY'
import os
from pathlib import Path

from app.db import DB_SCHEMA, get_engine
from app.services.startup_validation import (
    get_auth_host_mode,
    validate_required_tables,
)

auth_mode = get_auth_host_mode()
missing = validate_required_tables(get_engine(), schema=DB_SCHEMA, auth_mode=auth_mode)
Path(os.environ["PREFLIGHT_AUTH_MODE_FILE"]).write_text(auth_mode + "\n", encoding="utf-8")
Path(os.environ["PREFLIGHT_MISSING_FILE"]).write_text("\n".join(missing), encoding="utf-8")
print(
    "[entrypoint] preflight required tables check: "
    f"auth_mode={auth_mode} missing={missing if missing else '[]'}",
    flush=True,
)
PY

    auth_mode_preflight=$(cat "$PREFLIGHT_AUTH_MODE_FILE" 2>/dev/null | tr -d '\r\n')
    missing_required_tables=$(cat "$PREFLIGHT_MISSING_FILE" 2>/dev/null | sed '/^[[:space:]]*$/d' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$missing_required_tables" ]; then
        echo "[entrypoint] missing tables detected -> overriding mode to UPGRADE (auth_mode=${auth_mode_preflight} missing=${missing_required_tables})"
        ALEMBIC_DECISION="UPGRADE"
    fi
fi

run_upgrade() {
    echo "[entrypoint] running pre-upgrade sanity-check"
    python -m app.scripts.alembic_upgrade_preflight
    echo "[entrypoint] applying migrations via alembic upgrade head ($ALEMBIC_CONFIG)"
    alembic -c "$ALEMBIC_CONFIG" upgrade head >"$MIGRATION_LOG" 2>&1
    alembic_exit_code=$?
    echo "[entrypoint] alembic upgrade exit_code=${alembic_exit_code}"
    return "$alembic_exit_code"
}

set +e
case "$ALEMBIC_DECISION" in
    SKIP)
        echo "[entrypoint] decision=SKIP, skipping alembic migrate action"
        migration_status=0
        ;;
    UPGRADE)
        run_upgrade
        migration_status=$?
        ;;
    FAIL)
        echo "[entrypoint] decision=FAIL, refusing to run alembic command" >&2
        migration_status=1
        ;;
    *)
        echo "[entrypoint] unknown decision '$ALEMBIC_DECISION', refusing startup" >&2
        migration_status=1
        ;;
esac
set -e

if [ "$migration_status" -ne 0 ]; then
    if [ "$ALEMBIC_DECISION" = "UPGRADE" ]; then
        echo "[entrypoint] alembic upgrade exit_code=${migration_status}" >&2
        echo "[entrypoint] tail -n 120 ${MIGRATION_LOG}" >&2
        tail -n 120 "$MIGRATION_LOG" >&2 || true
    else
        echo "[entrypoint] migration validation failed; last log lines:" >&2
        tail -n 200 "$MIGRATION_LOG" >&2 || true
    fi
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
set +e
repair_diagnostics=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "select current_schema(), current_setting('search_path'), to_regclass('${schema_resolved}.operations'), to_regclass('${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}'), (SELECT array_agg((n.nspname, c.relname)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = 'operations'), (SELECT array_agg(table_schema) FROM information_schema.tables WHERE table_name = 'operations');")
repair_status=$?
set -e

if [ "$repair_status" -ne 0 ]; then
    echo "[entrypoint] WARNING: schema repair diagnostics failed; continuing startup (status=$repair_status)"
    processing_core_reg=""
    alembic_version_reg=""
else
    repair_diagnostics=$(printf '%s\n' "$repair_diagnostics" | tail -n 1)
    IFS='|' read -r diag_current_schema diag_search_path processing_core_reg alembic_version_reg pg_class_hits operations_schemas <<EOF
$repair_diagnostics
EOF
    echo "[entrypoint] repair diagnostics: current_schema=${diag_current_schema} search_path=${diag_search_path} ${schema_resolved}.operations=${processing_core_reg} ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}=${alembic_version_reg} pg_class_hits=${pg_class_hits} operations_schemas=${operations_schemas}"
fi

if [ -z "$processing_core_reg" ]; then
set +e
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', '${schema_resolved}');
END \$\$;

DO \$\$
BEGIN
  EXECUTE format('SET search_path TO %I, public', '${schema_resolved}');
END \$\$;

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
repair_apply_status=$?
set -e

if [ "$repair_apply_status" -ne 0 ]; then
    echo "[entrypoint] WARNING: schema repair DDL failed; continuing startup in fail-open mode (status=$repair_apply_status)"
fi

set +e
repaired_state=$(psql "$PSQL_URL" -v ON_ERROR_STOP=1 -Atc "select to_regclass('${schema_resolved}.operations'), to_regclass('${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}');")
repaired_state_status=$?
set -e

if [ "$repaired_state_status" -ne 0 ]; then
    echo "[entrypoint] WARNING: schema repair post-check failed; continuing startup (status=$repaired_state_status)"
    repaired_reg=""
    repaired_alembic_reg=""
else
repaired_state=$(printf '%s\n' "$repaired_state" | tail -n 1)
IFS='|' read -r repaired_reg repaired_alembic_reg <<EOF
$repaired_state
EOF
fi
echo "[entrypoint] post-migration schema repair completed: ${schema_resolved}.operations=${repaired_reg} ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}=${repaired_alembic_reg}"
else
    echo "[entrypoint] post-migration schema repair completed: ${schema_resolved}.operations=${processing_core_reg} ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}=${alembic_version_reg}"
fi

echo "[entrypoint] post-migration version validation starting"

validate_lineage_against_heads() {
    current_revision="$1"
    script_heads="$2"
    CURRENT_REVISION="$current_revision" SCRIPT_HEADS="$script_heads" ALEMBIC_CONFIG="$ALEMBIC_CONFIG" python - <<'PY'
import os

from alembic.config import Config
from alembic.script import ScriptDirectory


def normalize_parents(down_revision: object) -> tuple[str, ...]:
    if down_revision is None:
        return ()
    if isinstance(down_revision, str):
        return (down_revision,)
    if isinstance(down_revision, (tuple, list, set)):
        return tuple(str(item) for item in down_revision if item)
    return (str(down_revision),)


def is_ancestor(script: ScriptDirectory, ancestor: str, head: str) -> bool:
    stack = [head]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == ancestor:
            return True
        if current in visited:
            continue
        visited.add(current)
        revision = script.get_revision(current)
        if revision is None:
            continue
        stack.extend(normalize_parents(revision.down_revision))
    return False


current_revision = os.getenv("CURRENT_REVISION", "").strip()
heads = [line.strip() for line in os.getenv("SCRIPT_HEADS", "").splitlines() if line.strip()]
if not current_revision:
    raise RuntimeError("CURRENT_REVISION is empty")
if not heads:
    raise RuntimeError("SCRIPT_HEADS is empty")

config = Config(os.getenv("ALEMBIC_CONFIG", "/app/app/alembic.ini"))
script = ScriptDirectory.from_config(config)

if any(is_ancestor(script, current_revision, head) for head in heads):
    print(f"lineage OK: current={current_revision} heads={heads}")
else:
    raise RuntimeError(f"lineage mismatch: current={current_revision} is not ancestor of heads={heads}")
PY
}

validate_revision_is_head() {
    current_revision="$1"
    script_heads="$2"
    CURRENT_REVISION="$current_revision" SCRIPT_HEADS="$script_heads" python - <<'PY'
import os

current_revision = os.getenv("CURRENT_REVISION", "").strip()
heads = [line.strip() for line in os.getenv("SCRIPT_HEADS", "").splitlines() if line.strip()]
if not current_revision:
    raise RuntimeError("CURRENT_REVISION is empty")
if not heads:
    raise RuntimeError("SCRIPT_HEADS is empty")

if current_revision in heads:
    print(f"head OK: current={current_revision} heads={heads}")
else:
    raise RuntimeError(f"head mismatch: current={current_revision} is not in script heads={heads}")
PY
}

count_lines() {
    values="$1"
    if [ -z "$values" ]; then
        echo "0"
        return
    fi
    printf "%s\n" "$values" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' '
}

format_list() {
    values="$1"
    if [ -z "$values" ]; then
        printf "[]"
        return
    fi

    joined=$(printf "%s\n" "$values" | sed '/^[[:space:]]*$/d' | awk 'NR==1 {printf "%s", $0; next} {printf ", %s", $0}')
    printf "[%s]" "$joined"
}

get_sql_versions() {
    psql "$PSQL_URL" -q -v ON_ERROR_STOP=1 -tA -c \
        "SELECT version_num FROM ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME} ORDER BY version_num;" \
        | tr -d '\r' | sed '/^[[:space:]]*$/d'
}

list_alembic_version_tables() {
    psql "$PSQL_URL" -q -v ON_ERROR_STOP=1 -tA -c \
        "SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_name ILIKE 'alembic%version%' ORDER BY table_schema, table_name;" \
        | tr -d '\r' | sed '/^[[:space:]]*$/d'
}

sql_versions=$(get_sql_versions)
sql_rows_count=$(count_lines "$sql_versions")
sql_current=$(printf "%s\n" "$sql_versions" | sed '/^[[:space:]]*$/d' | tail -n 1)
echo "[entrypoint] sql_versions=$(format_list "$sql_versions")"
echo "[entrypoint] rows_count=${sql_rows_count}"
echo "[entrypoint] sql_current=${sql_current:-<base>}"

if [ "$ALEMBIC_DECISION" = "SKIP" ]; then
    if [ "$sql_rows_count" -ne 1 ]; then
        echo "[entrypoint] version table mismatch: SKIP expects exactly 1 row in ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}, got ${sql_rows_count}" >&2
        exit 1
    fi
    echo "[entrypoint] decision=SKIP => validating lineage(current in ancestors of script heads)"
    if ! validate_lineage_against_heads "$sql_current" "$expected_heads"; then
        echo "[entrypoint] version table mismatch: SKIP requires lineage compatibility with script heads" >&2
        exit 1
    fi
else
    if [ "$sql_rows_count" -eq 0 ]; then
        echo "[entrypoint] upgrade reported success but version table empty (${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME})" >&2
        echo "[entrypoint] alembic version-like tables:" >&2
        table_list=$(list_alembic_version_tables)
        if [ -n "$table_list" ]; then
            printf "%s\n" "$table_list" | sed 's/^/[entrypoint]   /' >&2
        else
            echo "[entrypoint]   <none>" >&2
        fi
        exit 1
    fi
    if [ "$sql_rows_count" -ne 1 ]; then
        echo "[entrypoint] version table mismatch: ${ALEMBIC_DECISION} expects exactly 1 row in ${VERSION_TABLE_SCHEMA}.${VERSION_TABLE_NAME}, got ${sql_rows_count}" >&2
        exit 1
    fi
    echo "[entrypoint] decision=${ALEMBIC_DECISION} => validating sql_current is one of script heads"
    if ! validate_revision_is_head "$sql_current" "$expected_heads"; then
        echo "[entrypoint] version table mismatch: ${ALEMBIC_DECISION} requires sql_current to match script head" >&2
        echo "[entrypoint] current SQL versions: $(format_list "$sql_versions")" >&2
        echo "[entrypoint] expected script heads: $(format_list "$expected_heads")" >&2
        exit 1
    fi
fi

echo "[entrypoint] version validation OK: current=${sql_current}"

echo "[entrypoint] validating required tables using auth-aware validator"
if ! python -m app.services.startup_validation; then
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
