import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DB_SCHEMA, get_db
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import OperationStatus
from app.models.terminal import Terminal
from app.tests.utils import ensure_connectable, get_database_url

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_POSTGRES_TESTS", "false").lower() in {"1", "true", "yes"},
    reason="Postgres integration tests explicitly skipped",
)


REQUIRED_TABLES = [
    "users",
    "clients",
    "cards",
    "client_user_roles",
    "card_limits",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
]


def _make_alembic_config(db_url: str) -> Config:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.integration
def test_required_core_tables_present_after_upgrade() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)
    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for this test")

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        connection.execute(sa.text("SET search_path TO :schema"), {"schema": DB_SCHEMA})
        effective_search_path = connection.execute(sa.text("SHOW search_path")).scalar_one()
        version_table = connection.execute(
            sa.text("select to_regclass(:reg)"), {"reg": f"{DB_SCHEMA}.alembic_version_core"}
        ).scalar()
        db_name, current_schema, search_path = connection.execute(
            sa.text("select current_database(), current_schema(), current_setting('search_path')")
        ).one()
        versions = (
            [
                row[0]
                for row in connection.execute(
                    sa.text(f'SELECT version_num FROM "{DB_SCHEMA}".alembic_version_core')
                )
            ]
            if version_table
            else []
        )
        tables = connection.execute(
            sa.text(
                "select table_schema, table_name from information_schema.tables where table_schema=:schema order by table_name limit 30"
            ),
            {"schema": DB_SCHEMA},
        ).all()

    existing = {row.table_name for row in tables}
    missing = sorted(set(REQUIRED_TABLES) - existing)
    diagnostic = (
        f"db={db_name} schema={current_schema} search_path={search_path} (effective={effective_search_path}) versions={versions} "
        f"tables={[f'{row.table_schema}.{row.table_name}' for row in tables]}"
    )

    assert not missing, f"Missing required tables {missing}. Diagnostics: {diagnostic}"


@pytest.mark.integration
def test_core_endpoints_postgres_smoke() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)
    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for this test")

    engine_kwargs: dict[str, object] = {}
    if db_url.startswith("postgresql") and DB_SCHEMA:
        engine_kwargs["connect_args"] = {
            "options": f"-c search_path={DB_SCHEMA}",
            "prepare_threshold": 0,
        }
        engine = sa.create_engine(db_url, **engine_kwargs)

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    with engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE operations CASCADE"))
        connection.execute(sa.text("TRUNCATE TABLE terminals CASCADE"))
        connection.execute(sa.text("TRUNCATE TABLE merchants CASCADE"))
        connection.execute(sa.text("TRUNCATE TABLE cards CASCADE"))
        connection.execute(sa.text("TRUNCATE TABLE clients CASCADE"))

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db

    try:
        client_pk = uuid4()
        with TestingSessionLocal() as session:
            session.add(Client(id=client_pk, name="Smoke Client", status="ACTIVE"))
            session.add(Card(id="smoke-card", client_id=str(client_pk), status="ACTIVE"))
            session.add(Merchant(id="smoke-merchant", name="Smoke", status="ACTIVE"))
            session.add(Terminal(id="smoke-terminal", merchant_id="smoke-merchant", status="ACTIVE"))
            session.commit()

        client = TestClient(app)

        list_response = client.get("/api/v1/operations?limit=1&offset=0")
        assert list_response.status_code == 200
        payload = list_response.json()
        assert "items" in payload and "total" in payload

        authorize_payload = {
            "client_id": str(client_pk),
            "card_id": "smoke-card",
            "terminal_id": "smoke-terminal",
            "merchant_id": "smoke-merchant",
            "amount": 500,
            "currency": "RUB",
            "ext_operation_id": "smoke-op-1",
        }

        auth_response = client.post("/api/v1/transactions/authorize", json=authorize_payload)
        assert auth_response.status_code == 200
        data = auth_response.json()
        assert data["operation_id"] == "smoke-op-1"

        with engine.connect() as connection:
            op_status, response_message = connection.execute(
                sa.text(
                    "select status, response_message from operations where operation_id=:op_id"
                ),
                {"op_id": "smoke-op-1"},
            ).one()

        assert op_status == OperationStatus.AUTHORIZED.value
        assert response_message == "APPROVED"
    finally:
        app.dependency_overrides.pop(get_db, None)
