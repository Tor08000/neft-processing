import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.terminal import Terminal


@pytest.fixture(scope="module")
def _apply_migrations():
    if engine.dialect.name != "postgresql":  # pragma: no cover - sqlite fallback
        pytest.skip("Test requires Postgres")

    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))
    command.upgrade(cfg, "head")
    yield


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Test requires Postgres")
@pytest.mark.usefixtures("_apply_migrations")
def test_limit_config_scope_and_window_enums():
    with engine.connect() as connection:
        enum_rows = connection.exec_driver_sql(
            """
            SELECT t.typname, e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname IN ('limitconfigscope', 'limitwindow')
            ORDER BY t.typname, enumsortorder
            """
        ).fetchall()

        enum_map: dict[str, list[str]] = {}
        for typname, label in enum_rows:
            enum_map.setdefault(typname, []).append(label)

        scope_type = connection.exec_driver_sql(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'limit_configs'
              AND column_name = 'scope'
            """
        ).scalar()

        window_type = connection.exec_driver_sql(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'limit_configs'
              AND column_name = 'window'
            """
        ).scalar()

    assert set(enum_map.get("limitconfigscope", [])) == {"GLOBAL", "CLIENT", "CARD", "TARIFF"}
    assert set(enum_map.get("limitwindow", [])) == {"PER_TX", "DAILY", "MONTHLY"}
    assert scope_type == "limitconfigscope"
    assert window_type == "limitwindow"


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Test requires Postgres")
@pytest.mark.usefixtures("_apply_migrations")
def test_authorize_endpoint_not_failing_with_contract_limits():
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE operations, cards, terminals, merchants, clients, limit_configs RESTART IDENTITY CASCADE"
            )
        )

    db = SessionLocal()
    try:
        client_id = uuid4()
        db.add(Client(id=client_id, name="Client", status="ACTIVE"))
        db.add(Card(id="card-contract", client_id=str(client_id), status="ACTIVE"))
        db.add(Merchant(id="merchant-contract", name="Merchant", status="ACTIVE"))
        db.add(Terminal(id="terminal-contract", merchant_id="merchant-contract", status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    payload = {
        "client_id": str(client_id),
        "card_id": "card-contract",
        "terminal_id": "terminal-contract",
        "merchant_id": "merchant-contract",
        "amount": 1000,
        "currency": "RUB",
        "ext_operation_id": "ext-contract-1",
    }

    response = TestClient(app).post("/api/v1/transactions/authorize", json=payload)
    assert response.status_code < 500
