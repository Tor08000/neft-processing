import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine.url import make_url

from alembic import command
from alembic.config import Config
import sqlalchemy as sa
from functools import lru_cache
from psycopg import errors as psycopg_errors
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

import pytest
from jose import jwt
from .fixtures.rsa_keys import rsa_keys  # noqa: F401

ROOT_DIR = Path(__file__).resolve()
while ROOT_DIR.name != "app" and ROOT_DIR.parent != ROOT_DIR:
    ROOT_DIR = ROOT_DIR.parent


def _find_repo_root(start_dir: Path) -> Path:
    for current in (start_dir, *start_dir.parents):
        docker_compose = current / "docker-compose.yml"
        if docker_compose.exists():
            return current
        has_git = (current / ".git").exists()
        has_platform_shared = (current / "platform").is_dir() and (current / "shared").is_dir()
        if has_git or has_platform_shared:
            return current
    return start_dir.parent


REPO_ROOT = _find_repo_root(ROOT_DIR)
SHARED_PATH = REPO_ROOT / "shared" / "python"
SERVICE_ROOT = REPO_ROOT / "services" / "core-api"
PROCESSING_APP_ROOT = ROOT_DIR.parent


def _prepend_path(path: Path) -> None:
    if not path.exists():
        return
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


for path in (SHARED_PATH, PROCESSING_APP_ROOT, SERVICE_ROOT):
    _prepend_path(path)

if os.getenv("DATABASE_URL_TEST"):
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://neft:neft@postgres:5432/neft")
os.environ.setdefault("NEFT_DB_SCHEMA", "processing_core")
os.environ.setdefault("NEFT_AUTH_ISSUER", "neft-auth")
os.environ.setdefault("NEFT_AUTH_AUDIENCE", "neft-admin")
os.environ.setdefault("RISK_V5_SHADOW_ENABLED", "false")

from app import models  # noqa: F401
from app.db import Base
from app.db.schema import DB_SCHEMA
from app.db.types import ExistingEnum
from app.integrations.fuel import models as fuel_models  # noqa: F401
from app.alembic.helpers import ensure_pg_enum

FASTAPI_SKIP_REASON = (
    "fastapi not installed; run in docker: docker compose exec -T core-api pytest -q -x"
)


def _has_fastapi() -> bool:
    try:
        import fastapi  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


HAS_FASTAPI = _has_fastapi()
TESTS_ROOT = PROCESSING_APP_ROOT / "app" / "tests"

EXPECTED_ISSUER = os.getenv("NEFT_AUTH_ISSUER", "neft-auth")
EXPECTED_AUDIENCE = os.getenv("NEFT_AUTH_AUDIENCE", "neft-admin")


def _log_database_url() -> None:
    raw_url = os.getenv("DATABASE_URL") or ""
    try:
        parsed = make_url(raw_url)
        safe_url = parsed._replace(password="***").render_as_string(hide_password=False)
    except Exception:
        safe_url = raw_url
    print(f"pytest database url: {safe_url}")


_log_database_url()


def pytest_report_header(config: pytest.Config) -> str | None:
    if not HAS_FASTAPI:
        return f"{FASTAPI_SKIP_REASON}; skipping contracts/smoke/integration collections"
    return None


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:  # type: ignore[override]
    if HAS_FASTAPI:
        return False
    path_str = str(collection_path).lower()
    if "/tests/contracts/" in path_str or "\\tests\\contracts\\" in path_str:
        return True
    if "/tests/smoke/" in path_str or "\\tests\\smoke\\" in path_str:
        return True
    if "/tests/integration/" in path_str or "\\tests\\integration\\" in path_str:
        return True
    return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # type: ignore[override]
    known_marks = {
        "unit",
        "integration",
        "smoke",
        "contracts",
        "contracts_api",
        "contracts_events",
    }
    for item in items:
        try:
            item_path = Path(str(getattr(item, "fspath", getattr(item, "path", "")))).resolve()
        except OSError:
            item_path = Path(str(getattr(item, "fspath", getattr(item, "path", ""))))
        if TESTS_ROOT not in item_path.parents and item_path != TESTS_ROOT:
            continue
        if not any(item.get_closest_marker(mark) for mark in known_marks):
            item.add_marker("unit")


def _uses_postgres(database_url: str) -> bool:
    try:
        return make_url(database_url).drivername.startswith("postgresql")
    except Exception:
        return False


def _markexpr_includes(markexpr: str, marker: str) -> bool:
    return re.search(rf"(?<![\w:]){re.escape(marker)}(?![\w:])", markexpr) is not None


