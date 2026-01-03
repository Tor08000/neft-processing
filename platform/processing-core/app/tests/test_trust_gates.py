from __future__ import annotations

import base64
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from app.db import get_engine, get_sessionmaker
from app.db.types import new_uuid_str
from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseEvent, CaseEventType, CaseKind, CasePriority
from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationSeverity,
    FuelCard,
    FuelCardStatus,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachStatus,
    FuelLimitBreachType,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.marketplace_catalog import (
    MarketplacePriceModel,
    MarketplaceProduct,
    MarketplaceProductStatus,
    MarketplaceProductType,
    PartnerProfile,
)
from app.models.marketplace_orders import MarketplaceOrderActorType, MarketplaceOrderEvent
from app.security.rbac.principal import Principal
from app.services.audit_service import ActorType, RequestContext
from app.services.billing_service import capture_payment, issue_invoice, refund_payment
from app.services.case_events_service import CaseEventActor, verify_case_event_chain, verify_case_event_signatures
from app.services.case_export_service import create_export
from app.services.case_export_verification_service import verify_export
from app.services.cases_service import create_case
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.marketplace_order_service import MarketplaceOrderService
from app.services.fleet_policy_engine import evaluate_policies_for_breach
from app.services.fleet_service import set_limit


class FakeExportStorage:
    objects: dict[str, tuple[bytes, str]] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def put_bytes(self, key: str, content: bytes, *, content_type: str, retain_until=None) -> None:
        self.objects[key] = (content, content_type)

    def get_bytes(self, key: str) -> bytes:
        content, _ = self.objects.get(key, (b"", ""))
        return content


@pytest.fixture(autouse=True)
def _audit_signing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(private_pem).decode("utf-8"))


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        return
    tables = [
        "audit_log",
        "case_events",
        "case_comments",
        "case_snapshots",
        "cases",
        "decision_memory",
        "internal_ledger_entries",
        "internal_ledger_transactions",
        "internal_ledger_accounts",
        "billing_refunds",
        "billing_payments",
        "billing_invoices",
        "reconciliation_links",
        "marketplace_order_events",
        "marketplace_orders",
        "marketplace_products",
        "partner_profiles",
        "fleet_policy_executions",
        "fleet_action_policies",
        "fleet_notification_outbox",
        "fuel_limit_breaches",
        "fuel_limits",
        "fuel_transactions",
        "fuel_stations",
        "fuel_networks",
        "fuel_cards",
    ]
    table_list = ", ".join(tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))


def _require_postgres() -> None:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        pytest.skip("trust gate tests require postgres")


def _admin_principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        roles={"admin"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims={"tenant_id": 1, "email": "ops@neft.io"},
    )


def _assert_case_event_integrity(db_session, case_id: str) -> None:
    chain = verify_case_event_chain(db_session, case_id=case_id)
    signatures = verify_case_event_signatures(db_session, case_id=case_id)
    assert chain.verified is True
    assert signatures.verified is True


