#!/usr/bin/env sh
set -e

echo "[entrypoint] core-api starting"

# Ensure shared python package is importable even if PYTHONPATH was not
# propagated for some reason (e.g. overridden by docker-compose env).
export PYTHONPATH="/opt/python:/app:${PYTHONPATH}"

python - <<'PY'
import os
from sqlalchemy.engine.url import make_url
from app.db import resolve_db_schema, schema_resolution_line

db_url = os.getenv("DATABASE_URL")
schema, source = resolve_db_schema()

print(f"[entrypoint] {schema_resolution_line(schema, source)}", flush=True)

if not db_url:
    print("[entrypoint] DATABASE_URL is not set", flush=True)
else:
    masked = make_url(db_url).render_as_string(hide_password=True)
    search_path = f"{schema},public" if schema else "public"
    print(f"[entrypoint] DATABASE_URL={masked}", flush=True)
    print(f"[entrypoint] DB_SCHEMA={schema} search_path={search_path}", flush=True)
PY

eval "$(python - <<'PY'
from app.db import resolve_db_schema

schema, source = resolve_db_schema()

print(f'DB_SCHEMA_RESOLVED=\"{schema}\"')
print(f'DB_SCHEMA_SOURCE=\"{source}\"')
PY
)"

schema="${DB_SCHEMA_RESOLVED:-public}"

