from __future__ import annotations

import base64
from datetime import datetime, timezone
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
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.decision_memory import DecisionMemoryRecord
from app.models.marketplace_catalog import MarketplaceService, MarketplaceServiceStatus
from app.models.marketplace_offers import (
    MarketplaceOffer,
    MarketplaceOfferEntitlementScope,
    MarketplaceOfferGeoScope,
    MarketplaceOfferPriceModel,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)
from app.models.marketplace_orders import (
    MarketplaceOrder,
    MarketplaceOrderEvent,
    MarketplaceOrderLine,
    MarketplaceOrderProof,
)
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanLimit,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.routers.client_marketplace_orders import router as client_orders_router
from app.routers.partner.marketplace_orders import router as partner_orders_router
from app.security.rbac.principal import Principal, get_principal
from app.services import entitlements_service
from app.services.case_events_service import verify_case_event_signatures
from app.tests.utils import ensure_connectable, get_database_url


CURRENT_PRINCIPAL: Principal | None = None


@pytest.fixture(autouse=True)
def _prepare_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    entitlements_service._ENTITLEMENTS_CACHE.clear()
    monkeypatch.setattr(entitlements_service, "DB_SCHEMA", None, raising=False)
    yield
    entitlements_service._ENTITLEMENTS_CACHE.clear()


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
        CaseSnapshot.__table__,
        CaseComment.__table__,
        CaseEvent.__table__,
        DecisionMemoryRecord.__table__,
        MarketplaceService.__table__,
        MarketplaceOffer.__table__,
        MarketplaceOrder.__table__,
        MarketplaceOrderLine.__table__,
        MarketplaceOrderProof.__table__,
        MarketplaceOrderEvent.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_orders_router, prefix="/api/v1")
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


@pytest.fixture()
def gated_api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        SubscriptionPlan.__table__,
        SubscriptionPlanModule.__table__,
        SubscriptionPlanLimit.__table__,
        ClientSubscription.__table__,
        Case.__table__,
        CaseSnapshot.__table__,
        CaseComment.__table__,
        CaseEvent.__table__,
        DecisionMemoryRecord.__table__,
        MarketplaceService.__table__,
        MarketplaceOffer.__table__,
        MarketplaceOrder.__table__,
        MarketplaceOrderLine.__table__,
        MarketplaceOrderProof.__table__,
        MarketplaceOrderEvent.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_orders_router, prefix="/api/v1")
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


def _create_offer(db: Session, partner_id: str) -> MarketplaceOffer:
    service = MarketplaceService(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Diagnostics",
        description="Engine diagnostics",
        category="Auto",
        status=MarketplaceServiceStatus.ACTIVE,
        duration_min=30,
    )
    offer = MarketplaceOffer(
        id=str(uuid4()),
        partner_id=partner_id,
        subject_type=MarketplaceOfferSubjectType.SERVICE,
        subject_id=str(service.id),
        title_override="Diagnostics",
        status=MarketplaceOfferStatus.ACTIVE,
        currency="RUB",
        price_model=MarketplaceOfferPriceModel.FIXED,
        price_amount=Decimal("1500"),
        geo_scope=MarketplaceOfferGeoScope.ALL_PARTNER_LOCATIONS,
        location_ids=[],
        entitlement_scope=MarketplaceOfferEntitlementScope.ALL_CLIENTS,
        allowed_subscription_codes=[],
        allowed_client_ids=[],
    )
    db.add(service)
    db.add(offer)
    db.commit()
    return offer


def _seed_marketplace_subscription(db: Session, *, client_id: str, enabled: bool) -> None:
    plan_id = f"plan-{uuid4()}"
    db.add(SubscriptionPlan(id=plan_id, code=f"PLAN_{uuid4().hex[:8].upper()}", title="Marketplace", is_active=True))
    db.add(
        SubscriptionPlanModule(
            plan_id=plan_id,
            module_code=SubscriptionModuleCode.MARKETPLACE,
            enabled=enabled,
            tier="base",
            limits={},
        )
    )
    db.add(
        ClientSubscription(
            id=str(uuid4()),
            tenant_id=1,
            client_id=client_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            start_at=datetime.now(timezone.utc),
            auto_renew=False,
        )
    )
    db.commit()


