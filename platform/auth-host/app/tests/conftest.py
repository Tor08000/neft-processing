from __future__ import annotations

import asyncio
import os
import socket
import sys
from pathlib import Path

import pytest
import psycopg


def _prioritize_service(service_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    sys.path.insert(0, str(service_root))


def _prepend_path(path: Path) -> None:
    if not path.exists():
        return

    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _find_repo_root(start: Path) -> Path:
    env_root = os.environ.get("REPO_ROOT") or os.environ.get("APP_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.exists():
            return candidate

    current = start
    fallback: Path | None = None

    for _ in range(15):
        if (current / ".git").exists() or (current / "docker-compose.yml").exists():
            return current

        if (current / "platform").exists() and (current / "shared").exists():
            fallback = current
        elif (current / "pyproject.toml").exists():
            fallback = fallback or current

        if current.parent == current:
            break
        current = current.parent

    return fallback or start


root = _find_repo_root(Path(__file__).resolve().parent)
shared_path = root / "shared" / "python"
service_root = root / "platform" / "auth-host"

_prepend_path(shared_path)

if service_root.exists():
    _prioritize_service(service_root)

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _configure_local_docker_postgres_for_host_tests() -> None:
    if os.getenv("POSTGRES_HOST"):
        return

    if _port_open("localhost", 5432):
        os.environ["POSTGRES_HOST"] = "localhost"


_configure_local_docker_postgres_for_host_tests()


def _can_reach_auth_db() -> bool:
    try:
        from app import db

        dsn = db.DSN_ASYNC
        if dsn.startswith("postgresql://"):
            dsn = dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        elif dsn.startswith("postgres://"):
            dsn = dsn.replace("postgres://", "postgresql+psycopg://", 1)
        with psycopg.connect(dsn):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _restore_auth_runtime_truth_after_suite():
    yield

    if not _can_reach_auth_db():
        return

    from app import bootstrap, db
    from app.settings import Settings
    from app.tests.migration_helpers import run_auth_migrations

    run_auth_migrations(db.DSN_ASYNC)
    asyncio.run(bootstrap.bootstrap_required_users(Settings()))