wait_for_postgres() {
    python - <<'PY'
import os
import sys
import time

from sqlalchemy.engine import make_url
import psycopg

dsn = os.getenv("DATABASE_URL")
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
interval = int(os.getenv("DB_WAIT_INTERVAL", "2"))

deadline = time.time() + timeout
last_error = None


def _normalize_postgres_dsn(raw: str) -> str:
    """Convert SQLAlchemy-style URLs to psycopg-friendly DSNs.

    psycopg accepts plain libpq connection strings and "postgresql://" URLs, but
    will reject dialect suffixes like ``postgresql+psycopg://``. To support both
    DSN styles used by the project we normalise URLs with a scheme by stripping
    driver aliases and rendering them without hiding the password.
    """

    if "postgresql" not in raw:
        return raw

    if "://" not in raw:
        return raw

    try:
        url = make_url(raw)
    except Exception:
        return raw

    if not url.drivername.startswith("postgresql"):
        return raw

    safe_url = url.set(drivername="postgresql")
    return safe_url.render_as_string(hide_password=False)


if not dsn:
    print("[entrypoint] DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

dsn = _normalize_postgres_dsn(dsn)

while time.time() < deadline:
    try:
        with psycopg.connect(dsn, connect_timeout=5, prepare_threshold=0) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] postgres is not ready after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

wait_for_redis() {
    python - <<'PY'
import os
import sys
import time

import redis

url = os.getenv("REDIS_URL")
timeout = int(os.getenv("REDIS_WAIT_TIMEOUT", "60"))
interval = int(os.getenv("REDIS_WAIT_INTERVAL", "2"))

deadline = time.time() + timeout
last_error = None
client = redis.Redis.from_url(url)

while time.time() < deadline:
    try:
        client.ping()
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - entrypoint diagnostics
        last_error = exc
        time.sleep(interval)

print(f"[entrypoint] redis is not ready after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

echo "[entrypoint] waiting for postgres..."
wait_for_postgres
if [ "${SKIP_REDIS_WAIT}" != "1" ]; then
    echo "[entrypoint] waiting for redis..."
    wait_for_redis
fi

# Shared diagnostics helpers
dump_migration_diagnostics() {
    set +e
    echo "[entrypoint] alembic heads output:" >&2
    alembic -c "$ALEMBIC_CONFIG" heads
    echo "[entrypoint] alembic current output:" >&2
    alembic -c "$ALEMBIC_CONFIG" current
    echo "[entrypoint] table inventory (all schemas):" >&2
    python - <<'PY'
from app.diagnostics.db_state import collect_inventory

inventory = collect_inventory()
for schema, table in inventory.tables:
    print(f"{schema}.{table}")
PY
    set -e
}

capture_db_id() {
    eval "$(
        DB_ID_PREFIX="$1" python - <<'PY'
import os
import shlex
import sys

from sqlalchemy import create_engine, text

from app.db import resolve_db_schema, schema_resolution_line

prefix = os.environ["DB_ID_PREFIX"]
url = os.getenv("DATABASE_URL")
schema, schema_source = resolve_db_schema()

if not url:
    print("[entrypoint] DATABASE_URL is not set for DB identity probe", file=sys.stderr)
    sys.exit(1)

engine_kwargs = {"future": True, "pool_pre_ping": True}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "options": f"-csearch_path={schema},public",
        "prepare_threshold": 0,
    }

engine = create_engine(url, **engine_kwargs)

with engine.connect() as conn:
    server_addr, server_port, current_db, current_user = conn.execute(
        text("select inet_server_addr(), inet_server_port(), current_database(), current_user")
    ).one()
    db_oid = conn.execute(text("select oid from pg_database where datname=current_database();")).scalar_one_or_none()
    postmaster_start = conn.execute(text("select pg_postmaster_start_time();")).scalar_one_or_none()

def export(name: str, value) -> None:
    printable = "" if value is None else str(value)
    print(f"{name}={shlex.quote(printable)}")

line = (
    f"DB_ID[{prefix}]: host={server_addr} port={server_port} db={current_db} "
    f"user={current_user} db_oid={db_oid} postmaster_start_time={postmaster_start} schema={schema}"
)
export(f"DB_ID_{prefix}_ADDR", server_addr)
export(f"DB_ID_{prefix}_PORT", server_port)
export(f"DB_ID_{prefix}_DB", current_db)
export(f"DB_ID_{prefix}_USER", current_user)
export(f"DB_ID_{prefix}_OID", db_oid)
export(f"DB_ID_{prefix}_PM", postmaster_start)
export(f"DB_ID_{prefix}_SCHEMA", schema)
export(f"DB_ID_{prefix}_SOURCE", schema_source)
export(f"DB_ID_{prefix}_LINE", line)
print(f"echo {shlex.quote('[entrypoint] ' + schema_resolution_line(schema, schema_source))}")
print(f"echo {shlex.quote('[entrypoint] ' + line)}")
PY
    )"
}

assert_db_identity_stable() {
    if [ -z "${DB_ID_PRE_OID}" ] || [ -z "${DB_ID_POST_OID}" ]; then
        echo "[entrypoint] DB identity guard missing required values" >&2
        exit 1
    fi

    if [ "${DB_ID_PRE_OID}" != "${DB_ID_POST_OID}" ] || [ "${DB_ID_PRE_PM}" != "${DB_ID_POST_PM}" ]; then
        echo "[entrypoint] DB instance changed mid-run: pre oid=${DB_ID_PRE_OID} post oid=${DB_ID_POST_OID} pre start=${DB_ID_PRE_PM} post start=${DB_ID_POST_PM}" >&2
        exit 1
    fi
}

verify_migration_ddls() {
    python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, event, text

from app.diagnostics.db_state import to_regclass
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.getenv("DATABASE_URL")
required_tables = (
    "alembic_version",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
)

if not url:
    print("[entrypoint] DATABASE_URL is not set for migration verification", file=sys.stderr)
    sys.exit(1)

debug_sql = os.getenv("DB_DEBUG_SQL") == "1"
engine_kwargs = {"future": True, "pool_pre_ping": True, "echo": debug_sql}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "options": f"-csearch_path={schema},public",
        "prepare_threshold": 0,
    }

engine = create_engine(url, **engine_kwargs)

if debug_sql:
    def _log_event(conn, *_args, _name):
        print(
            f"[entrypoint] DB_DEBUG_SQL: {_name.upper()} connection={hex(id(conn))}",
            flush=True,
        )

    for name in ("begin", "commit", "rollback", "close"):
        event.listen(engine, name, lambda conn, *_args, _name=name: _log_event(conn, _name=_name))


def _collect_required_tables() -> dict[str, str | None]:
    with engine.connect() as conn:
        return {name: to_regclass(conn, schema, name) for name in required_tables}


def _collect_inventory() -> tuple[list[str], list[str]]:
    with engine.connect() as conn:
        user_schemas = conn.execute(
            text(
                """
                select nspname
                from pg_namespace
                where nspname not in ('pg_catalog','information_schema','pg_toast')
                order by 1
                """
            )
        ).scalars().all()
        user_tables = [
            f"{row.table_schema}.{row.table_name}"
            for row in conn.execute(
                text(
                    """
                    select table_schema, table_name
                    from information_schema.tables
                    where table_schema not in ('pg_catalog','information_schema','pg_toast')
                    order by 1,2
                    """
                )
            )
        ]
    return user_schemas, user_tables


results = _collect_required_tables()
missing = [name for name, reg in results.items() if reg is None]
if missing:
    user_schemas, user_tables = _collect_inventory()
    print(
        f"[entrypoint] migration verification failed; missing tables in schema '{schema}': {missing}",
        file=sys.stderr,
    )
    print(f"[entrypoint] user schemas: {user_schemas}", file=sys.stderr)
    print(f"[entrypoint] user tables ({len(user_tables)}): {user_tables}", file=sys.stderr)
    print(
        "[entrypoint] hint: docker compose logs --tail=200 postgres to check if the DB was reset",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    f"[entrypoint] verified required tables exist in schema '{schema}': {sorted(results)}",
    flush=True,
)
PY
}

