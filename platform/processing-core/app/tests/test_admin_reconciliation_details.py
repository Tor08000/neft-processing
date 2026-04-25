from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationLink,
    ReconciliationLinkDirection,
    ReconciliationLinkStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService

from ._money_router_harness import (
    ADMIN_RECONCILIATION_TEST_TABLES,
    admin_reconciliation_client_context,
    money_session_context,
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=ADMIN_RECONCILIATION_TEST_TABLES) as db:
        yield db


@pytest.fixture
def reconciliation_client(session: Session) -> TestClient:
    with admin_reconciliation_client_context(db_session=session) as api_client:
        yield api_client


def _audit_ctx() -> RequestContext:
    return RequestContext(actor_type=ActorType.SYSTEM, actor_id="test-suite")


def _seed_statement(session: Session, *, statement_id: str, now: datetime) -> ExternalStatement:
    statement = ExternalStatement(
        id=statement_id,
        provider="bank_stub",
        period_start=now - timedelta(days=31),
        period_end=now - timedelta(days=1),
        currency="RUB",
        total_in=Decimal("1000.0000"),
        total_out=Decimal("250.0000"),
        closing_balance=Decimal("750.0000"),
        lines=[
            {"id": "line-1", "ref": "payment-1", "amount": "500.00", "direction": "IN"},
            {"id": "line-2", "ref": "payment-2", "amount": "250.00", "direction": "OUT"},
        ],
        source_hash=f"hash-{statement_id}",
        created_at=now - timedelta(hours=2),
    )
    session.add(statement)
    return statement


def _seed_run(session: Session, *, run_id: str, statement_id: str, now: datetime) -> ReconciliationRun:
    run = ReconciliationRun(
        id=run_id,
        scope=ReconciliationScope.EXTERNAL,
        provider="bank_stub",
        period_start=now - timedelta(days=31),
        period_end=now - timedelta(days=1),
        status=ReconciliationRunStatus.COMPLETED,
        created_at=now - timedelta(hours=1),
        created_by_user_id=str(uuid4()),
        summary={
            "mismatches_found": 2,
            "total_delta_abs": "25.0000",
            "statement_id": statement_id,
            "links": {"matched": 1, "mismatched": 1, "pending": 0},
            "links_matched": 1,
            "links_mismatched": 1,
            "links_pending": 0,
            "internal_totals": {
                "total_in": "1000.0000",
                "total_out": "250.0000",
                "closing_balance": "725.0000",
            },
        },
    )
    session.add(run)
    return run


def _seed_adjustment(
    session: Session,
    *,
    discrepancy: ReconciliationDiscrepancy,
    now: datetime,
) -> str:
    service = InternalLedgerService(session)
    result = service.post_transaction(
        tenant_id=1,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="RECONCILIATION_DISCREPANCY",
        external_ref_id=str(discrepancy.id),
        idempotency_key=f"recon-adjustment:{discrepancy.id}",
        posted_at=now,
        meta={"discrepancy_id": str(discrepancy.id)},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id="client-1",
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=250,
                currency=discrepancy.currency,
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SUSPENSE,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=250,
                currency=discrepancy.currency,
            ),
        ],
    )
    discrepancy.status = ReconciliationDiscrepancyStatus.RESOLVED
    discrepancy.resolution = {
        "adjustment_tx_id": str(result.transaction.id),
        "resolved_at": now.isoformat(),
        "note": "operator adjustment",
    }
    AuditService(session).audit(
        event_type="DISCREPANCY_RESOLVED",
        entity_type="reconciliation_discrepancy",
        entity_id=str(discrepancy.id),
        action="resolved",
        after={"discrepancy_id": str(discrepancy.id), "adjustment_tx_id": str(result.transaction.id)},
        request_ctx=_audit_ctx(),
    )
    return str(result.transaction.id)