def _assert_db_worm(
    engine,
    *,
    table: str,
    column: str,
    record_id: str,
    expected_value: object,
    update_value: object | None = None,
) -> None:
    update_value = expected_value if update_value is None else update_value
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
                {"value": update_value, "id": record_id},
            )
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": record_id})
    with engine.begin() as conn:
        row = conn.execute(text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": record_id}).one()
    assert row[0] == expected_value


def test_trust_gate_case_creation_redaction_and_signature() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    try:
        case = create_case(
            session,
            tenant_id=1,
            kind=CaseKind.OPERATION,
            entity_id="op-1",
            kpi_key=None,
            window_days=None,
            title=None,
            priority=CasePriority.MEDIUM,
            note="contact ops@neft.io token=secret-token",
            explain=None,
            diff=None,
            selected_actions=None,
            mastery_snapshot=None,
            created_by="user-1",
            request_id="req-1",
            trace_id="trace-1",
        )
        session.commit()

        event = (
            session.query(CaseEvent)
            .filter(CaseEvent.case_id == case.id)
            .filter(CaseEvent.type == CaseEventType.CASE_CREATED)
            .one()
        )
        assert event.signature is not None
        changes = event.payload_redacted.get("changes") or []
        note_change = next(item for item in changes if item["field"] == "note")
        assert note_change["to"]["redacted"] is True
        _assert_case_event_integrity(session, case_id=str(case.id))
    finally:
        session.close()


def test_trust_gate_finance_case_events() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    try:
        actor = CaseEventActor(id="user-1", email="ops@neft.io")
        invoice_result = issue_invoice(
            session,
            tenant_id=1,
            client_id="client-1",
            case_id=None,
            currency="RUB",
            amount_total=Decimal("100"),
            due_at=None,
            idempotency_key="trust-invoice-1",
            actor=actor,
            request_id="req-invoice",
            trace_id="trace-invoice",
        )
        payment_result = capture_payment(
            session,
            tenant_id=1,
            invoice_id=invoice_result.invoice.id,
            provider="bank",
            provider_payment_id="pay-1",
            amount=Decimal("100"),
            currency="RUB",
            idempotency_key="trust-payment-1",
            actor=actor,
            request_id="req-payment",
            trace_id="trace-payment",
        )
        refund_result = refund_payment(
            session,
            tenant_id=1,
            payment_id=payment_result.payment.id,
            provider_refund_id="refund-1",
            amount=Decimal("100"),
            currency="RUB",
            idempotency_key="trust-refund-1",
            actor=actor,
            request_id="req-refund",
            trace_id="trace-refund",
        )
        session.commit()

        case_events = (
            session.query(CaseEvent)
            .filter(CaseEvent.case_id == invoice_result.invoice.case_id)
            .filter(CaseEvent.type.in_(
                [
                    CaseEventType.INVOICE_ISSUED,
                    CaseEventType.PAYMENT_CAPTURED,
                    CaseEventType.PAYMENT_REFUNDED,
                ]
            ))
            .all()
        )
        assert {event.type for event in case_events} == {
            CaseEventType.INVOICE_ISSUED,
            CaseEventType.PAYMENT_CAPTURED,
            CaseEventType.PAYMENT_REFUNDED,
        }
        assert all(event.signature for event in case_events)
        _assert_case_event_integrity(session, case_id=str(invoice_result.invoice.case_id))
        assert refund_result.payment.status.value == "REFUNDED_FULL"
    finally:
        session.close()


def test_trust_gate_ledger_audit_log_redaction() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    try:
        ledger = InternalLedgerService(session)
        result = ledger.post_transaction(
            tenant_id=1,
            transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
            external_ref_type="manual",
            external_ref_id="adj-1",
            idempotency_key="trust-ledger-1",
            posted_at=datetime.now(timezone.utc),
            meta={"token": "secret-token"},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=1000,
                    currency="RUB",
                    meta={"token": "secret-token"},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=1000,
                    currency="RUB",
                    meta={"token": "secret-token"},
                ),
            ],
        )
        session.commit()

        audit = (
            session.query(AuditLog)
            .filter(AuditLog.entity_id == str(result.transaction.id))
            .filter(AuditLog.event_type == "ledger_transaction")
            .one()
        )
        assert audit.prev_hash == "GENESIS"
        assert audit.hash is not None
        assert audit.after["entries"][0]["meta"]["token"] == "***"
    finally:
        session.close()


def test_trust_gate_marketplace_order_events() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    try:
        partner_id = str(uuid4())
        client_id = str(uuid4())
        product = MarketplaceProduct(
            partner_id=partner_id,
            type=MarketplaceProductType.SERVICE,
            title="Oil change",
            description="Service",
            category="maintenance",
            price_model=MarketplacePriceModel.FIXED,
            price_config={"amount": "1000"},
            status=MarketplaceProductStatus.PUBLISHED,
        )
        session.add(PartnerProfile(partner_id=partner_id, company_name="Partner", description="desc"))
        session.add(product)
        session.commit()

        request_ctx = RequestContext(
            actor_type=ActorType.USER,
            actor_id=str(uuid4()),
            actor_email="ops@neft.io",
            tenant_id=1,
        )
        service = MarketplaceOrderService(session, request_ctx=request_ctx)
        order = service.create_order(
            client_id=client_id,
            product_id=str(product.id),
            quantity=Decimal("1"),
            note="bearer abc.def.ghi",
            external_ref="ext-1",
            actor=MarketplaceOrderActorType.CLIENT,
        )
        service.accept_order(
            partner_id=partner_id,
            order_id=str(order.id),
            note="accepted",
            actor=MarketplaceOrderActorType.PARTNER,
        )
        session.commit()

        events = session.query(MarketplaceOrderEvent).filter(MarketplaceOrderEvent.order_id == order.id).all()
        assert {event.event_type.value for event in events} == {"ORDER_CREATED", "ORDER_ACCEPTED"}
        created_event = next(event for event in events if event.event_type.value == "ORDER_CREATED")
        assert created_event.payload_redacted["note"]["redacted"] is True

        case = (
            session.query(Case)
            .filter(Case.kind == CaseKind.ORDER)
            .filter(Case.entity_id == str(order.id))
            .one()
        )
        _assert_case_event_integrity(session, case_id=str(case.id))
    finally:
        session.close()


