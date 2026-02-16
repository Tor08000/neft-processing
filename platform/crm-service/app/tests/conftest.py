from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))


os.environ["CRM_DATABASE_URL"] = "sqlite:///./crm_test.db"
os.environ["CRM_AUTH_DISABLED_FOR_TESTS"] = "1"

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def tenant_headers() -> dict[str, str]:
    return {"X-Tenant-Id": "tenant-test"}