def _has_integration_path(config: pytest.Config) -> bool:
    for arg in config.args:
        arg_path = Path(arg)
        try:
            parts = {part.lower() for part in arg_path.parts}
        except Exception:
            parts = set()
        if {"integration", "smoke"} & parts:
            return True
        arg_lower = str(arg).lower()
        if "/integration/" in arg_lower or "\\integration\\" in arg_lower:
            return True
        if "/smoke/" in arg_lower or "\\smoke\\" in arg_lower:
            return True
    return False


def _should_skip_db_bootstrap(config: pytest.Config) -> bool:
    markexpr = (config.getoption("-m") or "").strip().lower()
    if markexpr:
        if any(
            _markexpr_includes(markexpr, marker)
            for marker in ("contracts", "contracts_events", "contracts_api")
        ):
            return True
        if _markexpr_includes(markexpr, "unit") and not any(
            _markexpr_includes(markexpr, marker) for marker in ("integration", "smoke")
        ):
            return False
        if any(_markexpr_includes(markexpr, marker) for marker in ("integration", "smoke")):
            return False
    if _has_integration_path(config):
        return False
    return False


def _run_alembic_upgrade(database_url: str, schema: str) -> None:
    alembic_ini = PROCESSING_APP_ROOT / "app" / "alembic.ini"
    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic config not found at {alembic_ini}")
    cfg = Config(str(alembic_ini))
    script_location = cfg.get_main_option("script_location")
    if not script_location:
        raise RuntimeError(
            "Alembic config is missing 'script_location'; "
            f"check {alembic_ini} and ensure it points at app/alembic"
        )
    url = make_url(database_url)
    query = dict(url.query)
    search_option = f"-c search_path={schema}"
    options = query.get("options", "").strip()
    if search_option not in options:
        options = f"{options} {search_option}".strip()
    query["options"] = options
    url_str = url.set(query=query).render_as_string(hide_password=False)
    cfg.set_main_option("sqlalchemy.url", _escape_alembic_cfg_percent(url_str))
    command.upgrade(cfg, "head")


def _escape_alembic_cfg_percent(url: str) -> str:
    return url.replace("%", "%%")


def _reset_schema(database_url: str, schema: str) -> None:
    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    finally:
        engine.dispose()


REQUIRED_TABLES = {
    "audit_log",
    "billing_invoices",
    "billing_job_runs",
    "billing_periods",
    "credit_notes",
    "internal_ledger_accounts",
    "internal_ledger_entries",
    "internal_ledger_transactions",
    "invoice_payments",
    "invoice_settlement_allocations",
    "invoice_transition_logs",
    "invoices",
    "operations",
}

def _register_enum(
    enum_types: dict[str, tuple[str, tuple[str, ...]]],
    *,
    name: str | None,
    schema: str,
    values: tuple[str, ...],
) -> None:
    if not name:
        return
    if not values:
        raise RuntimeError(f"Enum {name} has no values")
    existing = enum_types.get(name)
    if existing:
        existing_schema, existing_values = existing
        if existing_schema != schema or existing_values != values:
            raise RuntimeError(
                "Enum value mismatch for "
                f"{name}: {(existing_schema, existing_values)!r} vs {(schema, values)!r}"
            )
        return
    enum_types[name] = (schema, values)