def _create_order(client: TestClient, client_id: str, offer_id: str) -> str:
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    response = client.post(
        "/api/v1/marketplace/client/orders",
        json={
            "items": [{"offer_id": offer_id, "qty": 1}],
            "payment_method": "NEFT_INTERNAL",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_order(db: Session, client_id: str, partner_id: str) -> str:
    order = MarketplaceOrder(
        id=str(uuid4()),
        client_id=client_id,
        partner_id=partner_id,
        status="CREATED",
        payment_status="UNPAID",
        payment_method="NEFT_INTERNAL",
        currency="RUB",
        subtotal_amount=Decimal("1500"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("1500"),
        price_snapshot={
            "currency": "RUB",
            "subtotal": "1500",
            "discount": "0",
            "total": "1500",
        },
    )
    db.add(order)
    db.commit()
    return str(order.id)


def test_client_creates_order_with_audit(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    with SessionLocal() as db:
        order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one()
        assert order.status == "PENDING_PAYMENT"
        lines = db.query(MarketplaceOrderLine).filter(MarketplaceOrderLine.order_id == order_id).all()
        assert len(lines) == 1
        assert str(lines[0].offer_id) == str(offer.id)
        subject_type = lines[0].subject_type.value if hasattr(lines[0].subject_type, "value") else lines[0].subject_type
        assert subject_type == "SERVICE"
        events = db.query(MarketplaceOrderEvent).filter(MarketplaceOrderEvent.order_id == order_id).all()
        assert events
        assert events[0].audit_event_id is not None

        case = db.query(Case).filter(Case.entity_id == str(order.id)).one()
        signature_check = verify_case_event_signatures(db, case_id=str(case.id))
        assert signature_check.verified is True


def test_client_order_incidents_returns_cases_linked_by_order_entity(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)
    other_order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    response = client.get(f"/api/v1/marketplace/client/orders/{order_id}/incidents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 50
    assert payload["next_cursor"] is None
    assert len(payload["items"]) == 1
    assert payload["items"][0]["entity_id"] == order_id
    assert payload["items"][0]["title"] == f"Marketplace order {order_id}"
    assert payload["items"][0]["entity_id"] != other_order_id


def test_partner_order_incidents_returns_cases_linked_by_order_entity(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)
    other_order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    response = client.get(f"/api/v1/marketplace/partner/orders/{order_id}/incidents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 50
    assert payload["next_cursor"] is None
    assert len(payload["items"]) == 1
    assert payload["items"][0]["entity_id"] == order_id
    assert payload["items"][0]["title"] == f"Marketplace order {order_id}"
    assert payload["items"][0]["entity_id"] != other_order_id


def test_partner_order_incidents_denied_for_foreign_partner(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())
    foreign_partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(foreign_partner_id)
    response = client.get(f"/api/v1/marketplace/partner/orders/{order_id}/incidents")

    assert response.status_code == 403


def test_marketplace_order_cases_use_default_tenant_for_tokens_without_tenant_claim(
    api_client: tuple[TestClient, sessionmaker],
) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    with SessionLocal() as db:
        case = db.query(Case).filter(Case.entity_id == order_id).one()

    assert case.tenant_id == 1
    assert case.case_source_ref_type == "MARKETPLACE_ORDER"


def test_partner_confirms_and_completes_order(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    pay_response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "PAID"

    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    confirm_response = client.post(f"/api/v1/marketplace/partner/orders/{order_id}:confirm", json={})
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "CONFIRMED_BY_PARTNER"

    proof_response = client.post(
        f"/api/v1/marketplace/partner/orders/{order_id}/proofs",
        json={"attachment_id": str(uuid4()), "kind": "PHOTO", "note": "Done"},
    )
    assert proof_response.status_code == 201

    complete_response = client.post(
        f"/api/v1/marketplace/partner/orders/{order_id}:complete",
        json={"comment": "Done"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "COMPLETED"


def test_invalid_partner_access_denied(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_partner_principal(other_partner_id)
    response = client.post(f"/api/v1/marketplace/partner/orders/{order_id}:confirm", json={})
    assert response.status_code == 403


def test_invalid_transition_conflict(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    pay_response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )
    assert pay_response.status_code == 200
    response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )
    assert response.status_code == 409


def test_client_cancel_allowed_only_when_created(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        offer = _create_offer(db, partner_id)

    order_id = _create_order(client, client_id, offer.id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    cancel_response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}/cancel",
        json={"reason": None},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELED_BY_CLIENT"

    new_order_id = _create_order(client, client_id, offer.id)
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    client.post(
        f"/api/v1/marketplace/client/orders/{new_order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )
    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    client.post(f"/api/v1/marketplace/partner/orders/{new_order_id}:confirm", json={})
    client.post(
        f"/api/v1/marketplace/partner/orders/{new_order_id}/proofs",
        json={"attachment_id": str(uuid4()), "kind": "PHOTO", "note": "Done"},
    )
    client.post(f"/api/v1/marketplace/partner/orders/{new_order_id}:complete", json={"comment": "Done"})

    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    invalid_cancel = client.post(
        f"/api/v1/marketplace/client/orders/{new_order_id}/cancel",
        json={"reason": "Late"},
    )
    assert invalid_cancel.status_code == 409


def test_client_cancel_accepts_live_request_shape_with_nullable_reason(api_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = api_client
    client_id = str(uuid4())
    partner_id = str(uuid4())

    with SessionLocal() as db:
        order_id = _seed_order(db, client_id, partner_id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    cancel_response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}/cancel",
        json={"reason": None},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELED_BY_CLIENT"

    with SessionLocal() as db:
        order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one()
        assert order.status == "CANCELED_BY_CLIENT"


def test_client_marketplace_orders_require_marketplace_module_when_entitlements_are_present(
    gated_api_client: tuple[TestClient, sessionmaker],
) -> None:
    client, SessionLocal = gated_api_client
    client_id = str(uuid4())

    with SessionLocal() as db:
        _seed_marketplace_subscription(db, client_id=client_id, enabled=False)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    response = client.get("/api/v1/marketplace/client/orders")
    assert response.status_code == 403
    assert response.json() == {"detail": "feature_not_included"}


def test_marketplace_order_commission_snapshot_uses_meta_storage_truth() -> None:
    order = MarketplaceOrder(
        id=str(uuid4()),
        client_id=str(uuid4()),
        partner_id=str(uuid4()),
        price_snapshot={"currency": "RUB", "subtotal": "1000"},
        status="CREATED",
        meta=None,
    )

    order.commission_snapshot = {
        "rule_id": str(uuid4()),
        "type": "PERCENT",
        "rate": "0.10",
        "amount": "100",
    }

    assert order.meta is not None
    assert order.meta["commission_snapshot"]["amount"] == "100"
    assert order.commission_snapshot is not None
    assert order.commission_snapshot["type"] == "PERCENT"

    order.commission_snapshot = None
    assert order.commission_snapshot is None
    assert order.meta is None


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