def test_admin_reconciliation_run_detail_returns_statement_link_counts_and_timeline(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    run = _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    session.add(
        ReconciliationLink(
            id=str(uuid4()),
            entity_type="invoice",
            entity_id=str(uuid4()),
            provider="bank_stub",
            currency="RUB",
            expected_amount=Decimal("500.0000"),
            direction=ReconciliationLinkDirection.IN,
            expected_at=now - timedelta(days=2),
            match_key="payment-1",
            status=ReconciliationLinkStatus.MATCHED,
            run_id=run.id,
            created_at=now - timedelta(days=2),
        )
    )
    session.add(
        ReconciliationLink(
            id=str(uuid4()),
            entity_type="invoice",
            entity_id=str(uuid4()),
            provider="bank_stub",
            currency="RUB",
            expected_amount=Decimal("250.0000"),
            direction=ReconciliationLinkDirection.OUT,
            expected_at=now - timedelta(days=2),
            match_key="payment-2",
            status=ReconciliationLinkStatus.MISMATCHED,
            run_id=run.id,
            created_at=now - timedelta(days=2),
        )
    )

    AuditService(session).audit(
        event_type="RECONCILIATION_RUN_COMPLETED",
        entity_type="reconciliation_run",
        entity_id=run_id,
        action="completed",
        after={"run_id": run_id, "statement_id": statement_id},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["statement"]["id"] == statement_id
    assert payload["link_counts"] == {"matched": 1, "mismatched": 1, "pending": 0}
    assert payload["timeline"][0]["event_type"] == "RECONCILIATION_RUN_COMPLETED"


def test_admin_reconciliation_run_links_return_review_parity(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())
    entity_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    session.add(
        ReconciliationLink(
            id=str(uuid4()),
            entity_type="invoice",
            entity_id=entity_id,
            provider="bank_stub",
            currency="RUB",
            expected_amount=Decimal("250.0000"),
            direction=ReconciliationLinkDirection.OUT,
            expected_at=now - timedelta(days=2),
            match_key="payment-2",
            status=ReconciliationLinkStatus.MISMATCHED,
            run_id=run_id,
            created_at=now - timedelta(days=2),
        )
    )
    discrepancy_id = str(uuid4())
    session.add(
        ReconciliationDiscrepancy(
            id=discrepancy_id,
            run_id=run_id,
            ledger_account_id=None,
            currency="RUB",
            discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
            internal_amount=Decimal("250.0000"),
            external_amount=Decimal("240.0000"),
            delta=Decimal("-10.0000"),
            details={"entity_type": "invoice", "entity_id": entity_id, "statement_id": statement_id},
            status=ReconciliationDiscrepancyStatus.OPEN,
            created_at=now - timedelta(hours=1),
        )
    )
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}/links")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["links"]) == 1
    assert payload["links"][0]["entity_type"] == "invoice"
    assert payload["links"][0]["review_status"] == "open"
    assert payload["links"][0]["discrepancy_ids"] == [discrepancy_id]


def test_admin_reconciliation_statement_detail_returns_explain_and_timeline(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())
    link_id = str(uuid4())

    statement = _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    session.add(
        ReconciliationLink(
            id=link_id,
            entity_type="invoice",
            entity_id=str(uuid4()),
            provider=statement.provider,
            currency=statement.currency,
            expected_amount=Decimal("250.0000"),
            direction=ReconciliationLinkDirection.OUT,
            expected_at=now - timedelta(days=2),
            match_key="payment-2",
            status=ReconciliationLinkStatus.MISMATCHED,
            run_id=run_id,
            created_at=now - timedelta(days=2),
        )
    )
    balance_discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency=statement.currency,
        discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
        internal_amount=Decimal("725.0000"),
        external_amount=Decimal("750.0000"),
        delta=Decimal("25.0000"),
        details={"kind": "closing_balance", "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(hours=1),
    )
    session.add(balance_discrepancy)
    session.add(
        ReconciliationDiscrepancy(
            id=str(uuid4()),
            run_id=run_id,
            ledger_account_id=None,
            currency=statement.currency,
            discrepancy_type=ReconciliationDiscrepancyType.UNMATCHED_EXTERNAL,
            internal_amount=None,
            external_amount=None,
            delta=None,
            details={"statement_id": statement_id, "ref": "payment-x"},
            status=ReconciliationDiscrepancyStatus.OPEN,
            created_at=now - timedelta(hours=1),
        )
    )
    resolved_discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency=statement.currency,
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("240.0000"),
        delta=Decimal("-10.0000"),
        details={"entity_type": "invoice", "entity_id": str(uuid4()), "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=50),
    )
    session.add(resolved_discrepancy)
    adjustment_tx_id = _seed_adjustment(session, discrepancy=resolved_discrepancy, now=now - timedelta(minutes=20))
    AuditService(session).audit(
        event_type="EXTERNAL_STATEMENT_UPLOADED",
        entity_type="external_statement",
        entity_id=statement_id,
        action="created",
        after={"statement_id": statement_id, "provider": statement.provider},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/external/statements/{statement_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == statement_id
    assert payload["explain"]["related_run_id"] == run_id
    assert payload["explain"]["matched_links"] == 0
    assert payload["explain"]["mismatched_links"] == 1
    assert payload["explain"]["unmatched_external"] == 1
    assert payload["explain"]["open_discrepancies"] == 2
    assert payload["explain"]["resolved_discrepancies"] == 1
    assert payload["explain"]["adjusted_discrepancies"] == 1
    checks = {item["kind"]: item for item in payload["explain"]["total_checks"]}
    assert checks["closing_balance"]["status"] == "mismatch"
    assert checks["closing_balance"]["delta"] == "25.0000"
    assert adjustment_tx_id
    assert payload["timeline"][0]["event_type"] == "EXTERNAL_STATEMENT_UPLOADED"


def test_admin_reconciliation_discrepancies_return_timeline_and_adjustment_explain(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("500.0000"),
        delta=Decimal("250.0000"),
        details={"entity_type": "invoice", "entity_id": str(uuid4()), "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    session.add(discrepancy)
    adjustment_tx_id = _seed_adjustment(session, discrepancy=discrepancy, now=now - timedelta(minutes=10))
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}/discrepancies")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["discrepancies"]) == 1
    item = payload["discrepancies"][0]
    assert item["timeline"][0]["event_type"] == "DISCREPANCY_RESOLVED"
    assert item["adjustment_explain"]["adjustment_tx_id"] == adjustment_tx_id
    assert item["adjustment_explain"]["tenant_id"] == 1
    assert len(item["adjustment_explain"]["entries"]) == 2
    assert {entry["account_type"] for entry in item["adjustment_explain"]["entries"]} == {"CLIENT_AR", "SUSPENSE"}


def test_admin_reconciliation_discrepancy_detail_returns_full_timeline_and_richer_adjustment_explain(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("500.0000"),
        delta=Decimal("250.0000"),
        details={"entity_type": "invoice", "entity_id": str(uuid4()), "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    session.add(discrepancy)
    adjustment_tx_id = _seed_adjustment(session, discrepancy=discrepancy, now=now - timedelta(minutes=10))
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/discrepancies/{discrepancy.id}")

    assert response.status_code == 200
    payload = response.json()["discrepancy"]
    assert payload["id"] == str(discrepancy.id)
    assert payload["timeline"][0]["event_type"] == "DISCREPANCY_RESOLVED"
    assert payload["timeline"][-1]["event_type"] == "DISCREPANCY_DETECTED"
    explain = payload["adjustment_explain"]
    assert explain["adjustment_tx_id"] == adjustment_tx_id
    assert explain["transaction_type"] == "ADJUSTMENT"
    assert explain["external_ref_type"] == "RECONCILIATION_DISCREPANCY"
    assert explain["external_ref_id"] == str(discrepancy.id)
    assert explain["meta"]["discrepancy_id"] == str(discrepancy.id)
    assert explain["audit_events"][0]["entity_type"] == "internal_ledger_transaction"
    assert {entry["account_type"] for entry in explain["entries"]} == {"CLIENT_AR", "SUSPENSE"}


def test_admin_reconciliation_run_export_returns_canonical_payload(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())
    entity_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)

    session.add(
        ReconciliationLink(
            id=str(uuid4()),
            entity_type="invoice",
            entity_id=entity_id,
            provider="bank_stub",
            currency="RUB",
            expected_amount=Decimal("250.0000"),
            direction=ReconciliationLinkDirection.OUT,
            expected_at=now - timedelta(days=2),
            match_key="payment-2",
            status=ReconciliationLinkStatus.MISMATCHED,
            run_id=run_id,
            created_at=now - timedelta(days=2),
        )
    )
    discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("500.0000"),
        delta=Decimal("250.0000"),
        details={"entity_type": "invoice", "entity_id": entity_id, "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    session.add(discrepancy)
    adjustment_tx_id = _seed_adjustment(session, discrepancy=discrepancy, now=now - timedelta(minutes=10))
    AuditService(session).audit(
        event_type="RECONCILIATION_RUN_COMPLETED",
        entity_type="reconciliation_run",
        entity_id=run_id,
        action="completed",
        after={"run_id": run_id, "statement_id": statement_id},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == run_id
    assert payload["run"]["statement"]["id"] == statement_id
    assert payload["links"][0]["entity_id"] == entity_id
    assert payload["discrepancies"][0]["timeline"][0]["event_type"] == "DISCREPANCY_RESOLVED"
    assert payload["discrepancies"][0]["timeline"][-1]["event_type"] == "DISCREPANCY_DETECTED"
    assert payload["discrepancies"][0]["adjustment_explain"]["adjustment_tx_id"] == adjustment_tx_id
    assert payload["discrepancies"][0]["adjustment_explain"]["transaction_type"] == "ADJUSTMENT"
    assert payload["exported_at"]


def test_admin_reconciliation_run_export_supports_json_and_csv_downloads(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)
    discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
        internal_amount=Decimal("725.0000"),
        external_amount=Decimal("750.0000"),
        delta=Decimal("25.0000"),
        details={"kind": "closing_balance", "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    session.add(discrepancy)
    session.commit()

    json_response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}/export?format=json")
    csv_response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/runs/{run_id}/export?format=csv")

    assert json_response.status_code == 200
    assert json_response.headers["content-disposition"] == f'attachment; filename="reconciliation_run_{run_id}.json"'
    assert json_response.json()["run"]["id"] == run_id
    assert json_response.json()["discrepancies"][0]["id"] == str(discrepancy.id)

    assert csv_response.status_code == 200
    assert csv_response.headers["content-disposition"] == f'attachment; filename="reconciliation_run_{run_id}.csv"'
    assert "text/csv" in csv_response.headers["content-type"]
    body = csv_response.text
    assert "run_id,scope,provider,period_start,period_end,status,statement_id" in body
    assert str(discrepancy.id) in body


def test_admin_reconciliation_statement_discrepancies_return_drilldown_ready_payload(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)
    discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("500.0000"),
        delta=Decimal("250.0000"),
        details={"entity_type": "invoice", "entity_id": str(uuid4()), "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    session.add(discrepancy)
    _seed_adjustment(session, discrepancy=discrepancy, now=now - timedelta(minutes=10))
    session.commit()

    response = reconciliation_client.get(f"/api/core/v1/admin/reconciliation/external/statements/{statement_id}/discrepancies")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["discrepancies"]) == 1
    item = payload["discrepancies"][0]
    assert item["run_id"] == run_id
    assert item["timeline"][0]["event_type"] == "DISCREPANCY_RESOLVED"
    assert item["adjustment_explain"]["transaction_type"] == "ADJUSTMENT"


def test_admin_reconciliation_run_export_supports_filtered_discrepancy_only_csv(
    reconciliation_client: TestClient,
    session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    statement_id = str(uuid4())
    run_id = str(uuid4())

    _seed_statement(session, statement_id=statement_id, now=now)
    _seed_run(session, run_id=run_id, statement_id=statement_id, now=now)
    resolved_discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
        internal_amount=Decimal("250.0000"),
        external_amount=Decimal("500.0000"),
        delta=Decimal("250.0000"),
        details={"entity_type": "invoice", "entity_id": str(uuid4()), "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=30),
    )
    open_discrepancy = ReconciliationDiscrepancy(
        id=str(uuid4()),
        run_id=run_id,
        ledger_account_id=None,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
        internal_amount=Decimal("725.0000"),
        external_amount=Decimal("750.0000"),
        delta=Decimal("25.0000"),
        details={"kind": "closing_balance", "statement_id": statement_id},
        status=ReconciliationDiscrepancyStatus.OPEN,
        created_at=now - timedelta(minutes=20),
    )
    session.add(resolved_discrepancy)
    session.add(open_discrepancy)
    _seed_adjustment(session, discrepancy=resolved_discrepancy, now=now - timedelta(minutes=10))
    session.commit()

    response = reconciliation_client.get(
        "/api/core/v1/admin/reconciliation/runs/"
        f"{run_id}/export?format=csv&export_scope=discrepancies&discrepancy_status=resolved&discrepancy_type=MISMATCHED_AMOUNT"
    )

    assert response.status_code == 200
    body = response.text
    assert str(resolved_discrepancy.id) in body
    assert str(open_discrepancy.id) not in body
    assert f",{statement_id}," in body