def test_trust_gate_fleet_limits_and_auto_block() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    try:
        client_id = str(uuid4())
        card = FuelCard(
            tenant_id=1,
            client_id=client_id,
            card_token="token-1",
            card_alias="NEFT-1",
            status=FuelCardStatus.ACTIVE,
        )
        session.add(card)
        session.commit()

        principal = _admin_principal()
        limit = set_limit(
            session,
            client_id=client_id,
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            period=FuelLimitPeriod.DAILY,
            amount_limit=Decimal("100"),
            volume_limit_liters=None,
            categories=None,
            stations_allowlist=None,
            effective_from=None,
            principal=principal,
            request_id="req-limit",
            trace_id="trace-limit",
        )

        breach = FuelLimitBreach(
            client_id=client_id,
            scope_type=FuelLimitBreachScopeType.CARD,
            scope_id=card.id,
            period=FuelLimitPeriod.DAILY,
            limit_id=limit.id,
            breach_type=FuelLimitBreachType.AMOUNT,
            threshold=Decimal("100"),
            observed=Decimal("180"),
            delta=Decimal("80"),
            occurred_at=datetime.now(timezone.utc),
            status=FuelLimitBreachStatus.OPEN,
        )
        policy = FleetActionPolicy(
            client_id=client_id,
            scope_type=FleetActionPolicyScopeType.CLIENT,
            trigger_type=FleetActionTriggerType.LIMIT_BREACH,
            trigger_severity_min=FleetNotificationSeverity.LOW,
            breach_kind=FleetActionBreachKind.HARD,
            action=FleetActionPolicyAction.AUTO_BLOCK_CARD,
            cooldown_seconds=300,
            active=True,
        )
        session.add_all([breach, policy])
        session.commit()

        evaluate_policies_for_breach(session, str(breach.id))
        session.commit()

        case = session.query(Case).filter(Case.kind == CaseKind.FLEET, Case.entity_id == client_id).one()
        events = session.query(CaseEvent).filter(CaseEvent.case_id == case.id).all()
        event_types = {event.type for event in events}
        assert CaseEventType.LIMIT_SET in event_types
        assert CaseEventType.FUEL_CARD_AUTO_BLOCKED in event_types
        assert all(event.signature for event in events)
        _assert_case_event_integrity(session, case_id=str(case.id))
    finally:
        session.close()


def test_trust_gate_export_sign_and_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_postgres()
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    monkeypatch.setattr("app.services.case_export_verification_service.ExportStorage", FakeExportStorage)
    session = get_sessionmaker()()
    try:
        case = create_case(
            session,
            tenant_id=1,
            kind=CaseKind.OPERATION,
            entity_id="op-export-1",
            kpi_key=None,
            window_days=None,
            title=None,
            priority=CasePriority.MEDIUM,
            note="export",
            explain=None,
            diff=None,
            selected_actions=None,
            mastery_snapshot=None,
            created_by="user-1",
            request_id="req-export",
            trace_id="trace-export",
        )
        export = create_export(
            session,
            kind="CASE",
            case_id=str(case.id),
            payload={"case": {"id": str(case.id), "token": "secret-token"}},
            mastery_snapshot=None,
            actor=CaseEventActor(id="user-1", email="ops@neft.io"),
            request_id="req-export",
            trace_id="trace-export",
        )
        session.commit()

        verification = verify_export(session, export=export)
        assert verification.content_hash_verified is True
        assert verification.artifact_signature_verified is True
        assert verification.audit_chain_verified is True
    finally:
        session.close()