after_commit_visibility_probe() {
    python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
if not url:
    print("[entrypoint] DATABASE_URL is not set for after-commit probe", file=sys.stderr)
    sys.exit(1)

engine = create_engine(
    url,
    future=True,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": 0} if url.startswith("postgresql") else {},
    echo=os.getenv("DB_DEBUG_SQL") == "1",
)

with engine.connect() as conn:
    alembic_reg = conn.execute(
        text("select to_regclass(:regclass)"), {"regclass": f"{schema}.alembic_version"}
    ).scalar_one_or_none()
    operations_reg = conn.execute(
        text("select to_regclass(:regclass)"), {"regclass": f"{schema}.operations"}
    ).scalar_one_or_none()
    pg_class_table_count = conn.execute(
        text(
            """
            select count(*)
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = :schema and c.relkind = 'r'
            """
        ),
        {"schema": schema},
    ).scalar_one()

print(f"[entrypoint] after-commit probe: alembic_version regclass = {alembic_reg}", flush=True)
print(f"[entrypoint] after-commit probe: operations regclass = {operations_reg}", flush=True)
print(f"[entrypoint] after-commit probe: pg_class table count in {schema} = {pg_class_table_count}", flush=True)
PY
}

log_db_fingerprint() {
    python - <<'PY'
import os
import sys

from app.diagnostics.db_state import log_fingerprint_from_url
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.getenv("DATABASE_URL")
label = os.getenv("DB_FINGERPRINT_LABEL", "")

if not url:
    print("[entrypoint] DATABASE_URL is not set for fingerprint collection", file=sys.stderr)
    sys.exit(1)


def _emit(message: str) -> None:
    print(f"[entrypoint] {message}", flush=True)


log_fingerprint_from_url(url=url, schema=schema, emitter=_emit, label=label)
PY
}

log_entrypoint_identity() {
    python - <<'PY'
import os
import sys

from app.diagnostics.db_state import log_identity_from_url
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.getenv("DATABASE_URL")
label = os.getenv("IDENTITY_LABEL") or "identity"

if not url:
    print(f"[entrypoint identity {label}] DATABASE_URL is not set", file=sys.stderr, flush=True)
    sys.exit(1)


def _emit(message: str) -> None:
    print(message, flush=True)


log_identity_from_url(
    url=url,
    schema=schema,
    emitter=_emit,
    label=f"entrypoint identity {label}",
)
PY
}

log_db_identity_probe() {
    IDENTITY_PROBE_LABEL="$1" python - <<'PY'
import os
import sys

from app.diagnostics.db_state import log_identity_probe_from_url
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.getenv("DATABASE_URL")
label = os.getenv("IDENTITY_PROBE_LABEL")

if not url:
    print("[entrypoint] DATABASE_URL is not set for identity probe", file=sys.stderr)
    sys.exit(1)

# Emit a single line matching DB_ID: ...
log_identity_probe_from_url(
    url=url,
    schema=schema,
    label=label,
    emitter=lambda msg: print(f"[entrypoint] {msg}", flush=True),
)
PY
}

require_upgrade_tables_present() {
    python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.diagnostics.db_state import identity_probe_line
from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.getenv("DATABASE_URL")
if not url:
    print("[entrypoint] DATABASE_URL is not set for post-upgrade table check", file=sys.stderr)
    sys.exit(1)

engine_kwargs = {"future": True, "pool_pre_ping": True}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "options": f"-csearch_path={schema},public",
        "prepare_threshold": 0,
    }

engine = create_engine(url, **engine_kwargs)
masked = make_url(url).render_as_string(hide_password=True)

