from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.marketplace_contracts import Contract
from app.models.marketplace_settlement import MarketplaceSettlementSnapshot
from app.models.settlement_v1 import SettlementItem, SettlementPeriod


@pytest.fixture(autouse=True)
def clean_db():
    tables = [
        AuditLog.__table__,
        Invoice.__table__,
        Contract.__table__,
        SettlementPeriod.__table__,
        SettlementItem.__table__,
        MarketplaceSettlementSnapshot.__table__,
    ]
    for table in reversed(tables):
        table.drop(bind=engine, checkfirst=True)
    for table in tables:
        table.create(bind=engine, checkfirst=True)
    yield
    for table in reversed(tables):
        table.drop(bind=engine, checkfirst=True)


@pytest.fixture(autouse=True)
def _patch_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "ensure_default_refs", lambda _db: None)
    monkeypatch.setattr(main, "register_shadow_hook", lambda: None)
    monkeypatch.setattr(main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _create_invoice(session, *, client_id: str, number: str) -> Invoice:
    invoice = Invoice(
        id=str(uuid4()),
        client_id=client_id,
        number=number,
        period_from=datetime.now(timezone.utc).date(),
        period_to=datetime.now(timezone.utc).date(),
        currency="RUB",
        total_amount=10000,
        total_with_tax=10000,
        amount_due=10000,
        status=InvoiceStatus.SENT,
    )
    session.add(invoice)
    session.commit()
    return invoice
def test_client_portal_invoices_scoped(db_session, make_jwt):
    client_id = str(uuid4())
    other_client_id = str(uuid4())
    _create_invoice(db_session, client_id=client_id, number="INV-CLIENT-1")
    _create_invoice(db_session, client_id=other_client_id, number="INV-CLIENT-2")

    token = make_jwt(roles=("CLIENT_USER",), client_id=client_id, extra={"aud": "neft-client"})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/client/invoices")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 1
        assert payload["items"][0]["invoice_number"] == "INV-CLIENT-1"


def test_partner_portal_contracts_and_settlement_reads_are_mounted_without_writes(make_jwt):
    token = make_jwt(
        roles=("PARTNER_OWNER",),
        extra={"partner_id": str(uuid4()), "subject_type": "partner_user", "aud": "neft-partner"},
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        settlements = api_client.get("/api/partner/settlements")
        assert settlements.status_code == 200
        assert settlements.json()["items"] == []

        details = api_client.get(f"/api/partner/settlements/{uuid4()}")
        assert details.status_code == 404

        confirm = api_client.post(f"/api/partner/settlements/{uuid4()}/confirm")
        assert confirm.status_code == 404

        contracts = api_client.get("/api/partner/contracts")
        assert contracts.status_code == 200
        assert contracts.json()["items"] == []

        core_contracts = api_client.get("/api/core/partner/contracts")
        assert core_contracts.status_code == 200
        assert core_contracts.json()["items"] == []