def test_trust_gate_db_immutability() -> None:
    _require_postgres()
    session = get_sessionmaker()()
    engine = get_engine()
    try:
        ledger = InternalLedgerService(session)
        ledger_result = ledger.post_transaction(
            tenant_id=1,
            transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
            external_ref_type="manual",
            external_ref_id="worm-ledger",
            idempotency_key="worm-ledger-1",
            posted_at=datetime.now(timezone.utc),
            meta=None,
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=1000,
                    currency="RUB",
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=1000,
                    currency="RUB",
                ),
            ],
        )
        actor = CaseEventActor(id="user-1", email="ops@neft.io")
        invoice_result = issue_invoice(
            session,
            tenant_id=1,
            client_id="client-1",
            case_id=None,
            currency="RUB",
            amount_total=Decimal("50"),
            due_at=None,
            idempotency_key="worm-invoice-1",
            actor=actor,
            request_id="req-worm",
            trace_id="trace-worm",
        )
        payment_result = capture_payment(
            session,
            tenant_id=1,
            invoice_id=invoice_result.invoice.id,
            provider="bank",
            provider_payment_id="pay-worm",
            amount=Decimal("50"),
            currency="RUB",
            idempotency_key="worm-payment-1",
            actor=actor,
            request_id="req-worm",
            trace_id="trace-worm",
        )
        refund_result = refund_payment(
            session,
            tenant_id=1,
            payment_id=payment_result.payment.id,
            provider_refund_id="refund-worm",
            amount=Decimal("50"),
            currency="RUB",
            idempotency_key="worm-refund-1",
            actor=actor,
            request_id="req-worm",
            trace_id="trace-worm",
        )

        partner_id = str(uuid4())
        product = MarketplaceProduct(
            partner_id=partner_id,
            type=MarketplaceProductType.SERVICE,
            title="Service",
            description="desc",
            category="cat",
            price_model=MarketplacePriceModel.FIXED,
            price_config={"amount": "100"},
            status=MarketplaceProductStatus.PUBLISHED,
        )
        session.add(PartnerProfile(partner_id=partner_id, company_name="Partner", description="desc"))
        session.add(product)
        session.flush()
        request_ctx = RequestContext(actor_type=ActorType.USER, actor_id=str(uuid4()), actor_email="ops@neft.io")
        order_service = MarketplaceOrderService(session, request_ctx=request_ctx)
        order = order_service.create_order(
            client_id=str(uuid4()),
            product_id=str(product.id),
            quantity=Decimal("1"),
            note="immutable",
            external_ref="order-worm",
            actor=MarketplaceOrderActorType.CLIENT,
        )

        network_id = new_uuid_str()
        station_id = new_uuid_str()
        card_id = new_uuid_str()
        network = FuelNetwork(id=network_id, name="Network", provider_code="NET-1", status=FuelNetworkStatus.ACTIVE)
        station = FuelStation(
            id=station_id,
            network_id=network_id,
            name="Station",
            status=FuelStationStatus.ACTIVE,
            station_code="ST-1",
        )
        card = FuelCard(
            id=card_id,
            tenant_id=1,
            client_id="client-1",
            card_token="card-token",
            card_alias="CARD-1",
            status=FuelCardStatus.ACTIVE,
        )
        session.add_all([network, station, card])
        session.flush()
        fuel_tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card_id,
            vehicle_id=None,
            driver_id=None,
            station_id=station_id,
            network_id=network_id,
            occurred_at=datetime.now(timezone.utc),
            fuel_type=FuelType.DIESEL,
            volume_ml=1000,
            unit_price_minor=1000,
            amount_total_minor=1000,
            currency="RUB",
            status=FuelTransactionStatus.APPROVED,
            provider_code="PROVIDER",
            provider_tx_id="TX-1",
            external_ref="EXT-1",
        )
        session.add(fuel_tx)
        session.commit()

        audit_entry = session.query(AuditLog).filter(AuditLog.entity_id == str(ledger_result.transaction.id)).one()
        ledger_entry = (
            session.query(InternalLedgerEntry)
            .filter(InternalLedgerEntry.ledger_transaction_id == ledger_result.transaction.id)
            .first()
        )
        order_event = (
            session.query(MarketplaceOrderEvent)
            .filter(MarketplaceOrderEvent.order_id == order.id)
            .first()
        )
        case_event = session.query(CaseEvent).filter(CaseEvent.case_id == invoice_result.invoice.case_id).first()

        _assert_db_worm(engine, table="audit_log", column="event_type", record_id=str(audit_entry.id), expected_value=audit_entry.event_type)
        _assert_db_worm(
            engine,
            table="internal_ledger_entries",
            column="amount",
            record_id=str(ledger_entry.id),
            expected_value=ledger_entry.amount,
        )
        _assert_db_worm(
            engine,
            table="billing_invoices",
            column="status",
            record_id=str(invoice_result.invoice.id),
            expected_value=invoice_result.invoice.status.value,
        )
        _assert_db_worm(
            engine,
            table="billing_payments",
            column="status",
            record_id=str(payment_result.payment.id),
            expected_value=payment_result.payment.status.value,
        )
        _assert_db_worm(
            engine,
            table="billing_refunds",
            column="status",
            record_id=str(refund_result.refund.id),
            expected_value=refund_result.refund.status.value,
        )
        _assert_db_worm(
            engine,
            table="marketplace_order_events",
            column="event_type",
            record_id=str(order_event.id),
            expected_value=order_event.event_type.value,
        )
        _assert_db_worm(
            engine,
            table="fuel_transactions",
            column="status",
            record_id=str(fuel_tx.id),
            expected_value=fuel_tx.status.value,
        )
        _assert_db_worm(
            engine,
            table="case_events",
            column="type",
            record_id=str(case_event.id),
            expected_value=case_event.type.value,
        )
    finally:
        session.close()
