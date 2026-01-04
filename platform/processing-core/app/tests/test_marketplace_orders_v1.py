from __future__ import annotations

import base64
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.models.cases import Case, CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.marketplace_catalog import (
    MarketplacePriceModel,
    MarketplaceProduct,
    MarketplaceProductStatus,
    MarketplaceProductType,
)
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderEvent
from app.routers.client_marketplace_orders import router as client_orders_router
from app.routers.partner.marketplace_orders import router as partner_orders_router
from app.security.rbac.principal import Principal, get_principal
from app.services.case_events_service import verify_case_event_signatures
from app.tests.utils import ensure_connectable, get_database_url


CURRENT_PRINCIPAL: Principal | None = None


def _build_client_principal(client_id: str) -> Principal:
    return Principal(
        user_id=None,
        roles={"client_user"},
        scopes=set(),
        client_id=UUID(client_id),
        partner_id=None,
        is_admin=False,
        raw_claims={"client_id": client_id, "roles": ["client_user"]},
    )


def _build_partner_principal(partner_id: str) -> Principal:
    return Principal(
        user_id=UUID(str(uuid4())),
        roles={"partner_user"},
        scopes=set(),
        client_id=None,
        partner_id=UUID(partner_id),
        is_admin=False,
        raw_claims={"user_id": str(uuid4()), "roles": ["partner_user"], "partner_id": partner_id},
    )


