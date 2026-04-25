from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))


os.environ["CRM_DATABASE_URL"] = "sqlite:///./crm_test.db"
os.environ["CRM_AUTH_DISABLED_FOR_TESTS"] = "1"

import pytest

_SERVICE_DEPS_AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("fastapi", "sqlalchemy"))


def pytest_ignore_collect(collection_path, config):  # noqa: ANN001
    if collection_path.name == "conftest.py":
        return False
    return not _SERVICE_DEPS_AVAILABLE


if _SERVICE_DEPS_AVAILABLE:
    from fastapi.testclient import TestClient

    from app.db import Base, engine  # noqa: E402
    from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    if not _SERVICE_DEPS_AVAILABLE:
        pytest.skip("crm-service tests require service deps; run inside the service container or install requirements")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    if not _SERVICE_DEPS_AVAILABLE:
        pytest.skip("crm-service tests require service deps; run inside the service container or install requirements")
    return TestClient(app)


@pytest.fixture()
def tenant_headers() -> dict[str, str]:
    return {"X-Tenant-Id": "tenant-test"}