with engine.connect() as conn:
    operations_reg = conn.execute(
        text("select to_regclass(:regclass)"), {"regclass": f"{schema}.operations"}
    ).scalar_one_or_none()
    alembic_reg = conn.execute(
        text("select to_regclass(:regclass)"), {"regclass": f"{schema}.alembic_version"}
    ).scalar_one_or_none()
    info_tables = set(
        conn.execute(
            text(
                """
                select table_name
                from information_schema.tables
                where table_schema=:schema and table_name in ('alembic_version','operations')
                """
            ),
            {"schema": schema},
        ).scalars()
    )
    regclass_tables = {
        name for name, reg in {"alembic_version": alembic_reg, "operations": operations_reg}.items() if reg
    }
    if info_tables != regclass_tables:
        current_schema, search_path = conn.execute(text("select current_schema, current_setting('search_path')")).one()
        schema_tables = list(
            conn.execute(
            text("select table_name from information_schema.tables where table_schema=:schema order by 1"),
            {"schema": schema},
        ).scalars()
        )
        probe = identity_probe_line(conn, schema=schema, label="post-upgrade")
        print(
            "[entrypoint] regclass and information_schema disagree about required tables",
            file=sys.stderr,
        )
        print(f"[entrypoint] regclass_tables={sorted(regclass_tables)} info_tables={sorted(info_tables)}", file=sys.stderr)
        print(f"[entrypoint] current_schema={current_schema} search_path={search_path}", file=sys.stderr)
        print(f"[entrypoint] tables_in_schema={schema_tables}", file=sys.stderr)
        print(f"[entrypoint] {probe}", file=sys.stderr)
        sys.exit(1)

    if operations_reg is None and alembic_reg is None:
        probe = identity_probe_line(conn, schema=schema, label="post-upgrade")
        print(
            "[entrypoint] CRITICAL: operations and alembic_version are both missing after upgrade",
            file=sys.stderr,
        )
        print(f"[entrypoint] DATABASE_URL={masked}", file=sys.stderr)
        print(f"[entrypoint] target_schema={schema}", file=sys.stderr)
        print(f"[entrypoint] {probe}", file=sys.stderr)
        sys.exit(1)

print(
    f"[entrypoint] post-upgrade regclass state: operations={operations_reg} alembic_version={alembic_reg}",
    flush=True,
)
PY
}

assert_alembic_state() {
    heads_output=$(alembic -c "$ALEMBIC_CONFIG" heads -v 2>&1)
    current_output=$(alembic -c "$ALEMBIC_CONFIG" current -v 2>&1)

    echo "[entrypoint] alembic heads:" >&2
    echo "$heads_output" >&2
    echo "[entrypoint] alembic current:" >&2
    echo "$current_output" >&2

    REQUIRED_REVISION="20270720_0029_cards_created_at"

    HEADS_OUTPUT="$heads_output" CURRENT_OUTPUT="$current_output" REQUIRED_REVISION="$REQUIRED_REVISION" \
        python - <<'PY'
import os
import re
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
alembic_config_path = os.getenv("ALEMBIC_CONFIG", "app/alembic.ini")
db_url = os.environ["DATABASE_URL"]

heads_output = os.environ["HEADS_OUTPUT"]
current_output = os.environ["CURRENT_OUTPUT"]
required_revision = os.environ["REQUIRED_REVISION"]


def _extract_revisions(output: str) -> list[str]:
    pattern = re.compile(r"(?P<rev>[0-9a-f]{10,}|\d{8}_\d+_[\\w]+)")
    revisions: list[str] = []
    for line in output.splitlines():
        for match in pattern.finditer(line):
            revisions.append(match.group("rev"))
    return revisions


def _version_table_schemas(conn) -> list[str]:
    return list(
        conn.execute(
            text(
                """
                select table_schema
                from information_schema.tables
                where table_name='alembic_version'
                order by table_schema
                """
            )
        ).scalars()
    )


def _collect_inventory(conn):
    user_schemas = conn.execute(
        text(
            """
            select nspname
            from pg_namespace
            where nspname not in ('pg_catalog','information_schema','pg_toast')
            order by 1
            """
        )
    ).scalars().all()
    user_tables = [
        f"{row.table_schema}.{row.table_name}"
        for row in conn.execute(
            text(
                """
                select table_schema, table_name
                from information_schema.tables
                where table_schema not in ('pg_catalog','information_schema','pg_toast')
                order by 1,2
                """
            )
        )
    ]
    return user_schemas, user_tables


def _regclass(conn, name: str) -> str | None:
    return conn.execute(text("select to_regclass(:regclass)"), {"regclass": f"{schema}.{name}"}).scalar_one_or_none()


heads = _extract_revisions(heads_output)
current = _extract_revisions(current_output)

script_dir = ScriptDirectory.from_config(Config(alembic_config_path))
script_heads = script_dir.get_heads()
script_heads_set = set(script_heads)

engine_kwargs = {"future": True, "pool_pre_ping": True}
if db_url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "prepare_threshold": 0,
        "options": f"-csearch_path={schema},public",
    }

