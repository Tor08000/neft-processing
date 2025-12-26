from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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


@dataclass(frozen=True)
class InternalLedgerHealth:
    broken_transactions_count: int
    missing_postings_count: int


class InternalLedgerService:
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
            with self.db.begin_nested():
                self.db.add(account)
                self.db.flush()
        except IntegrityError:
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

    def _get_or_create_transaction(
        self,
        *,
        tenant_id: int,
        transaction_type: InternalLedgerTransactionType,
        external_ref_type: str,
        external_ref_id: str,
        idempotency_key: str,
        posted_at: datetime | None,
        meta: dict[str, object] | None = None,
    ) -> tuple[InternalLedgerTransaction, bool]:
        existing = (
            self.db.query(InternalLedgerTransaction)
            .filter(InternalLedgerTransaction.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            return existing, True

        txn = InternalLedgerTransaction(
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            external_ref_type=external_ref_type,
            external_ref_id=external_ref_id,
            idempotency_key=idempotency_key,
            posted_at=posted_at,
            meta=meta,
        )
        try:
            with self.db.begin_nested():
                self.db.add(txn)
                self.db.flush()
        except IntegrityError:
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

    def _post_entries(self, entries: Iterable[InternalLedgerEntry]) -> None:
        entries_list = list(entries)
        debit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.DEBIT)
        credit_sum = sum(entry.amount for entry in entries_list if entry.direction == InternalLedgerEntryDirection.CREDIT)
        if debit_sum != credit_sum:
            raise ValueError("ledger transaction is unbalanced")
        for entry in entries_list:
            self.db.add(entry)

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

        transaction, is_replay = self._get_or_create_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.INVOICE_ISSUED,
            external_ref_type="INVOICE",
            external_ref_id=invoice.id,
            idempotency_key=f"invoice:{invoice.id}:issued:v1",
            posted_at=posted_at,
            meta={"invoice_id": invoice.id},
        )
        if is_replay:
            return

        account_ar = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_AR,
            currency=currency,
        )
        account_revenue = self._ensure_account(
            tenant_id=tenant_id,
            client_id=None,
            account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
            currency=currency,
        )

        entries = [
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_ar,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=total_due,
                currency=currency,
                meta={"invoice_id": invoice.id, "kind": "invoice_issued"},
            ),
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_revenue,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=total_net,
                currency=currency,
                meta={"invoice_id": invoice.id, "kind": "invoice_revenue"},
            ),
        ]

        if total_tax:
            account_tax = self._ensure_account(
                tenant_id=tenant_id,
                client_id=None,
                account_type=InternalLedgerAccountType.TAX_VAT,
                currency=currency,
            )
            entries.append(
                self._build_entry(
                    tenant_id=tenant_id,
                    transaction=transaction,
                    account=account_tax,
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=total_tax,
                    currency=currency,
                    meta={"invoice_id": invoice.id, "kind": "invoice_tax"},
                )
            )

        self._post_entries(entries)

    def post_payment_applied(
        self,
        *,
        invoice: Invoice,
        payment: InvoicePayment,
        tenant_id: int,
    ) -> None:
        transaction, is_replay = self._get_or_create_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.PAYMENT_APPLIED,
            external_ref_type="PAYMENT",
            external_ref_id=str(payment.id),
            idempotency_key=f"payment:{payment.id}:applied:v1",
            posted_at=payment.created_at,
            meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
        )
        if is_replay:
            return

        currency = payment.currency
        amount = int(payment.amount)

        account_cash = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_CASH,
            currency=currency,
        )
        account_ar = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_AR,
            currency=currency,
        )

        entries = [
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_cash,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
            ),
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_ar,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "payment_id": str(payment.id)},
            ),
        ]
        self._post_entries(entries)

    def post_credit_note_applied(
        self,
        *,
        invoice: Invoice,
        credit_note: CreditNote,
        tenant_id: int,
    ) -> None:
        transaction, is_replay = self._get_or_create_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.CREDIT_NOTE_APPLIED,
            external_ref_type="CREDIT_NOTE",
            external_ref_id=str(credit_note.id),
            idempotency_key=f"credit_note:{credit_note.id}:applied:v1",
            posted_at=credit_note.created_at,
            meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
        )
        if is_replay:
            return

        currency = credit_note.currency
        amount = int(credit_note.amount)

        account_revenue = self._ensure_account(
            tenant_id=tenant_id,
            client_id=None,
            account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
            currency=currency,
        )
        account_ar = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_AR,
            currency=currency,
        )

        entries = [
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_revenue,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
            ),
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_ar,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "credit_note_id": str(credit_note.id)},
            ),
        ]
        self._post_entries(entries)

    def post_refund_applied(
        self,
        *,
        invoice: Invoice,
        refund: CreditNote,
        tenant_id: int,
    ) -> None:
        transaction, is_replay = self._get_or_create_transaction(
            tenant_id=tenant_id,
            transaction_type=InternalLedgerTransactionType.REFUND_APPLIED,
            external_ref_type="REFUND",
            external_ref_id=str(refund.id),
            idempotency_key=f"refund:{refund.id}:applied:v1",
            posted_at=refund.created_at,
            meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
        )
        if is_replay:
            return

        currency = refund.currency
        amount = int(refund.amount)

        account_ar = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_AR,
            currency=currency,
        )
        account_cash = self._ensure_account(
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            account_type=InternalLedgerAccountType.CLIENT_CASH,
            currency=currency,
        )

        entries = [
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_ar,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
            ),
            self._build_entry(
                tenant_id=tenant_id,
                transaction=transaction,
                account=account_cash,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount,
                currency=currency,
                meta={"invoice_id": invoice.id, "refund_id": str(refund.id)},
            ),
        ]
        self._post_entries(entries)


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
    "InternalLedgerService",
]
