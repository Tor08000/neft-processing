import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import OperationStatus
from app.models.terminal import Terminal
from app.tests.utils import ensure_connectable, get_database_url


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SKIP_POSTGRES_TESTS", "false").lower() in {"1", "true", "yes"},
    reason="Postgres integration tests explicitly skipped",
)

def test_authorize_persists_operation_in_postgres():
    configured_url = get_database_url()
    db_url = (
        configured_url
        if not configured_url.startswith("sqlite")
        else "postgresql+psycopg://neft:neft@postgres:5432/neft"
    )
    engine = ensure_connectable(db_url)
    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for this test")

    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    with engine.connect() as connection:
        connection.execute(sa.text("TRUNCATE TABLE operations RESTART IDENTITY CASCADE"))
        connection.commit()

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db

    try:
        with TestingSessionLocal() as session:
            client_pk = uuid4()
            session.add(Client(id=client_pk, name="Postgres Client", status="ACTIVE"))
            session.add(Card(id="pg-card", client_id=str(client_pk), status="ACTIVE"))
            session.add(Merchant(id="pg-merchant", name="PG", status="ACTIVE"))
            session.add(Terminal(id="pg-terminal", merchant_id="pg-merchant", status="ACTIVE"))
            session.commit()

        client = TestClient(app)
        payload = {
            "client_id": str(client_pk),
            "card_id": "pg-card",
            "terminal_id": "pg-terminal",
            "merchant_id": "pg-merchant",
            "amount": 1500,
            "currency": "RUB",
            "ext_operation_id": "pg-ext-1",
        }

        resp = client.post("/api/v1/transactions/authorize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["operation_id"] == "pg-ext-1"

        with engine.connect() as connection:
            count = connection.execute(sa.text("select count(*) from operations"))
            ops_count = count.scalar_one()
            status, response_message = connection.execute(
                sa.text(
                    "select status, response_message from operations order by created_at desc limit 1"
                )
            ).one()

        assert ops_count == 1
        assert status == OperationStatus.AUTHORIZED.value
        assert response_message == "APPROVED"
    finally:
        app.dependency_overrides.pop(get_db, None)