def _make_alembic_config(db_url: str) -> Config:
    app_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(app_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(app_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture()
def signing_key() -> bytes:
    private_key = Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(autouse=True)
def audit_signing_env(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(signing_key).decode("utf-8"))


@pytest.fixture()
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        Case.__table__,
        CaseEvent.__table__,
        DecisionMemoryRecord.__table__,
        MarketplaceProduct.__table__,
        MarketplaceOrder.__table__,
        MarketplaceOrderEvent.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_orders_router, prefix="/api")
    app.include_router(partner_orders_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_principal() -> Principal:
        if CURRENT_PRINCIPAL is None:
            raise RuntimeError("principal_not_set")
        return CURRENT_PRINCIPAL

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = override_get_principal

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(tables):
        table.drop(bind=engine)
    engine.dispose()


def _create_product(db: Session, partner_id: str) -> MarketplaceProduct:
    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=partner_id,
        type=MarketplaceProductType.SERVICE,
        title="Diagnostics",
        description="Engine diagnostics",
        category="Auto",
        price_model=MarketplacePriceModel.FIXED,
        price_config={"amount": 1500, "currency": "RUB"},
        status=MarketplaceProductStatus.PUBLISHED,
        moderation_status="APPROVED",
    )
    db.add(product)
    db.commit()
    return product


def _create_order(client: TestClient, client_id: str, product_id: str, *, idempotency_key: str | None = None) -> str:
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    response = client.post(
        "/api/client/marketplace/orders",
        json={
            "product_id": product_id,
            "quantity": 2,
            "note": "Need this soon",
            "idempotency_key": idempotency_key or f"order-{uuid4()}",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_client_creates_order_with_audit(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        product = _create_product(db, partner_id)

    order_id = _create_order(client, client_id, product.id)

    with SessionLocal() as db:
        order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one()
        assert order.status == "CREATED"
        events = db.query(MarketplaceOrderEvent).filter(MarketplaceOrderEvent.order_id == order_id).all()
        assert events
        assert events[0].audit_event_id is not None

        case = db.query(Case).filter(Case.entity_id == str(order.id)).one()
        signature_check = verify_case_event_signatures(db, case_id=str(case.id))
        assert signature_check.verified is True


def test_partner_accepts_and_progresses_order(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        product = _create_product(db, partner_id)

    order_id = _create_order(client, client_id, product.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    accept_response = client.post(f"/api/partner/orders/{order_id}/accept", json={})
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"

    start_response = client.post(f"/api/partner/orders/{order_id}/start", json={})
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "IN_PROGRESS"

    progress_response = client.post(
        f"/api/partner/orders/{order_id}/progress",
        json={"progress_percent": 40, "message": "Halfway"},
    )
    assert progress_response.status_code == 200

    complete_response = client.post(
        f"/api/partner/orders/{order_id}/complete",
        json={"summary": "Done"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "COMPLETED"


def test_invalid_partner_access_denied(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())

    with SessionLocal() as db:
        product = _create_product(db, partner_id)

    order_id = _create_order(client, client_id, product.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(other_partner_id)
    response = client.post(f"/api/partner/orders/{order_id}/accept", json={})
    assert response.status_code == 403


def test_invalid_transition_conflict(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        product = _create_product(db, partner_id)

    order_id = _create_order(client, client_id, product.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    response = client.post(f"/api/partner/orders/{order_id}/complete", json={"summary": "Too soon"})
    assert response.status_code == 409


def test_client_cancel_allowed_only_when_created(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        product = _create_product(db, partner_id)

    order_id = _create_order(client, client_id, product.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    cancel_response = client.post(
        f"/api/client/marketplace/orders/{order_id}/cancel",
        json={"reason": "Not needed"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"

    new_order_id = _create_order(client, client_id, product.id)
    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    client.post(f"/api/partner/orders/{new_order_id}/accept", json={})
    client.post(f"/api/partner/orders/{new_order_id}/start", json={})
    client.post(f"/api/partner/orders/{new_order_id}/complete", json={"summary": "Done"})

    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    invalid_cancel = client.post(
        f"/api/client/marketplace/orders/{new_order_id}/cancel",
        json={"reason": "Late"},
    )
    assert invalid_cancel.status_code == 409


@pytest.mark.skipif(sa.create_engine(get_database_url()).dialect.name != "postgresql", reason="WORM guard requires Postgres")
def test_marketplace_order_events_worm_guard_blocks_update_and_delete() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)
    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    schema = DB_SCHEMA
    case_id = str(uuid4())
    order_id = str(uuid4())
    event_id = str(uuid4())
    case_event_id = str(uuid4())
    schema_prefix = f'"{schema}".' if schema else ""

    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET search_path TO "{schema}"')
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}cases
                (id, tenant_id, kind, title, status, queue, priority, escalation_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (case_id, 1, "order", "Marketplace order case", "TRIAGE", "GENERAL", "MEDIUM", 0),
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}case_events
                (id, case_id, seq, type, payload_redacted, prev_hash, hash)
            VALUES (%s, %s, %s, %s, %s::json, %s, %s)
            """,
            (
                case_event_id,
                case_id,
                1,
                "CASE_CREATED",
                '{"note":"init"}',
                "GENESIS",
                "hash",
            ),
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}marketplace_orders
                (id, client_id, partner_id, product_id, quantity, price_snapshot, status)
            VALUES (%s, %s, %s, %s, %s, %s::json, %s)
            """,
            (
                order_id,
                str(uuid4()),
                str(uuid4()),
                str(uuid4()),
                Decimal("1.0"),
                '{"price_model":"FIXED","price_config":{"amount":100,"currency":"RUB"}}',
                "CREATED",
            ),
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}marketplace_order_events
                (id, order_id, event_type, payload_redacted, actor_type, audit_event_id)
            VALUES (%s, %s, %s, %s::json, %s, %s)
            """,
            (
                event_id,
                order_id,
                "ORDER_CREATED",
                '{"note":"hello"}',
                "client",
                case_event_id,
            ),
        )

        with pytest.raises(sa.exc.DBAPIError) as exc_info:
            connection.exec_driver_sql(
                f"UPDATE {schema_prefix}marketplace_order_events SET payload_redacted = %s::json WHERE id = %s",
                ('{"tampered":true}', event_id),
            )
        assert "marketplace_order_events is WORM" in str(exc_info.value)

        with pytest.raises(sa.exc.DBAPIError) as exc_info:
            connection.exec_driver_sql(
                f"DELETE FROM {schema_prefix}marketplace_order_events WHERE id = %s",
                (event_id,),
            )
        assert "marketplace_order_events is WORM" in str(exc_info.value)