from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.finance import CreditNote, InvoicePayment
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.services.audit_service import AuditService, RequestContext
from app.services.key_normalization import normalize_key


@dataclass(frozen=True)
class InternalLedgerHealth:
    broken_transactions_count: int
    missing_postings_count: int


@dataclass(frozen=True)
class InternalLedgerLine:
    account_type: InternalLedgerAccountType
    client_id: str | None
    direction: InternalLedgerEntryDirection
    amount: int
    currency: str
    meta: dict[str, object] | None = None


@dataclass(frozen=True)
class InternalLedgerTransactionResult:
    transaction: InternalLedgerTransaction
    is_replay: bool


class InternalLedgerService:
    GENESIS_BATCH_HASH = "GENESIS_INTERNAL_LEDGER_V1"

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _canonical_json(data: dict[str, object]) -> str:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def entry_hash_for_payload(cls, payload: dict[str, object]) -> str:
        canonical = cls._canonical_json(payload)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _ensure_account(
        self,
        *,
        tenant_id: int,
        client_id: str | None,
        account_type: InternalLedgerAccountType,
        currency: str,
    ) -> InternalLedgerAccount:
        existing = (
            self.db.query(InternalLedgerAccount)
            .filter(InternalLedgerAccount.tenant_id == tenant_id)
            .filter(InternalLedgerAccount.client_id == client_id)
            .filter(InternalLedgerAccount.account_type == account_type)
            .filter(InternalLedgerAccount.currency == currency)
            .one_or_none()
        )
        if existing:
            return existing

        account = InternalLedgerAccount(
            tenant_id=tenant_id,
            client_id=client_id,
            account_type=account_type,
            currency=currency,
        )
        try:
            nested = self.db.begin_nested()
            self.db.add(account)
            self.db.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            existing = (
                self.db.query(InternalLedgerAccount)
                .filter(InternalLedgerAccount.tenant_id == tenant_id)
                .filter(InternalLedgerAccount.client_id == client_id)
                .filter(InternalLedgerAccount.account_type == account_type)
                .filter(InternalLedgerAccount.currency == currency)
                .one_or_none()
            )
            if existing:
                return existing
            raise
        return account

    @staticmethod
    def _canonical_postings_payload(entries: Iterable[InternalLedgerLine]) -> list[dict[str, object]]:
        return [
            {
                "account_type": entry.account_type.value,
                "client_id": entry.client_id,
                "direction": entry.direction.value,
                "amount": int(entry.amount),
                "currency": entry.currency,
                "meta": entry.meta or {},
            }
            for entry in entries
        ]

    def _next_batch_sequence(self, *, tenant_id: int) -> int:
        latest = (
            self.db.query(func.max(InternalLedgerTransaction.batch_sequence))
            .filter(InternalLedgerTransaction.tenant_id == tenant_id)
            .scalar()
        )
        return int(latest or 0) + 1

    def _last_batch_hash(self, *, tenant_id: int) -> str:
        latest = (
            self.db.query(InternalLedgerTransaction.batch_hash)
            .filter(InternalLedgerTransaction.tenant_id == tenant_id)
            .order_by(InternalLedgerTransaction.batch_sequence.desc())
            .limit(1)
            .scalar()
        )
        return latest or self.GENESIS_BATCH_HASH

    @classmethod
    def compute_batch_hash(
        cls,
        *,
        previous_batch_hash: str,
        serialized_postings: list[dict[str, object]],
        total_debit: int,
        total_credit: int,
        timestamp: datetime,
    ) -> str:
        payload = {
            "previous_batch_hash": previous_batch_hash,
            "serialized_postings": serialized_postings,
            "total_debit": int(total_debit),
            "total_credit": int(total_credit),
            "timestamp": timestamp.isoformat(),
        }
        canonical = cls._canonical_json(payload)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get_or_create_transaction(
        self,
        *,
        tenant_id: int,
        transaction_type: InternalLedgerTransactionType,
        external_ref_type: str,
        external_ref_id: str,
        idempotency_key: str,
        total_amount: int | None,
        currency: str | None,
        posted_at: datetime | None,
        meta: dict[str, object] | None = None,
        total_debit: int | None = None,
        total_credit: int | None = None,
        serialized_postings: list[dict[str, object]] | None = None,
    ) -> tuple[InternalLedgerTransaction, bool]:
        idempotency_key = normalize_key(idempotency_key, prefix="ledger:")
        existing = (
            self.db.query(InternalLedgerTransaction)
            .filter(InternalLedgerTransaction.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            if currency and existing.currency and existing.currency != currency:
                raise ValueError("ledger transaction currency mismatch")
            if total_amount is not None and existing.total_amount is not None and existing.total_amount != total_amount:
                raise ValueError("ledger transaction amount mismatch")
            return existing, True

        batch_sequence = self._next_batch_sequence(tenant_id=tenant_id)
        previous_batch_hash = self._last_batch_hash(tenant_id=tenant_id)
        effective_posted_at = posted_at or datetime.now(timezone.utc)
        debit_value = int(total_debit if total_debit is not None else total_amount or 0)
        credit_value = int(total_credit if total_credit is not None else total_amount or 0)

        txn = InternalLedgerTransaction(
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            external_ref_type=external_ref_type,
            external_ref_id=external_ref_id,
            idempotency_key=idempotency_key,
            total_amount=total_amount,
            total_debit=debit_value,
            total_credit=credit_value,
            currency=currency,
            batch_sequence=batch_sequence,
            previous_batch_hash=previous_batch_hash,
            batch_hash=self.compute_batch_hash(
                previous_batch_hash=previous_batch_hash,
                serialized_postings=serialized_postings or [],
                total_debit=debit_value,
                total_credit=credit_value,
                timestamp=effective_posted_at,
            ),
            posted_at=effective_posted_at,
            meta=meta,
        )
        try:
            nested = self.db.begin_nested()
            self.db.add(txn)
            self.db.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            existing = (
                self.db.query(InternalLedgerTransaction)
                .filter(InternalLedgerTransaction.idempotency_key == idempotency_key)
                .one_or_none()
            )
            if existing:
                return existing, True
            raise
        return txn, False

    def _build_entry(
        self,
        *,
        tenant_id: int,
        transaction: InternalLedgerTransaction,
        account: InternalLedgerAccount,
        direction: InternalLedgerEntryDirection,
        amount: int,
        currency: str,
        meta: dict[str, object] | None = None,
    ) -> InternalLedgerEntry:
        payload = {
            "tenant_id": tenant_id,
            "ledger_transaction_id": str(transaction.id),
            "account_id": str(account.id),
            "direction": direction.value,
            "amount": int(amount),
            "currency": currency,
        }
        entry_hash = self.entry_hash_for_payload(payload)
        return InternalLedgerEntry(
            tenant_id=tenant_id,
            ledger_transaction_id=transaction.id,
            account_id=account.id,
            direction=direction,
            amount=int(amount),
            currency=currency,
            entry_hash=entry_hash,
            meta=meta,
        )

    def _post_entries(
        self,
        *,
        transaction: InternalLedgerTransaction,
        entries: Iterable[InternalLedgerEntry],
        expected_currency: str | None = None,
    ) -> None:
        entries_list = list(entries)
        if not entries_list:
            raise ValueError("ledger transaction requires entries")
        currency_set = {entry.currency for entry in entries_list}
        if len(currency_set) != 1:
            raise ValueError("ledger transaction has mixed currencies")
        currency = next(iter(currency_set))
        if expected_currency and currency != expected_currency:
            raise ValueError("ledger transaction currency mismatch")
        if transaction.currency and transaction.currency != currency:
            raise ValueError("ledger transaction currency mismatch")
        debit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.DEBIT)
        credit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.CREDIT)
        if debit_sum != credit_sum:
            raise ValueError("ledger transaction is unbalanced")

        account_map = {
            str(account.id): account
            for account in self.db.query(InternalLedgerAccount)
            .filter(InternalLedgerAccount.id.in_([entry.account_id for entry in entries_list]))
            .all()
        }
        serialized_postings = [
            {
                "account_type": account_map[str(entry.account_id)].account_type.value,
                "client_id": account_map[str(entry.account_id)].client_id,
                "direction": entry.direction.value,
                "amount": int(entry.amount),
                "currency": entry.currency,
                "meta": entry.meta or {},
            }
            for entry in entries_list
        ]
        effective_posted_at = transaction.posted_at or datetime.now(timezone.utc)
        transaction.total_debit = int(debit_sum)
        transaction.total_credit = int(credit_sum)
        transaction.total_amount = int(debit_sum)
        transaction.batch_hash = self.compute_batch_hash(
            previous_batch_hash=transaction.previous_batch_hash,
            serialized_postings=serialized_postings,
            total_debit=int(debit_sum),
            total_credit=int(credit_sum),
            timestamp=effective_posted_at,
        )
        transaction.posted_at = effective_posted_at

        for entry in entries_list:
            self.db.add(entry)
        self._emit_audit_event(transaction=transaction, entries=entries_list, currency=currency, total_amount=debit_sum)

    def _emit_audit_event(
        self,
        *,
        transaction: InternalLedgerTransaction,
        entries: list[InternalLedgerEntry],
        currency: str,
        total_amount: int,
    ) -> None:
        audit = AuditService(self.db)
        entry_payload = [
            {
                "account_id": str(entry.account_id),
                "direction": entry.direction.value,
                "amount": entry.amount,
                "currency": entry.currency,
                "entry_hash": entry.entry_hash,
                "meta": entry.meta,
            }
            for entry in entries
        ]
        audit.audit(
            event_type="ledger_transaction",
            entity_type="internal_ledger_transaction",
            entity_id=str(transaction.id),
            action=transaction.transaction_type.value,
            after={
                "ledger_transaction_id": str(transaction.id),
                "transaction_type": transaction.transaction_type.value,
                "external_ref_type": transaction.external_ref_type,
                "external_ref_id": transaction.external_ref_id,
                "currency": currency,
                "total_amount": total_amount,
                "entries": entry_payload,
            },
            external_refs={
                "external_ref_type": transaction.external_ref_type,
                "external_ref_id": transaction.external_ref_id,
                "ledger_transaction_id": str(transaction.id),
            },
            request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=transaction.tenant_id),
        )

    def post_transaction(
        self,
        *,
        tenant_id: int,
        transaction_type: InternalLedgerTransactionType,
        external_ref_type: str,
        external_ref_id: str,
        idempotency_key: str,
        posted_at: datetime | None,
        meta: dict[str, object] | None,
        entries: Iterable[InternalLedgerLine],
    ) -> InternalLedgerTransactionResult:
        entries_list = list(entries)
        if not entries_list:
            raise ValueError("ledger transaction requires entries")
        currency_set = {entry.currency for entry in entries_list}
        if len(currency_set) != 1:
            raise ValueError("ledger transaction has mixed currencies")
        currency = next(iter(currency_set))
        debit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.DEBIT)
        credit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.CREDIT)
        if debit_sum != credit_sum:
            raise ValueError("ledger transaction is unbalanced")

        transaction, is_replay = self._get_or_create_transaction(
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            external_ref_type=external_ref_type,
            external_ref_id=external_ref_id,
            idempotency_key=idempotency_key,
            total_amount=debit_sum,
            currency=currency,
            posted_at=posted_at,
            meta=meta,
            total_debit=debit_sum,
            total_credit=credit_sum,
            serialized_postings=self._canonical_postings_payload(entries_list),
        )
        if is_replay:
            return InternalLedgerTransactionResult(transaction=transaction, is_replay=True)

        built_entries = []
        for entry in entries_list:
            account = self._ensure_account(
                tenant_id=tenant_id,
                client_id=entry.client_id,
                account_type=entry.account_type,
                currency=entry.currency,
            )
            built_entries.append(
                self._build_entry(
                    tenant_id=tenant_id,
                    transaction=transaction,
                    account=account,
                    direction=entry.direction,
                    amount=entry.amount,
                    currency=entry.currency,
                    meta=entry.meta,
                )
            )

        self._post_entries(transaction=transaction, entries=built_entries, expected_currency=currency)
        return InternalLedgerTransactionResult(transaction=transaction, is_replay=False)

    def post_invoice_issued(self, *, invoice: Invoice, tenant_id: int) -> None:
        if invoice.status not in {
            InvoiceStatus.ISSUED,
            InvoiceStatus.SENT,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
        }:
            return

        currency = invoice.currency
        total_net = int(invoice.total_amount or 0)
        total_tax = int(invoice.tax_amount or 0)
        total_due = int(invoice.total_with_tax or total_net + total_tax)
        posted_at = invoice.issued_at or datetime.now(timezone.utc)

        entries = [
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id=invoice.client_id,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=total_due,
                currency=currency,
                meta={"invoice_id": invoice.id, "kind": "invoice_issued"},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=total_net,
                currency=currency,
                meta={"invoice_id": invoice.id, "kind": "invoice_revenue"},
            ),
        ]

        if total_tax:
            entries.append(
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.TAX_VAT,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=total_tax,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "kind": "invoice_tax"},
                )
            )

        self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.INVOICE_ISSUED,
            external_ref_type="INVOICE",
            external_ref_id=invoice.id,
            idempotency_key=f"invoice:{invoice.id}:issued:v1",
            posted_at=posted_at,
            meta={"invoice_id": invoice.id},
            entries=entries,
        )

    def post_fuel_settlement(
        self,
        *,
        tenant_id: int,
        fuel_transaction_id: str,
        client_id: str,
        amount: int,
        currency: str,
        posted_at: datetime | None = None,
    ) -> InternalLedgerTransaction:
        result = self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.FUEL_SETTLEMENT,
            external_ref_type="FUEL_TRANSACTION",
            external_ref_id=fuel_transaction_id,
            idempotency_key=f"fuel_tx:{fuel_transaction_id}:settlement:v1",
            posted_at=posted_at,
            meta={"fuel_transaction_id": fuel_transaction_id},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id=client_id,
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=amount,
                    currency=currency,
                    meta={"fuel_transaction_id": fuel_transaction_id},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.PROVIDER_PAYABLE,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=amount,
                    currency=currency,
                    meta={"fuel_transaction_id": fuel_transaction_id},
                ),
            ],
        )
        return result.transaction

    def post_fuel_reversal(
        self,
        *,
        tenant_id: int,
        fuel_transaction_id: str,
        client_id: str,
        amount: int,
        currency: str,
        posted_at: datetime | None = None,
    ) -> InternalLedgerTransaction:
        result = self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.FUEL_REVERSAL,
            external_ref_type="FUEL_TRANSACTION",
            external_ref_id=fuel_transaction_id,
            idempotency_key=f"fuel_tx:{fuel_transaction_id}:reversal:v1",
            posted_at=posted_at,
            meta={"fuel_transaction_id": fuel_transaction_id},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.PROVIDER_PAYABLE,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=amount,
                    currency=currency,
                    meta={"fuel_transaction_id": fuel_transaction_id},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id=client_id,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=amount,
                    currency=currency,
                    meta={"fuel_transaction_id": fuel_transaction_id},
                ),
            ],
        )
        return result.transaction

    def post_payment_applied(
        self,
        *,
        invoice: Invoice,
        payment: InvoicePayment,
        tenant_id: int,
    ) -> None:
        currency = payment.currency
        amount = int(payment.amount)
        existing = (
            self.db.query(InternalLedgerTransaction)
            .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
            .filter(InternalLedgerTransaction.external_ref_id == str(payment.id))
            .one_or_none()
        )
        if existing:
            return
        self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.PAYMENT_APPLIED,
            external_ref_type="PAYMENT",
            external_ref_id=str(payment.id),
            idempotency_key=f"payment:{payment.idempotency_key}:applied:v1",
            posted_at=payment.created_at,
            meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_CASH,
                    client_id=invoice.client_id,
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id=invoice.client_id,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
                ),
            ],
        )

    def post_credit_note_applied(
        self,
        *,
        invoice: Invoice,
        credit_note: CreditNote,
        tenant_id: int,
    ) -> None:
        currency = credit_note.currency
        amount = int(credit_note.amount)
        self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.CREDIT_NOTE_APPLIED,
            external_ref_type="CREDIT_NOTE",
            external_ref_id=str(credit_note.id),
            idempotency_key=f"credit_note:{credit_note.id}:applied:v1",
            posted_at=credit_note.created_at,
            meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
                    client_id=None,
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id=invoice.client_id,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
                ),
            ],
        )

    def post_refund_applied(
        self,
        *,
        invoice: Invoice,
        refund: CreditNote,
        tenant_id: int,
    ) -> None:
        currency = refund.currency
        amount = int(refund.amount)
        self.post_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.REFUND_APPLIED,
            external_ref_type="REFUND",
            external_ref_id=str(refund.id),
            idempotency_key=f"refund:{refund.id}:applied:v1",
            posted_at=refund.created_at,
            meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id=invoice.client_id,
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_CASH,
                    client_id=invoice.client_id,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=amount,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
                ),
            ],
        )