@lru_cache(maxsize=1)
def _iter_enum_types() -> dict[str, tuple[str, tuple[str, ...]]]:
    enum_types: dict[str, tuple[str, tuple[str, ...]]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            while isinstance(column_type, sa.ARRAY):
                column_type = column_type.item_type
            if isinstance(column_type, ExistingEnum):
                schema = column_type.schema or DB_SCHEMA
                _register_enum(
                    enum_types,
                    name=column_type.name,
                    schema=schema,
                    values=tuple(column_type._values),
                )
                continue
            if isinstance(column_type, PGEnum):
                schema = column_type.schema or DB_SCHEMA
                _register_enum(
                    enum_types,
                    name=column_type.name,
                    schema=schema,
                    values=tuple(column_type.enums),
                )
                continue
            if isinstance(column_type, sa.Enum):
                schema = column_type.schema or DB_SCHEMA
                _register_enum(
                    enum_types,
                    name=column_type.name,
                    schema=schema,
                    values=tuple(column_type.enums),
                )
                continue
    return enum_types


_RESOLVED_ENUM_VALUES: dict[str, tuple[str, ...] | None] = {}


def _resolve_enum_values(enum_name: str) -> tuple[str, ...] | None:
    if enum_name in _RESOLVED_ENUM_VALUES:
        return _RESOLVED_ENUM_VALUES[enum_name]
    enum_registry = _iter_enum_types()
    if enum_name in enum_registry:
        _, values = enum_registry[enum_name]
        _RESOLVED_ENUM_VALUES[enum_name] = values
        return values
    try:
        from app.models.fuel import FleetNotificationChannelStatus, FleetNotificationChannelType
    except ModuleNotFoundError:
        FleetNotificationChannelStatus = None  # type: ignore[assignment]
        FleetNotificationChannelType = None  # type: ignore[assignment]
    known_enums = {
        "fleet_notification_channel_status": tuple(
            member.value for member in FleetNotificationChannelStatus
        )
        if FleetNotificationChannelStatus
        else None,
        "fleet_notification_channel_type": tuple(
            member.value for member in FleetNotificationChannelType
        )
        if FleetNotificationChannelType
        else None,
    }
    resolved = known_enums.get(enum_name)
    _RESOLVED_ENUM_VALUES[enum_name] = resolved
    return resolved


def _collect_processing_enums(schema: str) -> dict[str, tuple[str, ...]]:
    enums = {}
    for enum_name, (enum_schema, values) in _iter_enum_types().items():
        if enum_schema == schema:
            enums[enum_name] = values
    return enums


# Warm enum registry after all model imports are loaded.
_iter_enum_types.cache_clear()
_iter_enum_types()
_RESOLVED_ENUM_VALUES.clear()

REQUIRED_ENUMS = set(_collect_processing_enums(DB_SCHEMA))


def _schema_diagnostics(conn, *, schema: str, missing_tables: set[str]) -> str:
    current = conn.execute(
        text("select current_schema(), current_setting('search_path')")
    ).all()
    tables = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
            ORDER BY table_name
            LIMIT 30
            """
        ),
        {"schema": schema},
    ).scalars()
    tables_list = list(tables)
    try:
        revision = conn.execute(
            text(f'SELECT version_num FROM "{schema}".alembic_version_core')
        ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        revision = f"error: {exc!r}"

    enums_status = {}
    if conn.dialect.name == "postgresql":
        rows = conn.execute(
            text(
                """
                SELECT t.typname
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = :schema AND t.typname = ANY(:names)
                """
            ),
            {"schema": schema, "names": sorted(REQUIRED_ENUMS)},
        ).scalars()
        existing_enums = set(rows)
        enums_status = {
            "missing": sorted(REQUIRED_ENUMS - existing_enums),
            "present": sorted(existing_enums),
        }

    return (
        f"schema={schema}, missing_tables={sorted(missing_tables)}; "
        f"current_schema/search_path={current}; "
        f"tables(sample)={tables_list}; "
        f"alembic_revision={revision}; "
        f"enums={enums_status or 'n/a'}"
    )


def _ensure_required_enums(database_url: str, schema: str) -> None:
    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        enum_map = _collect_processing_enums(schema)
        if not enum_map:
            return
        with engine.connect() as conn:
            for enum_name, values in sorted(enum_map.items()):
                ensure_pg_enum(conn, enum_name, values=values, schema=schema)
    finally:
        engine.dispose()


def _ensure_required_tables(database_url: str, schema: str) -> None:
    max_attempts = 5
    missing_enum_regex = re.compile(r'type "([^"]+)\.([^"]+)" does not exist')
    missing_enum_unqualified_regex = re.compile(r'type "([^"]+)" does not exist')
    created_enums: list[str] = []
    last_exception: Exception | None = None

    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        def _check_required_tables(conn) -> None:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names(schema=schema))
            rows = conn.execute(
                text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_name = ANY(:table_names)
                    """
                ),
                {"table_names": sorted(REQUIRED_TABLES)},
            ).all()
            schemas_by_table: dict[str, set[str]] = {}
            for table_schema, table_name in rows:
                schemas_by_table.setdefault(table_name, set()).add(table_schema)

            missing = REQUIRED_TABLES - tables
            if missing:
                other_schema_hits = {
                    table: sorted(schemas - {schema})
                    for table, schemas in schemas_by_table.items()
                    if schemas - {schema}
                }
                diagnostics = _schema_diagnostics(conn, schema=schema, missing_tables=missing)
                raise RuntimeError(
                    "Missing required tables after migrations: "
                    f"{', '.join(sorted(missing))}. "
                    "Found in other schemas: "
                    f"{', '.join(f'{table} -> {schemas}' for table, schemas in sorted(other_schema_hits.items())) or '[]'}. "
                    f"Diagnostics: {diagnostics}"
                )

        for attempt in range(max_attempts):
            try:
                with engine.begin() as conn:
                    Base.metadata.create_all(bind=conn)
                    _check_required_tables(conn)
                return
            except ProgrammingError as exc:
                last_exception = exc
                message = str(exc.orig)
                match = missing_enum_regex.search(message)
                if match:
                    error_schema, enum_name = match.groups()
                else:
                    match = missing_enum_unqualified_regex.search(message)
                    if match:
                        error_schema = schema
                        enum_name = match.group(1)
                    elif not isinstance(exc.orig, psycopg_errors.UndefinedObject):
                        raise
                    else:
                        raise
                if error_schema != schema:
                    raise RuntimeError(
                        f"Enum {error_schema}.{enum_name} is missing outside expected schema {schema}"
                    ) from exc
                values = _resolve_enum_values(enum_name)
                if not values:
                    raise RuntimeError(
                        f"Unknown enum values for {enum_name}"
                    ) from exc
                values_sql = ", ".join("'{}'".format(value.replace("'", "''")) for value in values)
                schema_sql = schema.replace('"', '""')
                enum_sql = enum_name.replace('"', '""')
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1
                                FROM pg_type t
                                JOIN pg_namespace n ON n.oid = t.typnamespace
                                WHERE n.nspname = '{schema_sql}' AND t.typname = '{enum_sql}'
                            ) THEN
                                CREATE TYPE "{schema_sql}"."{enum_sql}" AS ENUM ({values_sql});
                            END IF;
                        END $$;
                        """
                    )
                if enum_name not in created_enums:
                    created_enums.append(enum_name)
        last_message = f"{last_exception!r}" if last_exception else "unknown error"
        raise RuntimeError(
            "Exceeded enum bootstrap attempts while ensuring required tables. "
            f"Created enums={created_enums}. Last error={last_message}"
        )
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def ensure_db_ready(request: pytest.FixtureRequest) -> None:
    if _should_skip_db_bootstrap(request.config):
        return

    database_url = os.getenv("DATABASE_URL", "")
    if not _uses_postgres(database_url):
        pytest.fail("postgres not available; start docker compose postgres")

    schema = (os.getenv("NEFT_DB_SCHEMA") or "processing_core").strip() or "processing_core"
    try:
        _reset_schema(database_url, schema)
        _run_alembic_upgrade(database_url, schema)
        _ensure_required_enums(database_url, schema)
        _ensure_required_tables(database_url, schema)
    except OperationalError:
        pytest.fail("postgres not available; start docker compose postgres")
    except Exception as exc:
        pytest.fail(f"DB bootstrap failed: {exc!r}")


@pytest.fixture(autouse=True)
def _mock_admin_public_key(monkeypatch: pytest.MonkeyPatch, rsa_keys: dict):
    if not HAS_FASTAPI:
        return
    try:
        from app.services import admin_auth, client_auth
    except ModuleNotFoundError:
        return

    monkeypatch.setenv("ADMIN_PUBLIC_KEY", rsa_keys["public"])
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", rsa_keys["public"])
    for module in (admin_auth, client_auth):
        monkeypatch.setattr(module, "_cached_public_key", None, raising=False)
        monkeypatch.setattr(module, "_public_key_cached_at", 0.0, raising=False)

    from app import services
    from app.api.dependencies.admin import require_admin_user
    from app.main import app

    app.dependency_overrides[require_admin_user] = services.admin_auth.require_admin


@pytest.fixture
def make_jwt(rsa_keys: dict):
    def _make_jwt(
        roles=("ADMIN",),
        minutes_valid: int = 60,
        sub: str = "user-1",
        client_id: str | None = None,
        extra: dict | None = None,
    ):
        payload = {
            "sub": sub,
            "roles": list(roles),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes_valid),
            "aud": EXPECTED_AUDIENCE,
            "iss": EXPECTED_ISSUER,
        }
        if client_id:
            payload["client_id"] = client_id
        if roles and len(roles) == 1:
            payload["role"] = roles[0]
        if extra:
            payload.update(extra)
        return jwt.encode(payload, rsa_keys["private"], algorithm="RS256")

    return _make_jwt


@pytest.fixture
def admin_token(make_jwt):
    return make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))


@pytest.fixture
def user_token(make_jwt):
    return make_jwt(roles=("USER",))


@pytest.fixture
def admin_auth_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}", "X-CRM-Version": "1"}


@pytest.fixture
def client_token(make_jwt):
    return make_jwt(roles=("CLIENT_USER",), client_id="client-1")


@pytest.fixture
def client_auth_headers(client_token: str):
    return {"Authorization": f"Bearer {client_token}"}