engine = create_engine(db_url, **engine_kwargs)

try:
    with engine.connect() as conn:
        version_schemas = _version_table_schemas(conn)
        version_in_target = schema in version_schemas
        required_tables = ("operations", "accounts", "ledger_entries", "limit_configs")
        table_state = {name: _regclass(conn, name) for name in required_tables}
        cards_created = conn.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema=:schema
                  and table_name='cards'
                  and column_name='created_at'
                """
            ),
            {"schema": schema},
        ).scalar_one_or_none() is not None
        search_path = conn.exec_driver_sql("SHOW search_path").scalar_one_or_none()

        if not version_in_target:
            user_schemas, user_tables = _collect_inventory(conn)
            print(
                f"[entrypoint] alembic_version missing in target schema '{schema}' (search_path={search_path})",
                file=sys.stderr,
            )
            print(f"[entrypoint] alembic_version found in schemas: {version_schemas}", file=sys.stderr)
            print(f"[entrypoint] user schemas: {user_schemas}", file=sys.stderr)
            print(f"[entrypoint] user tables ({len(user_tables)}): {user_tables}", file=sys.stderr)
            sys.exit(1)

        version_rows = conn.execute(
            text(f'SELECT version_num FROM "{schema}".alembic_version')
        ).fetchall()
        version_values = [row[0] for row in version_rows]
except SQLAlchemyError as exc:
    print(f"[entrypoint] failed to inspect alembic state: {exc}", file=sys.stderr)
    sys.exit(1)


def _log_state(prefix: str = "current") -> None:
    print(
        f"[entrypoint] {prefix}: heads={heads} script_heads={script_heads} current={current} "
        f"versions_in_db={version_values}",
        file=sys.stderr,
    )
    missing = [name for name, reg in table_state.items() if reg is None]
    print(
        f"[entrypoint] {prefix}: required_tables_missing={missing} cards.created_at={cards_created}",
        file=sys.stderr,
    )


current_set = set(current)
heads_set = set(heads)
version_set = set(version_values)

issues: list[str] = []
if not current_output.strip() or not current:
    issues.append("alembic current returned empty output")
if not heads:
    issues.append("alembic heads returned no revisions")
if not version_values:
    issues.append("alembic_version exists but contains no rows")
if required_revision not in version_values:
    issues.append(
        f"alembic_version table missing required revision '{required_revision}' (found {version_values})"
    )
if current_set != heads_set:
    issues.append(f"alembic current {current} does not match heads {heads}")
if current_set != script_heads_set:
    issues.append(f"alembic current {current} does not match script heads {script_heads}")
if version_set != script_heads_set:
    issues.append(
        f"alembic_version contents {version_values} do not match script heads {script_heads}"
    )

if issues:
    _log_state(prefix="mismatch")
    print("[entrypoint] migration verification failed:", *issues, sep="\n- ", file=sys.stderr)
    sys.exit(1)

print(
    f"[entrypoint] alembic current = {sorted(current_set)} matches heads {sorted(script_heads_set)}",
    flush=True,
)
PY
}

assert_cards_created_at() {
    if python - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.environ.get("DATABASE_URL")

if not url:
    print("[entrypoint] DATABASE_URL is not set for cards.created_at verification", file=sys.stderr)
    sys.exit(1)

engine_kwargs = {"future": True, "pool_pre_ping": True}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "prepare_threshold": 0,
        "options": f"-csearch_path={schema},public",
    }

engine = create_engine(url, **engine_kwargs)

try:
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema=:schema
                  and table_name='cards'
                  and column_name='created_at'
                """
            ),
            {"schema": schema},
        ).scalar_one_or_none()
except SQLAlchemyError as exc:  # pragma: no cover - startup guard
    print(f"[entrypoint] failed to verify cards.created_at presence: {exc}", file=sys.stderr)
    sys.exit(1)

if exists:
    print(f"[entrypoint] verified cards.created_at exists in schema '{schema}'", flush=True)
    sys.exit(0)

print(f"[entrypoint] cards.created_at missing in schema '{schema}'", file=sys.stderr)
sys.exit(1)
PY
    then
        return 0
    fi

    echo "[entrypoint] alembic_version contents:" >&2
    python - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import resolve_db_schema, schema_resolution_line