def verify_ledger_chain(db: Session, *, tenant_id: int | None = None) -> tuple[bool, str | None]:
    query = db.query(InternalLedgerTransaction).order_by(InternalLedgerTransaction.batch_sequence.asc())
    if tenant_id is not None:
        query = query.filter(InternalLedgerTransaction.tenant_id == tenant_id)
    rows = query.all()
    previous_hash = InternalLedgerService.GENESIS_BATCH_HASH
    expected_seq = 1
    for row in rows:
        if int(row.batch_sequence) != expected_seq:
            return False, f"missing_or_out_of_order_batch:{row.batch_sequence}"
        if row.previous_batch_hash != previous_hash:
            return False, f"previous_batch_hash_mismatch:{row.id}"
        entries = (
            db.query(InternalLedgerEntry, InternalLedgerAccount)
            .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
            .filter(InternalLedgerEntry.ledger_transaction_id == row.id)
            .order_by(InternalLedgerEntry.id.asc())
            .all()
        )
        serialized_postings = [
            {
                "account_type": account.account_type.value,
                "client_id": account.client_id,
                "direction": entry.direction.value,
                "amount": int(entry.amount),
                "currency": entry.currency,
                "meta": entry.meta or {},
            }
            for entry, account in entries
        ]
        debit_sum = sum(int(entry.amount) for entry, _ in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
        credit_sum = sum(int(entry.amount) for entry, _ in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
        expected_hash = InternalLedgerService.compute_batch_hash(
            previous_batch_hash=previous_hash,
            serialized_postings=serialized_postings,
            total_debit=debit_sum,
            total_credit=credit_sum,
            timestamp=row.posted_at or row.created_at,
        )
        if row.batch_hash != expected_hash:
            return False, f"batch_hash_mismatch:{row.id}"
        previous_hash = row.batch_hash
        expected_seq += 1
    return True, None


class InternalLedgerHealthService:
    def __init__(self, db: Session):
        self.db = db

    def check(self) -> InternalLedgerHealth:
        debit_sum = func.coalesce(
            func.sum(
                case(
                    (InternalLedgerEntry.direction == InternalLedgerEntryDirection.DEBIT, InternalLedgerEntry.amount),
                    else_=0,
                )
            ),
            0,
        )
        credit_sum = func.coalesce(
            func.sum(
                case(
                    (InternalLedgerEntry.direction == InternalLedgerEntryDirection.CREDIT, InternalLedgerEntry.amount),
                    else_=0,
                )
            ),
            0,
        )

        broken_subquery = (
            self.db.query(InternalLedgerEntry.ledger_transaction_id)
            .group_by(InternalLedgerEntry.ledger_transaction_id)
            .having(debit_sum != credit_sum)
            .subquery()
        )

        broken_count = self.db.query(func.count()).select_from(broken_subquery).scalar() or 0

        invoice_missing = (
            self.db.query(Invoice.id)
            .outerjoin(
                InternalLedgerTransaction,
                (InternalLedgerTransaction.external_ref_type == "INVOICE")
                & (InternalLedgerTransaction.external_ref_id == Invoice.id),
            )
            .filter(
                Invoice.status.in_(
                    [
                        InvoiceStatus.ISSUED,
                        InvoiceStatus.SENT,
                        InvoiceStatus.PARTIALLY_PAID,
                        InvoiceStatus.PAID,
                    ]
                )
            )
            .filter(InternalLedgerTransaction.id.is_(None))
            .count()
        )

        payment_missing = (
            self.db.query(InvoicePayment.id)
            .outerjoin(
                InternalLedgerTransaction,
                (InternalLedgerTransaction.external_ref_type == "PAYMENT")
                & (InternalLedgerTransaction.external_ref_id == InvoicePayment.id),
            )
            .filter(InternalLedgerTransaction.id.is_(None))
            .count()
        )

        return InternalLedgerHealth(
            broken_transactions_count=int(broken_count),
            missing_postings_count=int(invoice_missing + payment_missing),
        )


__all__ = [
    "InternalLedgerHealth",
    "InternalLedgerHealthService",
    "InternalLedgerLine",
    "InternalLedgerService",
    "InternalLedgerTransactionResult",
]
