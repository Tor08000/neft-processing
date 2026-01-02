from __future__ import annotations

from datetime import date, datetime, timezone
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db
from app.db import SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.models.settlement_v1 import SettlementItem, SettlementPayout, SettlementPeriod, SettlementPeriodStatus


@pytest.fixture(autouse=True)
def clean_db():
    tables = [
        AuditLog.__table__,
        Invoice.__table__,
        InvoicePayment.__table__,
        CreditNote.__table__,
        SettlementItem.__table__,
        SettlementPayout.__table__,
        SettlementPeriod.__table__,
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


@pytest.fixture(scope="module", autouse=True)
def _use_sqlite_db():
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite://"
    db.DATABASE_URL = "sqlite://"
    db.reset_engine()
    yield
    if original_url is not None:
        os.environ["DATABASE_URL"] = original_url
        db.DATABASE_URL = original_url
    else:
        os.environ.pop("DATABASE_URL", None)
        db.DATABASE_URL = ""
    db.reset_engine()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_invoices(db_session, client_id: str, other_client_id: str) -> tuple[str, str]:
    own_invoice_id = str(uuid4())
    other_invoice_id = str(uuid4())
    db_session.add(
        Invoice(
            id=own_invoice_id,
            client_id=client_id,
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
        )
    )
    db_session.add(
        Invoice(
            id=other_invoice_id,
            client_id=other_client_id,
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            status=InvoiceStatus.SENT,
        )
    )
    db_session.commit()
    return own_invoice_id, other_invoice_id


def _seed_settlements(db_session, partner_id: str, other_partner_id: str) -> tuple[str, str]:
    own_settlement_id = str(uuid4())
    other_settlement_id = str(uuid4())
    db_session.add(
        SettlementPeriod(
            id=own_settlement_id,
            partner_id=partner_id,
            currency="RUB",
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            status=SettlementPeriodStatus.OPEN,
        )
    )
    db_session.add(
        SettlementPeriod(
            id=other_settlement_id,
            partner_id=other_partner_id,
            currency="RUB",
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            status=SettlementPeriodStatus.OPEN,
        )
    )
    db_session.commit()
    return own_settlement_id, other_settlement_id


def test_client_portal_invoice_access(db_session, make_jwt):
    client_id = str(uuid4())
    other_client_id = str(uuid4())
    own_invoice_id, other_invoice_id = _seed_invoices(db_session, client_id, other_client_id)

    token = make_jwt(roles=("CLIENT_USER",), client_id=client_id)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        invoices = api_client.get("/api/client/invoices")
        assert invoices.status_code == 200
        payload = invoices.json()
        assert payload["total"] == 1

        own_invoice = api_client.get(f"/api/client/invoices/{own_invoice_id}")
        assert own_invoice.status_code == 200

        foreign_invoice = api_client.get(f"/api/client/invoices/{other_invoice_id}")
        assert foreign_invoice.status_code == 403

        bad_token = make_jwt(roles=("USER",), client_id=client_id)
        forbidden = api_client.get(
            "/api/client/invoices",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert forbidden.status_code == 403

    with TestClient(app) as api_client_no_auth:
        missing = api_client_no_auth.get("/api/client/invoices")
        assert missing.status_code == 401


def test_partner_portal_settlements(db_session, make_jwt):
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())
    own_settlement_id, other_settlement_id = _seed_settlements(db_session, partner_id, other_partner_id)

    token = make_jwt(roles=("PARTNER_USER",), extra={"partner_id": partner_id})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        settlements = api_client.get("/api/partner/settlements")
        assert settlements.status_code == 200
        payload = settlements.json()
        assert len(payload["items"]) == 1

        own_details = api_client.get(f"/api/partner/settlements/{own_settlement_id}")
        assert own_details.status_code == 200

        foreign_details = api_client.get(f"/api/partner/settlements/{other_settlement_id}")
        assert foreign_details.status_code == 403

        confirm = api_client.post(f"/api/partner/settlements/{own_settlement_id}/confirm")
        assert confirm.status_code == 403
