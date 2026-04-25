from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.integrations.bank.statements.importer import import_bank_statement
from app.models.client import Client
from app.models.integrations import (
    BankReconciliationDiff,
    BankReconciliationMatch,
    ReconciliationDiffReason,
)
from app.models.invoice import Invoice, InvoiceLine
from app.models.audit_log import ActorType
from app.services.audit_service import RequestContext
from app.tests._scoped_router_harness import scoped_session_context

from ._path_root import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
FIXTURES = ROOT / "fixtures" / "bank"
if not FIXTURES.exists():
    FIXTURES = find_repo_root(ROOT.parent) / "fixtures" / "bank"

BANK_RECONCILIATION_TEST_TABLES = (
    Base.metadata.tables["clients"],
    Base.metadata.tables["audit_log"],
    Base.metadata.tables["integration_files"],
    Base.metadata.tables["bank_statements"],
    Base.metadata.tables["bank_transactions"],
    Base.metadata.tables["bank_reconciliation_runs"],
    Base.metadata.tables["bank_reconciliation_matches"],
    Base.metadata.tables["bank_reconciliation_diffs"],
    Invoice.__table__,
    InvoiceLine.__table__,
)


@pytest.fixture()
def db_session():
    with scoped_session_context(tables=BANK_RECONCILIATION_TEST_TABLES) as session:
        yield session


def test_bank_statement_reconciliation_e2e(db_session):
    client = Client(id=uuid4(), name="ООО Ромашка", inn="7700000000")
    db_session.add(client)
    db_session.commit()

    period_to = date(2026, 1, 31)
    invoice_main = Invoice(
        id=str(uuid4()),
        client_id=str(client.id),
        number="INV-2026-000123",
        period_from=period_to,
        period_to=period_to,
        currency="RUB",
        total_amount=10000000,
        tax_amount=2000000,
        total_with_tax=12000000,
        amount_paid=0,
        amount_due=12000000,
        issued_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    line = InvoiceLine(
        invoice_id=invoice_main.id,
        operation_id=str(uuid4()),
        product_id="SERVICE-FUEL-CARDS",
        line_amount=invoice_main.total_amount,
        tax_amount=invoice_main.tax_amount,
    )
    db_session.add(invoice_main)
    db_session.add(line)

    invoice_dup_1 = Invoice(
        id=str(uuid4()),
        client_id=str(client.id),
        number="INV-2026-000124",
        period_from=period_to,
        period_to=period_to,
        currency="RUB",
        total_amount=100000,
        tax_amount=0,
        total_with_tax=100000,
        amount_paid=0,
        amount_due=100000,
        issued_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    invoice_dup_2 = Invoice(
        id=str(uuid4()),
        client_id=str(client.id),
        number="INV-2026-000125",
        period_from=period_to,
        period_to=period_to,
        currency="RUB",
        total_amount=100000,
        tax_amount=0,
        total_with_tax=100000,
        amount_paid=0,
        amount_due=100000,
        issued_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db_session.add(invoice_dup_1)
    db_session.add(invoice_dup_2)
    db_session.commit()

    content = (FIXTURES / "statement.csv").read_text(encoding="utf-8")

    actor = RequestContext(actor_type=ActorType.SYSTEM, actor_id="tester")
    statement = import_bank_statement(
        db_session,
        bank_code="TEST",
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        file_name="statement.csv",
        content_type="text/csv",
        payload=content.encode("utf-8"),
        actor=actor,
    )
    db_session.commit()

    matches = db_session.query(BankReconciliationMatch).all()
    diffs = db_session.query(BankReconciliationDiff).all()

    assert statement.id is not None
    assert len(matches) >= 2

    reasons = {diff.reason for diff in diffs}
    assert ReconciliationDiffReason.AMOUNT_MISMATCH in reasons
    assert ReconciliationDiffReason.DATE_MISMATCH in reasons
    assert ReconciliationDiffReason.DUPLICATE_MATCH in reasons
    assert ReconciliationDiffReason.NOT_FOUND in reasons

    matched_invoice_ids = {match.invoice_id for match in matches}
    assert invoice_main.id in matched_invoice_ids
    assert Decimal(str(matches[0].score)) >= Decimal("0.9")
