from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountStatus,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.routers.admin.explain import router as explain_router


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(explain_router, prefix="/api/v1/admin")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_unified_explain_money_section(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        invoice = Invoice(
            id=str(uuid4()),
            client_id="client-1",
            period_from=datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
            period_to=datetime(2025, 1, 31, tzinfo=timezone.utc).date(),
            currency="RUB",
            total_amount=10000,
            tax_amount=2000,
            total_with_tax=12000,
            amount_paid=0,
            amount_due=12000,
            amount_refunded=0,
            status=InvoiceStatus.ISSUED,
        )
        db.add(invoice)
        db.flush()

        account_debit = InternalLedgerAccount(
            tenant_id=1,
            client_id="client-1",
            account_type=InternalLedgerAccountType.CLIENT_AR,
            currency="RUB",
            status=InternalLedgerAccountStatus.ACTIVE,
        )
        account_credit = InternalLedgerAccount(
            tenant_id=1,
            client_id="client-1",
            account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
            currency="RUB",
            status=InternalLedgerAccountStatus.ACTIVE,
        )
        db.add_all([account_debit, account_credit])
        db.flush()

        ledger_tx = InternalLedgerTransaction(
            tenant_id=1,
            transaction_type=InternalLedgerTransactionType.INVOICE_ISSUED,
            external_ref_type="invoice",
            external_ref_id=str(invoice.id),
            idempotency_key=f"invoice:{invoice.id}",
            posted_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )
        db.add(ledger_tx)
        db.flush()

        debit_entry = InternalLedgerEntry(
            tenant_id=1,
            ledger_transaction_id=ledger_tx.id,
            account_id=account_debit.id,
            direction=InternalLedgerEntryDirection.DEBIT,
            amount=12000,
            currency="RUB",
            entry_hash="hash-1",
        )
        credit_entry = InternalLedgerEntry(
            tenant_id=1,
            ledger_transaction_id=ledger_tx.id,
            account_id=account_credit.id,
            direction=InternalLedgerEntryDirection.CREDIT,
            amount=12000,
            currency="RUB",
            entry_hash="hash-2",
        )
        db.add_all([debit_entry, credit_entry])
        db.commit()

    response = client.get(f"/api/v1/admin/explain?invoice_id={invoice.id}&view=ACCOUNTANT")
    assert response.status_code == 200
    payload = response.json()
    money_section = payload["sections"]["money"]
    assert money_section["ledger_postings"][0]["ledger_transaction_id"] == str(ledger_tx.id)