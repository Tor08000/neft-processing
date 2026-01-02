from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.invoice import Invoice, InvoiceStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus


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


def _create_settlement(session, *, partner_id: str, amount: int = 10000) -> SettlementPeriod:
    now = datetime.now(timezone.utc)
    settlement = SettlementPeriod(
        id=str(uuid4()),
        partner_id=partner_id,
        currency="RUB",
        period_start=now - timedelta(days=30),
        period_end=now,
        status=SettlementPeriodStatus.CALCULATED,
        total_gross=amount,
        total_fees=500,
        total_refunds=200,
        net_amount=amount - 700,
    )
    session.add(settlement)
    session.commit()
    return settlement


def test_client_portal_invoices_scoped(db_session, make_jwt):
    client_id = "client-1"
    other_client_id = "client-2"
    _create_invoice(db_session, client_id=client_id, number="INV-CLIENT-1")
    _create_invoice(db_session, client_id=other_client_id, number="INV-CLIENT-2")

    token = make_jwt(roles=("CLIENT_USER",), client_id=client_id)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/client/invoices")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 1
        assert payload["items"][0]["invoice_number"] == "INV-CLIENT-1"


def test_partner_portal_settlements_scoped(db_session, make_jwt):
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())
    _create_settlement(db_session, partner_id=partner_id, amount=12000)
    _create_settlement(db_session, partner_id=other_partner_id, amount=8000)

    token = make_jwt(roles=("PARTNER_OWNER",), extra={"partner_id": partner_id, "subject_type": "partner_user"})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/partner/settlements")
        assert resp.status_code == 200
        payload = resp.json()
        assert len(payload["items"]) == 1
        assert payload["items"][0]["settlement_ref"]


def test_partner_forbidden_access_returns_403(db_session, make_jwt):
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())
    settlement = _create_settlement(db_session, partner_id=other_partner_id)

    token = make_jwt(roles=("PARTNER_OWNER",), extra={"partner_id": partner_id, "subject_type": "partner_user"})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get(f"/api/partner/settlements/{settlement.id}")
        assert resp.status_code == 403
