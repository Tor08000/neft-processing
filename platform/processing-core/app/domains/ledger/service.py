from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.ledger.enums import EntryStatus, LineDirection, OwnerType
from app.domains.ledger.invariants import LedgerInvariants
from app.domains.ledger.repo import LedgerRepo
from app.domains.ledger.schemas import LedgerEntryOut, LedgerLineOut, LedgerPostRequest


ACCOUNT_TYPES_BY_CODE = {
    "CLIENT_AR": "ASSET",
    "PARTNER_AP": "LIABILITY",
    "PLATFORM_FEES_REVENUE": "REVENUE",
    "CLEARING": "ASSET",
}

OWNER_BY_CODE = {
    "CLIENT_AR": OwnerType.CLIENT.value,
    "PARTNER_AP": OwnerType.PARTNER.value,
    "PLATFORM_FEES_REVENUE": OwnerType.PLATFORM.value,
    "CLEARING": OwnerType.PLATFORM.value,
}


class InternalLedgerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LedgerRepo(db)

    def post_entry(self, request: LedgerPostRequest) -> LedgerEntryOut:
        lines_payload = [
            {
                "account_code": line.account_code,
                "owner_id": str(line.owner_id) if line.owner_id else None,
                "direction": line.direction.value,
                "amount": str(line.amount),
                "currency": line.currency,
                "memo": line.memo,
            }
            for line in request.lines
        ]
        payload_hash = {
            "entry_type": request.entry_type.value,
            "dimensions": request.dimensions,
            "lines": [
                {
                    "direction": line["direction"],
                    "amount": line["amount"],
                    "currency": line["currency"],
                    "memo": line["memo"],
                }
                for line in lines_payload
            ],
        }

        existing = self.repo.get_entry_by_idempotency(request.idempotency_key)
        if existing:
            existing_lines = self.repo.get_lines(str(existing.id))
            existing_payload = {
                "entry_type": existing.entry_type,
                "dimensions": existing.dimensions,
                "lines": [
                    {
                        "direction": line.direction,
                        "amount": str(line.amount),
                        "currency": line.currency,
                        "memo": line.memo,
                    }
                    for line in existing_lines
                ],
            }
            LedgerInvariants.assert_idempotency_match(existing_payload, payload_hash)
            return self.get_entry(str(existing.id))

        LedgerInvariants.assert_positive(lines_payload)
        LedgerInvariants.assert_single_currency(lines_payload)
        LedgerInvariants.assert_balanced(lines_payload)
        LedgerInvariants.assert_required_dimensions(request.entry_type, request.dimensions)

        with self.db.begin_nested():
            entry = self.repo.create_entry(
                {
                    "status": EntryStatus.POSTED.value,
                    "entry_type": request.entry_type.value,
                    "idempotency_key": request.idempotency_key,
                    "correlation_id": request.correlation_id,
                    "source_system": "core-api",
                    "source_event_id": None,
                    "narrative": request.narrative,
                    "dimensions": request.dimensions,
                    "posted_at": datetime.now(timezone.utc),
                }
            )
            line_rows = []
            for idx, line in enumerate(request.lines, start=1):
                owner_type = OWNER_BY_CODE.get(line.account_code, OwnerType.PLATFORM.value)
                account = self.repo.get_or_create_account(
                    account_code=line.account_code,
                    account_type=ACCOUNT_TYPES_BY_CODE.get(line.account_code, "ASSET"),
                    owner_type=owner_type,
                    owner_id=str(line.owner_id) if line.owner_id else None,
                    currency=line.currency,
                )
                line_rows.append(
                    {
                        "entry_id": entry.id,
                        "line_no": idx,
                        "account_id": account.id,
                        "direction": line.direction.value,
                        "amount": line.amount,
                        "currency": line.currency,
                        "memo": line.memo,
                    }
                )
                sign = Decimal("1") if line.direction == LineDirection.DEBIT else Decimal("-1")
                self.repo.upsert_balance(account_id=account.id, currency=line.currency, delta=sign * line.amount)
            self.repo.create_lines(line_rows)

        self.db.flush()
        return self.get_entry(str(entry.id))

    def get_entry(self, entry_id: str) -> LedgerEntryOut:
        entry = self.repo.get_entry(entry_id)
        lines = self.repo.get_lines(entry_id)
        return LedgerEntryOut(
            entry_id=entry.id,
            status=entry.status,
            posted_at=entry.posted_at,
            lines=[
                LedgerLineOut(
                    line_no=line.line_no,
                    account_id=line.account_id,
                    direction=line.direction,
                    amount=line.amount,
                    currency=line.currency,
                )
                for line in lines
            ],
        )

    def get_balance(self, *, account_code: str, owner_id: str | None, currency: str):
        row = self.db.execute(
            text("""
            SELECT b.account_id, b.currency, b.balance
            FROM internal_ledger_v1_account_balances b
            JOIN internal_ledger_v1_accounts a ON a.id = b.account_id
            WHERE a.account_code = :account_code
              AND (:owner_id IS NULL OR a.owner_id = :owner_id)
              AND b.currency = :currency
            LIMIT 1"""),
            {"account_code": account_code, "owner_id": owner_id, "currency": currency},
        ).first()
        if not row:
            return {"account_id": None, "currency": currency, "balance": Decimal("0")}
        return {"account_id": row.account_id, "currency": row.currency, "balance": Decimal(str(row.balance))}
