import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.schema import MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

import pytest
from jose import jwt
from ._db_test_harness import get_test_dsn_or_fail
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

def _running_in_container() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("IN_DOCKER") == "1"
os.environ.setdefault("NEFT_DB_SCHEMA", "processing_core")
os.environ.setdefault("NEFT_AUTH_ISSUER", "neft-auth")
os.environ.setdefault("NEFT_AUTH_AUDIENCE", "neft-admin")
os.environ.setdefault("RISK_V5_SHADOW_ENABLED", "false")
# Keep pytest collection import-safe in clean environments.
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.db.schema import DB_SCHEMA
from app.integrations.fuel import models as fuel_models  # noqa: F401

_SQLALCHEMY_DROP_ALL = MetaData.drop_all


def _resolve_sqlalchemy_bind(bind):
    if callable(bind):
        try:
            return bind()
        except TypeError:
            return bind
    return bind


def _quote_table_name(bind, table_name: str, *, schema: str | None) -> str:
    preparer = bind.dialect.identifier_preparer
    quoted_table = preparer.quote(table_name)
    if not schema:
        return quoted_table
    return f"{preparer.quote_schema(schema)}.{quoted_table}"


def _pytest_postgres_truncate_drop_all(self, bind=None, tables=None, **kwargs):
    resolved_bind = _resolve_sqlalchemy_bind(bind)
    table_list = list(tables or [])
    if (
        resolved_bind is not None
        and table_list
        and getattr(getattr(resolved_bind, "dialect", None), "name", None) == "postgresql"
        and os.getenv("NEFT_PYTEST_SAFE_DROP_ALL", "1").lower() not in {"0", "false", "no"}
    ):
        schema = (os.getenv("NEFT_DB_SCHEMA") or DB_SCHEMA or "").strip() or None
        inspector = inspect(resolved_bind)
        existing_tables = set(inspector.get_table_names(schema=schema))
        qualified_names = [
            _quote_table_name(resolved_bind, table.name, schema=schema)
            for table in table_list
            if table.name in existing_tables
        ]
        if qualified_names:
            statement = "TRUNCATE TABLE " + ", ".join(qualified_names) + " RESTART IDENTITY CASCADE"
            if hasattr(resolved_bind, "begin"):
                with resolved_bind.begin() as connection:
                    connection.execute(text(statement))
            else:
                resolved_bind.execute(text(statement))
        return None
    return _SQLALCHEMY_DROP_ALL(self, bind=bind, tables=tables, **kwargs)


MetaData.drop_all = _pytest_postgres_truncate_drop_all

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


def _ensure_psycopg_driver(database_url: str) -> str:
    try:
        parsed = make_url(database_url)
    except Exception:
        return database_url
    drivername = parsed.drivername
    if drivername in {"postgres", "postgresql"} or drivername.endswith("+psycopg2"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def _log_database_url() -> None:
    raw_url = os.getenv("TEST_DATABASE_DSN") or os.getenv("DATABASE_URL_TEST") or os.getenv("DATABASE_URL") or ""
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


def _build_engine(database_url: str) -> Engine:
    if _uses_postgres(database_url):
        return create_engine(
            database_url,
            future=True,
            connect_args={
                "options": f"-c search_path={os.getenv('NEFT_DB_SCHEMA', 'processing_core')}",
                "prepare_threshold": 0,
            },
        )
    return create_engine(database_url, future=True)


@pytest.fixture(scope="session")
def test_db_engine() -> Engine:
    database_url = _ensure_psycopg_driver(get_test_dsn_or_fail())
    os.environ["DATABASE_URL"] = database_url
    engine = _build_engine(database_url)
    parsed = make_url(database_url)
    if engine.url.render_as_string(hide_password=False) != parsed.render_as_string(hide_password=False):
        raise RuntimeError("test_db_engine_dsn_mismatch")
    return engine


@pytest.fixture(scope="session")
def test_db_sessionmaker(test_db_engine: Engine):
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=test_db_engine,
    )


@pytest.fixture()
def test_db_session(test_db_sessionmaker):
    session = test_db_sessionmaker()
    try:
        yield session
    finally:
        session.close()


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
    if os.getenv("NEFT_SKIP_DB_BOOTSTRAP") == "1":
        return True
    for arg in config.args:
        if str(arg).endswith("test_portal_access_state.py"):
            return True
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
    previous_schema = os.environ.get("NEFT_DB_SCHEMA")
    os.environ["NEFT_DB_SCHEMA"] = schema
    url = make_url(database_url)
    query = dict(url.query)
    search_option = f"-c search_path={schema}"
    options = query.get("options", "").strip()
    if search_option not in options:
        options = f"{options} {search_option}".strip()
    query["options"] = options
    url_str = url.set(query=query).render_as_string(hide_password=False)
    cfg.set_main_option("sqlalchemy.url", _escape_alembic_cfg_percent(url_str))
    try:
        command.upgrade(cfg, "head")
    finally:
        if previous_schema is None:
            os.environ.pop("NEFT_DB_SCHEMA", None)
        else:
            os.environ["NEFT_DB_SCHEMA"] = previous_schema


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
    "alembic_version_core",
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

    return (
        f"schema={schema}, missing_tables={sorted(missing_tables)}; "
        f"current_schema/search_path={current}; "
        f"tables(sample)={tables_list}; "
        f"alembic_revision={revision}"
    )


def _check_required_tables(database_url: str, schema: str) -> None:
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
    finally:
        engine.dispose()


def _ensure_db_ready_for_request(request: pytest.FixtureRequest) -> None:
    if _should_skip_db_bootstrap(request.config):
        return

    try:
        database_url = _ensure_psycopg_driver(get_test_dsn_or_fail())
    except RuntimeError as exc:
        pytest.fail(str(exc))
    os.environ["DATABASE_URL"] = database_url
    if not _running_in_container() and "@postgres:" in database_url:
        pytest.fail("processing-core tests require docker compose stack. Run scripts\\test_core_stack.cmd")
    if not _uses_postgres(database_url):
        return

    schema = (os.getenv("NEFT_DB_SCHEMA") or "processing_core").strip() or "processing_core"
    try:
        _reset_schema(database_url, schema)
        _run_alembic_upgrade(database_url, schema)
        _check_required_tables(database_url, schema)
    except OperationalError:
        pytest.fail("postgres not available; start docker compose postgres")
    except Exception as exc:
        pytest.fail(f"DB bootstrap failed: {exc!r}")


@pytest.fixture(scope="session", autouse=True)
def ensure_db_ready(request: pytest.FixtureRequest) -> None:
    _ensure_db_ready_for_request(request)


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