schema, schema_source = resolve_db_schema()
print(f"[entrypoint] {schema_resolution_line(schema, schema_source)}", flush=True)
url = os.environ["DATABASE_URL"]

engine_kwargs = {"future": True, "pool_pre_ping": True}
if url.startswith("postgresql"):
    engine_kwargs["connect_args"] = {
        "prepare_threshold": 0,
        "options": f"-csearch_path={schema},public",
    }

engine = create_engine(url, **engine_kwargs)
try:
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT version_num FROM "{schema}".alembic_version')).fetchall()
        print(rows)
except SQLAlchemyError as exc:  # pragma: no cover - diagnostics helper
    print(f"[entrypoint] failed to read alembic_version contents: {exc}")
    sys.exit(0)
PY

    echo "[entrypoint] alembic history tail:" >&2
    alembic -c "$ALEMBIC_CONFIG" history --verbose | tail
    exit 1
}

# Run migrations before starting the API to guarantee schema availability
ALEMBIC_CONFIG=${ALEMBIC_CONFIG:-app/alembic.ini}
MIGRATIONS_RETRIES=${MIGRATIONS_RETRIES:-5}
MIGRATIONS_RETRY_DELAY=${MIGRATIONS_RETRY_DELAY:-2}

echo "[entrypoint] applying migrations via alembic ($ALEMBIC_CONFIG)"

python - <<'PY'
import sys
import traceback

from app.diagnostics.db_state import collect_inventory

try:
    inventory = collect_inventory()
except Exception as exc:  # noqa: BLE001 - startup diagnostics
    traceback.print_exc()
    print(f"[entrypoint] failed to collect pre-migration inventory: {exc}", flush=True)
    sys.exit(1)

print(
    "[entrypoint] pre-migration target: "
    f"db={inventory.current_database} user={inventory.current_user} "
    f"server={inventory.server_addr}:{inventory.server_port} search_path={inventory.search_path}",
    flush=True,
)
print(f"[entrypoint] pre-migration schemas: {inventory.schemas}", flush=True)
print(
    f"[entrypoint] pre-migration tables sample: {[f'{s}.{t}' for s, t in inventory.tables[:30]]}",
    flush=True,
)
PY

capture_db_id PRE

attempt=1
while [ "$attempt" -le "$MIGRATIONS_RETRIES" ]; do
    log_db_identity_probe "pre-upgrade-$attempt"
    IDENTITY_LABEL="pre-attempt-$attempt" log_entrypoint_identity
    DB_FINGERPRINT_LABEL="pre-migration-attempt-$attempt" log_db_fingerprint

    if alembic -x debug_sql=1 -c "$ALEMBIC_CONFIG" upgrade head; then
        capture_db_id POST
        assert_db_identity_stable
        log_db_identity_probe "post-upgrade-$attempt"
        require_upgrade_tables_present
        IDENTITY_LABEL="post-attempt-$attempt" log_entrypoint_identity
        assert_alembic_state
        after_commit_visibility_probe
        if verify_migration_ddls; then
            DB_FINGERPRINT_LABEL="post-migration-attempt-$attempt" log_db_fingerprint
            echo "[entrypoint] migrations applied"
            break
        fi

        echo "[entrypoint] migration attempt $attempt reported success but verification failed" >&2
        dump_migration_diagnostics
        exit 1
    fi

    if [ "$attempt" -eq "$MIGRATIONS_RETRIES" ]; then
        echo "[entrypoint] migrations failed after $attempt attempts; exiting" >&2
        exit 1
    fi

    echo "[entrypoint] migration attempt $attempt failed, retrying in $MIGRATIONS_RETRY_DELAY s"
    attempt=$((attempt + 1))
    sleep "$MIGRATIONS_RETRY_DELAY"
done

assert_cards_created_at

set +e
python app/scripts/migration_diagnostics.py
diagnostics_status=$?
set -e

if [ "$diagnostics_status" -ne 0 ]; then
    echo "[entrypoint] diagnostics failed with status $diagnostics_status" >&2
    dump_migration_diagnostics
fi

python - <<'PY'
from app.db import reset_engine

reset_engine()
print("[entrypoint] ORM engine cache reset after migrations", flush=True)
PY

if [ "${ENTRYPOINT_SKIP_APP}" = "1" ]; then
    echo "[entrypoint] ENTRYPOINT_SKIP_APP=1 is set; exiting after migrations"
    exit 0
fi

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
