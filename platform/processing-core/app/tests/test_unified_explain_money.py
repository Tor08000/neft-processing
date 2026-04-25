from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
from app.tests._explain_test_harness import EXPLAIN_UNIFIED_FUEL_TEST_TABLES
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, Session]:
    with scoped_session_context(tables=EXPLAIN_UNIFIED_FUEL_TEST_TABLES) as db:
        with router_client_context(router=explain_router, prefix="/api/v1/admin", db_session=db) as client:
            client.headers.update(admin_auth_headers)
            yield client, db


def test_unified_explain_money_section(admin_client: Tuple[TestClient, Session]):
    client, db = admin_client
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
