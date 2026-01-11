from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.integrations.bank.statements.parsers.csv_parser import parse_csv
from app.integrations.bank.statements.parsers.xml_1c_parser import parse_1c_bank_xml
from app.integrations.hub.artifacts import store_integration_file
from app.integrations.bank.statements.reconciliation import run_bank_reconciliation
from app.models.integrations import (
    BankStatement,
    BankStatementStatus,
    BankTransaction,
    IntegrationType,
)
from app.services.audit_service import AuditService, RequestContext

logger = get_logger(__name__)


def _hash_transaction(payload: dict[str, object]) -> str:
    raw = "|".join(
        [
            str(payload.get("date")),
            str(payload.get("amount")),
            str(payload.get("currency")),
            str(payload.get("direction")),
            str(payload.get("counterparty")),
            str(payload.get("purpose")),
            str(payload.get("external_ref")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def import_bank_statement(
    db: Session,
    *,
    bank_code: str,
    period_start: datetime,
    period_end: datetime,
    file_name: str,
    content_type: str,
    payload: bytes,
    actor: RequestContext,
) -> BankStatement:
    content = payload.decode("utf-8")
    if content_type.lower().endswith("xml"):
        transactions = parse_1c_bank_xml(content)
    else:
        transactions = parse_csv(content)

    stored = store_integration_file(
        db,
        file_name=file_name,
        content_type=content_type,
        payload=payload,
    )

    statement = BankStatement(
        bank_code=bank_code,
        period_start=period_start,
        period_end=period_end,
        uploaded_by=actor.actor_id,
        file_id=stored.file_id,
        status=BankStatementStatus.PARSED,
    )
    db.add(statement)
    db.flush()

    for tx in transactions:
        tx_hash = _hash_transaction(tx)
        record = BankTransaction(
            statement_id=statement.id,
            date=tx["date"],
            amount=tx["amount"],
            currency=str(tx["currency"]),
            direction=tx["direction"],
            counterparty=tx.get("counterparty"),
            purpose=tx.get("purpose"),
            external_ref=tx.get("external_ref"),
            hash=tx_hash,
        )
        db.add(record)

    AuditService(db).audit(
        event_type="BANK_STATEMENT_IMPORTED",
        entity_type="bank_statement",
        entity_id=str(statement.id),
        action="imported",
        after={
            "statement_id": str(statement.id),
            "bank_code": bank_code,
            "file_id": stored.file_id,
            "transactions": len(transactions),
        },
        request_ctx=actor,
    )

    logger.info(
        "bank_statement_imported",
        extra={"statement_id": str(statement.id), "bank_code": bank_code},
    )

    run_bank_reconciliation(db, statement_id=str(statement.id), actor=actor)
    return statement


__all__ = ["import_bank_statement"]
