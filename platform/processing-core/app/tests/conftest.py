import os
import re
import sys
from pathlib import Path
from sqlalchemy.engine.url import make_url
from datetime import datetime, timedelta, timezone

from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

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

try:
    from app.api.dependencies.admin import require_admin_user
    from app.main import app as fastapi_app
    from app.services import admin_auth as _admin_auth

    fastapi_app.dependency_overrides[require_admin_user] = _admin_auth.require_admin
except Exception:
    pass

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
            return True
        if any(_markexpr_includes(markexpr, marker) for marker in ("integration", "smoke")):
            return False
    if _has_integration_path(config):
        return False
    return False


def _run_alembic_upgrade(database_url: str) -> None:
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
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


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


def _ensure_required_tables(database_url: str, schema: str) -> None:
    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names(schema=schema))
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_name = ANY(:table_names)
                    """
                ),
                {"table_names": list({"operations", "cards"})},
            ).all()
        schemas_by_table: dict[str, set[str]] = {}
        for table_schema, table_name in rows:
            schemas_by_table.setdefault(table_name, set()).add(table_schema)
    finally:
        engine.dispose()

    required_tables = {"operations", "cards"}
    missing = required_tables - tables
    if missing:
        diagnostics = ", ".join(
            f"{table} in {sorted(schemas_by_table.get(table, set())) or '[]'}"
            for table in sorted(required_tables)
        )
        raise RuntimeError(
            "Missing required tables after migrations: "
            f"{', '.join(sorted(missing))}. Found schemas: {diagnostics}"
        )


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
        _run_alembic_upgrade(database_url)
        _ensure_required_tables(database_url, schema)
    except OperationalError:
        pytest.fail("postgres not available; start docker compose postgres")
    except Exception as exc:
        pytest.fail(f"DB bootstrap failed: {exc!r}")


@pytest.fixture(autouse=True)
def _mock_admin_public_key(monkeypatch: pytest.MonkeyPatch, rsa_keys: dict):
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
