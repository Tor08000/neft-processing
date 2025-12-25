import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.account import AccountType
from app.models.card import Card
from app.models.client import Client
from app.models.client_actions import DocumentAcknowledgement, InvoiceMessage, ReconciliationRequest
from app.models.contract_limits import LimitConfig, LimitConfigScope, LimitType, LimitWindow
from app.models.audit_log import ActorType, AuditLog, AuditVisibility
from app.models.invoice import InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType, RiskResult
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository
from app.models.ledger_entry import LedgerDirection
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_clients(session, client_id, other_client_id):
    session.add(
        Client(
            id=client_id,
            name="Client One",
            inn="7700",
            tariff_plan="STANDARD",
            account_manager="Manager",
            status="ACTIVE",
        )
    )
    session.add(Client(id=other_client_id, name="Client Two", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE", pan_masked="1111"))
    session.add(Card(id="card-2", client_id=str(other_client_id), status="ACTIVE", pan_masked="2222"))
    session.add(
        LimitConfig(
            scope=LimitConfigScope.CARD,
            subject_ref="card-1",
            limit_type=LimitType.DAILY_AMOUNT,
            value=1000,
            window=LimitWindow.DAILY,
            enabled=True,
        )
    )
    session.commit()


def test_client_profile_and_cards_filtered_by_client(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        profile = api_client.get("/api/v1/client/me")
        assert profile.status_code == 200
        body = profile.json()
        assert body["id"] == str(client_id)
        assert body["inn"] == "7700"
        assert body["tariff_plan"] == "STANDARD"

        cards = api_client.get("/api/v1/client/cards").json()
        assert len(cards["items"]) == 1
        assert cards["items"][0]["id"] == "card-1"
        assert cards["items"][0]["limits"][0]["type"] == "DAILY_AMOUNT"

        other_card = api_client.get("/api/v1/client/cards/card-2")
        assert other_card.status_code == 404


def test_client_operations_and_rbac(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)
    db_session.add(
        Operation(
            operation_id="op-1",
            operation_type=OperationType.AUTH,
            status=OperationStatus.APPROVED,
            merchant_id="m1",
            terminal_id="t1",
            client_id=str(client_id),
            card_id="card-1",
            amount=100,
            currency="RUB",
        )
    )
    db_session.add(
        Operation(
            operation_id="op-2",
            operation_type=OperationType.AUTH,
            status=OperationStatus.APPROVED,
            merchant_id="m2",
            terminal_id="t2",
            client_id=str(other_client_id),
            card_id="card-2",
            amount=200,
            currency="RUB",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        ops = api_client.get("/api/v1/client/operations").json()
        assert ops["total"] == 1
        assert ops["items"][0]["id"] == "op-1"

        details = api_client.get("/api/v1/client/operations/op-1")
        assert details.status_code == 200
        assert details.json()["id"] == "op-1"

        foreign = api_client.get("/api/v1/client/operations/op-2")
        assert foreign.status_code == 404

        # Client roles should not access admin endpoints
        from app.api.dependencies.admin import require_admin_user
        from app import services

        app.dependency_overrides[require_admin_user] = services.admin_auth.require_admin
        client_token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
        admin_resp = api_client.get(
            "/api/v1/admin/merchants",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert admin_resp.status_code == 403

        # Missing client_id in token must be rejected
        bad_token = make_jwt(roles=("CLIENT_USER",))
        resp = api_client.get(
            "/api/v1/client/cards",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403


def test_balances_and_statements(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)
    repo = AccountsRepository(db_session)
    ledger = LedgerRepository(db_session)

    account = repo.get_or_create_account(
        client_id=str(client_id),
        currency="RUB",
        account_type=AccountType.CLIENT_MAIN,
    )
    ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.CREDIT,
        amount=500,
        currency="RUB",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.DEBIT,
        amount=100,
        currency="RUB",
        posted_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        balances = api_client.get("/api/v1/client/balances").json()
        assert len(balances["items"]) == 1
        assert float(balances["items"][0]["current"]) == 400

        statement = api_client.get(
            "/api/v1/client/statements",
            params={
                "from": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
                "to": datetime(2024, 1, 3, tzinfo=timezone.utc).isoformat(),
            },
        )
        assert statement.status_code == 200
        data = statement.json()[0]
        assert data["start_balance"] == "0"
        assert data["credits"] in ("500", "500.0000")
        assert data["debits"] in ("100", "100.0000")
        assert data["end_balance"] in ("400", "400.0000")


def test_client_invoices_filtered(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2024, 3, 1),
            period_to=date(2024, 3, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
            lines=[
                BillingLineData(product_id="diesel", liters=Decimal("10"), unit_price=None, line_amount=1000, tax_amount=0)
            ],
        )
    )
    other_invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(other_client_id),
            period_from=date(2024, 3, 1),
            period_to=date(2024, 3, 31),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            lines=[BillingLineData(product_id="ai95", liters=None, unit_price=None, line_amount=2000, tax_amount=0)],
        )
    )

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        listing = api_client.get(
            "/api/v1/client/invoices",
            params={"status": ["SENT", "PAID"], "date_from": "2024-04-01", "date_to": "2024-04-30", "limit": 50},
        )
        assert listing.status_code == 200
        body = listing.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == invoice.id
        assert body["items"][0]["number"]
        assert body["items"][0]["amount_total"] == str(invoice.total_with_tax)

        details = api_client.get(f"/api/v1/client/invoices/{invoice.id}")
        assert details.status_code == 200
        assert details.json()["amount_due"] == str(invoice.amount_due)

        foreign = api_client.get(f"/api/v1/client/invoices/{other_invoice.id}")
        assert foreign.status_code == 403


def test_client_invoice_pdf_protected(db_session, make_jwt, monkeypatch):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2024, 5, 1),
            period_to=date(2024, 5, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="diesel", liters=None, unit_price=None, line_amount=5000, tax_amount=0)],
        )
    )
    invoice.pdf_object_key = f"invoices/{invoice.id}.pdf"
    db_session.commit()

    monkeypatch.setattr("app.routers.client_portal.S3Storage.get_bytes", lambda *_args, **_kwargs: b"pdf-bytes")

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(other_client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        forbidden = api_client.get(f"/api/v1/client/invoices/{invoice.id}/pdf")
        assert forbidden.status_code == 403

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get(f"/api/v1/client/invoices/{invoice.id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")


def test_client_invoice_audit_access_denied(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(other_client_id),
            period_from=date(2024, 7, 1),
            period_to=date(2024, 7, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 8, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="diesel", liters=None, unit_price=None, line_amount=1000, tax_amount=0)],
        )
    )

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get(f"/api/v1/client/invoices/{invoice.id}/audit")
        assert response.status_code == 403
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "CLIENT_ACCESS_FORBIDDEN")
        .filter(AuditLog.visibility == AuditVisibility.INTERNAL)
        .count()
        == 1
    )


def test_client_invoice_audit_returns_events(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2024, 8, 1),
            period_to=date(2024, 8, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 9, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="ai95", liters=None, unit_price=None, line_amount=2000, tax_amount=0)],
        )
    )
    db_session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            event_type="INVOICE_CREATED",
            entity_type="invoice",
            entity_id=invoice.id,
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            after={"amount": 2000, "status": "SENT", "currency": "RUB"},
            prev_hash="genesis",
            hash="hash-1",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get(f"/api/v1/client/invoices/{invoice.id}/audit")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["event_type"] == "INVOICE_CREATED"
        assert payload["items"][0]["visibility"] == "PUBLIC"


def test_client_audit_search_external_ref_scoped(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2024, 9, 1),
            period_to=date(2024, 9, 30),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 10, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="diesel", liters=None, unit_price=None, line_amount=3000, tax_amount=0)],
        )
    )
    other_invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(other_client_id),
            period_from=date(2024, 9, 1),
            period_to=date(2024, 9, 30),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2024, 10, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="ai95", liters=None, unit_price=None, line_amount=4000, tax_amount=0)],
        )
    )
    db_session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            event_type="PAYMENT_POSTED",
            entity_type="invoice",
            entity_id=invoice.id,
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            external_refs={"provider": "bank", "external_ref": "BANK-123"},
            after={"amount": 1000, "status": "POSTED"},
            prev_hash="hash-1",
            hash="hash-2",
        )
    )
    db_session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            event_type="PAYMENT_POSTED",
            entity_type="invoice",
            entity_id=other_invoice.id,
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            external_refs={"provider": "bank", "external_ref": "BANK-123"},
            after={"amount": 1000, "status": "POSTED"},
            prev_hash="hash-2",
            hash="hash-3",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get("/api/v1/client/audit/search", params={"external_ref": "BANK-123"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["entity_id"] == invoice.id


def test_client_operations_response_is_sanitized(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    db_session.add(
        Operation(
            operation_id="op-3",
            operation_type=OperationType.AUTH,
            status=OperationStatus.DECLINED,
            merchant_id="m3",
            terminal_id="t3",
            client_id=str(client_id),
            card_id="card-1",
            amount=300,
            currency="RUB",
            reason="AI_RISK_DECLINE_INTERNAL",
            risk_result=RiskResult.HIGH,
            limit_profile_id="lp-1",
            quantity=Decimal("42"),
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        ops = api_client.get("/api/v1/client/operations").json()
        payload = ops["items"][0]
        assert "limit_profile_id" not in payload
        assert "risk_result" not in payload
        assert payload["reason"] == "Операция отклонена службой безопасности"
        assert Decimal(str(payload["quantity"])) == Decimal("42")

        details = api_client.get("/api/v1/client/operations/op-3").json()
        assert "limit_profile_id" not in details
        assert "risk_result" not in details
        assert details["reason"] == "Операция отклонена службой безопасности"


def test_client_reconciliation_request_idempotent_and_audited(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    token = make_jwt(roles=("CLIENT_OWNER",), client_id=str(client_id), extra={"tenant_id": 1})
    payload = {"date_from": "2025-12-01", "date_to": "2025-12-31", "note": "Нужен акт сверки"}
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        first = api_client.post("/api/v1/client/reconciliation-requests", json=payload)
        second = api_client.post("/api/v1/client/reconciliation-requests", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db_session.query(ReconciliationRequest).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "RECONCILIATION_REQUEST_CREATED")
        .filter(AuditLog.visibility == AuditVisibility.PUBLIC)
        .count()
        == 1
    )


def test_document_acknowledgement_idempotent(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2025, 1, 1),
            period_to=date(2025, 1, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            lines=[BillingLineData(product_id="diesel", liters=None, unit_price=None, line_amount=1000, tax_amount=0)],
        )
    )

    token = make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=str(client_id),
        extra={"tenant_id": 1, "email": "client@example.com"},
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        first = api_client.post(f"/api/v1/client/documents/INVOICE_PDF/{invoice.id}/ack")
        second = api_client.post(f"/api/v1/client/documents/INVOICE_PDF/{invoice.id}/ack")

    assert first.status_code == 201
    assert second.status_code == 201
    assert db_session.query(DocumentAcknowledgement).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "DOCUMENT_ACKNOWLEDGED")
        .filter(AuditLog.visibility == AuditVisibility.PUBLIC)
        .count()
        == 1
    )


def test_invoice_messages_abac_and_audit(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2025, 2, 1),
            period_to=date(2025, 2, 28),
            currency="RUB",
            status=InvoiceStatus.SENT,
            lines=[BillingLineData(product_id="ai95", liters=None, unit_price=None, line_amount=2000, tax_amount=0)],
        )
    )
    other_invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(other_client_id),
            period_from=date(2025, 2, 1),
            period_to=date(2025, 2, 28),
            currency="RUB",
            status=InvoiceStatus.SENT,
            lines=[BillingLineData(product_id="ai95", liters=None, unit_price=None, line_amount=2000, tax_amount=0)],
        )
    )

    token = make_jwt(roles=("CLIENT_ACCOUNTANT",), client_id=str(client_id), extra={"tenant_id": 1})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        ok = api_client.post(f"/api/v1/client/invoices/{invoice.id}/messages", json={"message": "Уточните счет"})
        forbidden = api_client.post(
            f"/api/v1/client/invoices/{other_invoice.id}/messages", json={"message": "Чужой счет"}
        )

    assert ok.status_code == 201
    assert forbidden.status_code in (403, 404)
    assert db_session.query(InvoiceMessage).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "INVOICE_MESSAGE_CREATED")
        .filter(AuditLog.visibility == AuditVisibility.PUBLIC)
        .count()
        == 1
    )


def test_client_audit_excludes_internal_events(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id=str(client_id),
            period_from=date(2025, 3, 1),
            period_to=date(2025, 3, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
            issued_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
            lines=[BillingLineData(product_id="diesel", liters=None, unit_price=None, line_amount=1500, tax_amount=0)],
        )
    )

    db_session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            event_type="INVOICE_CREATED",
            entity_type="invoice",
            entity_id=invoice.id,
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            after={"amount": 1500, "status": "SENT"},
            prev_hash="hash-10",
            hash="hash-11",
        )
    )
    db_session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            event_type="ADMIN_MANUAL_FIX",
            entity_type="invoice",
            entity_id=invoice.id,
            action="UPDATE",
            visibility=AuditVisibility.INTERNAL,
            after={"note": "internal"},
            prev_hash="hash-11",
            hash="hash-12",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get(f"/api/v1/client/invoices/{invoice.id}/audit")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["event_type"] == "INVOICE_CREATED"
