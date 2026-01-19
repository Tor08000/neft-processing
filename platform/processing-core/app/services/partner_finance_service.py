from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.partner_core import (
    PartnerOffer,
    PartnerOrder,
    PartnerOrderStatus,
    PartnerProfile,
    PartnerProfileStatus,
)
from app.models.partner_finance import (
    PartnerAccount,
    PartnerAct,
    PartnerDocumentStatus,
    PartnerInvoice,
    PartnerLedgerDirection,
    PartnerLedgerEntry,
    PartnerLedgerEntryType,
    PartnerPayoutRequest,
    PartnerPayoutRequestStatus,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.notifications_v1 import enqueue_notification_message
from app.models.notifications import NotificationChannel, NotificationPriority, NotificationSubjectType
from app.services.partner_legal_service import PartnerLegalService


@dataclass
class BalanceDelta:
    available: Decimal = Decimal("0")
    pending: Decimal = Decimal("0")
    blocked: Decimal = Decimal("0")


class PartnerFinanceService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def get_account(self, *, partner_org_id: str, currency: str) -> PartnerAccount:
        account = (
            self.db.query(PartnerAccount)
            .filter(
                PartnerAccount.org_id == partner_org_id,
                PartnerAccount.currency == currency,
            )
            .one_or_none()
        )
        if account:
            return account
        account = PartnerAccount(org_id=partner_org_id, currency=currency)
        self.db.add(account)
        self.db.flush()
        return account

    def _apply_delta(self, account: PartnerAccount, delta: BalanceDelta) -> None:
        account.balance_available = (account.balance_available or 0) + delta.available
        account.balance_pending = (account.balance_pending or 0) + delta.pending
        account.balance_blocked = (account.balance_blocked or 0) + delta.blocked

    def _ledger_amount(self, amount: Decimal, direction: PartnerLedgerDirection) -> BalanceDelta:
        sign = Decimal("1") if direction == PartnerLedgerDirection.CREDIT else Decimal("-1")
        return BalanceDelta(available=amount * sign)

    def post_entry(
        self,
        *,
        partner_org_id: str,
        entry_type: PartnerLedgerEntryType,
        amount: Decimal,
        currency: str,
        direction: PartnerLedgerDirection,
        order_id: str | None = None,
        meta_json: dict | None = None,
        apply_balance: bool = True,
    ) -> PartnerLedgerEntry:
        entry = PartnerLedgerEntry(
            partner_org_id=partner_org_id,
            order_id=order_id,
            entry_type=entry_type,
            amount=amount,
            currency=currency,
            direction=direction,
            meta_json=meta_json,
        )
        self.db.add(entry)
        if apply_balance and entry_type in {
            PartnerLedgerEntryType.EARNED,
            PartnerLedgerEntryType.SLA_PENALTY,
            PartnerLedgerEntryType.ADJUSTMENT,
        }:
            account = self.get_account(partner_org_id=partner_org_id, currency=currency)
            self._apply_delta(account, self._ledger_amount(amount, direction))
        return entry

    def record_order_earned(self, *, order: PartnerOrder) -> PartnerLedgerEntry | None:
        if order.status != PartnerOrderStatus.DONE:
            return None
        offer = None
        if order.offer_id:
            offer = self.db.query(PartnerOffer).filter(PartnerOffer.id == order.offer_id).one_or_none()
        if not offer or offer.base_price is None:
            return None
        existing = (
            self.db.query(PartnerLedgerEntry)
            .filter(
                PartnerLedgerEntry.order_id == str(order.id),
                PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.EARNED,
            )
            .one_or_none()
        )
        if existing:
            return existing
        currency = offer.currency or "RUB"
        entry = self.post_entry(
            partner_org_id=str(order.partner_org_id),
            order_id=str(order.id),
            entry_type=PartnerLedgerEntryType.EARNED,
            amount=Decimal(offer.base_price),
            currency=currency,
            direction=PartnerLedgerDirection.CREDIT,
            meta_json={"source": "partner_order", "offer_id": str(offer.id)},
        )
        AuditService(self.db).audit(
            event_type="partner_earned",
            entity_type="partner_ledger_entry",
            entity_id=str(entry.id),
            action="partner_earned",
            after={
                "partner_org_id": str(order.partner_org_id),
                "order_id": str(order.id),
                "amount": str(offer.base_price),
                "currency": currency,
            },
            request_ctx=self.request_ctx,
        )
        enqueue_notification_message(
            self.db,
            event_type="partner_earned",
            subject_type=NotificationSubjectType.PARTNER,
            subject_id=str(order.partner_org_id),
            template_code="partner_earned",
            template_vars={
                "order_id": str(order.id),
                "amount": str(offer.base_price),
                "currency": currency,
            },
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"partner_earned:{order.id}",
            channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        )
        return entry

    def record_sla_penalty(
        self,
        *,
        partner_org_id: str,
        order_id: str,
        amount: Decimal,
        currency: str,
        reason: str,
    ) -> PartnerLedgerEntry:
        entry = self.post_entry(
            partner_org_id=partner_org_id,
            order_id=order_id,
            entry_type=PartnerLedgerEntryType.SLA_PENALTY,
            amount=amount,
            currency=currency,
            direction=PartnerLedgerDirection.DEBIT,
            meta_json={"reason": reason},
        )
        AuditService(self.db).audit(
            event_type="partner_sla_penalty",
            entity_type="partner_ledger_entry",
            entity_id=str(entry.id),
            action="partner_sla_penalty",
            after={
                "partner_org_id": partner_org_id,
                "order_id": order_id,
                "amount": str(amount),
                "currency": currency,
                "reason": reason,
            },
            request_ctx=self.request_ctx,
        )
        enqueue_notification_message(
            self.db,
            event_type="partner_sla_penalty",
            subject_type=NotificationSubjectType.PARTNER,
            subject_id=partner_org_id,
            template_code="partner_sla_penalty",
            template_vars={
                "order_id": order_id,
                "amount": str(amount),
                "currency": currency,
                "reason": reason,
            },
            priority=NotificationPriority.HIGH,
            dedupe_key=f"partner_sla_penalty:{order_id}:{reason}",
            channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        )
        return entry

    def _ensure_partner_active(self, partner_org_id: str) -> None:
        try:
            org_id_int = int(partner_org_id)
        except (TypeError, ValueError):
            org_id_int = None
        if org_id_int is None:
            return
        profile = self.db.query(PartnerProfile).filter(PartnerProfile.org_id == org_id_int).one_or_none()
        if profile and profile.status == PartnerProfileStatus.SUSPENDED:
            raise ValueError("partner_suspended")

    def request_payout(
        self,
        *,
        partner_org_id: str,
        amount: Decimal,
        currency: str,
        requested_by: str | None,
    ) -> PartnerPayoutRequest:
        self._ensure_partner_active(partner_org_id)
        PartnerLegalService(self.db, request_ctx=self.request_ctx).ensure_payout_allowed(partner_id=partner_org_id)
        account = self.get_account(partner_org_id=partner_org_id, currency=currency)
        if amount > (account.balance_available or 0):
            raise ValueError("insufficient_balance")
        payout = PartnerPayoutRequest(
            partner_org_id=partner_org_id,
            amount=amount,
            currency=currency,
            status=PartnerPayoutRequestStatus.REQUESTED,
            requested_by=requested_by,
        )
        self.db.add(payout)
        self._apply_delta(account, BalanceDelta(available=-amount, blocked=amount))
        self._record_transfer_ledger(
            partner_org_id=partner_org_id,
            amount=amount,
            currency=currency,
            entry_type=PartnerLedgerEntryType.PAYOUT_REQUESTED,
            meta_json={"payout_request_id": str(payout.id)},
        )
        AuditService(self.db).audit(
            event_type="partner_payout_requested",
            entity_type="partner_payout_request",
            entity_id=str(payout.id),
            action="partner_payout_requested",
            after={
                "partner_org_id": partner_org_id,
                "amount": str(amount),
                "currency": currency,
            },
            request_ctx=self.request_ctx,
        )
        enqueue_notification_message(
            self.db,
            event_type="partner_payout_requested",
            subject_type=NotificationSubjectType.PARTNER,
            subject_id=partner_org_id,
            template_code="partner_payout_requested",
            template_vars={"amount": str(amount), "currency": currency},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"partner_payout_requested:{payout.id}",
            channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        )
        return payout

    def approve_payout(self, *, payout: PartnerPayoutRequest, approved_by: str | None) -> PartnerPayoutRequest:
        if payout.status != PartnerPayoutRequestStatus.REQUESTED:
            raise ValueError("invalid_status")
        payout.status = PartnerPayoutRequestStatus.APPROVED
        payout.approved_by = approved_by
        payout.processed_at = datetime.now(timezone.utc)
        self.post_entry(
            partner_org_id=payout.partner_org_id,
            entry_type=PartnerLedgerEntryType.PAYOUT_APPROVED,
            amount=Decimal("0"),
            currency=payout.currency,
            direction=PartnerLedgerDirection.CREDIT,
            meta_json={"payout_request_id": str(payout.id)},
        )
        AuditService(self.db).audit(
            event_type="partner_payout_approved",
            entity_type="partner_payout_request",
            entity_id=str(payout.id),
            action="partner_payout_approved",
            after={"partner_org_id": payout.partner_org_id, "amount": str(payout.amount)},
            request_ctx=self.request_ctx,
        )
        enqueue_notification_message(
            self.db,
            event_type="partner_payout_approved",
            subject_type=NotificationSubjectType.PARTNER,
            subject_id=payout.partner_org_id,
            template_code="partner_payout_approved",
            template_vars={"amount": str(payout.amount), "currency": payout.currency},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"partner_payout_approved:{payout.id}",
            channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        )
        return payout

    def reject_payout(self, *, payout: PartnerPayoutRequest, approved_by: str | None, reason: str | None = None) -> None:
        if payout.status != PartnerPayoutRequestStatus.REQUESTED:
            raise ValueError("invalid_status")
        payout.status = PartnerPayoutRequestStatus.REJECTED
        payout.approved_by = approved_by
        payout.processed_at = datetime.now(timezone.utc)
        account = self.get_account(partner_org_id=payout.partner_org_id, currency=payout.currency)
        self._apply_delta(account, BalanceDelta(available=payout.amount, blocked=-payout.amount))
        self._record_transfer_ledger(
            partner_org_id=payout.partner_org_id,
            amount=payout.amount,
            currency=payout.currency,
            entry_type=PartnerLedgerEntryType.ADJUSTMENT,
            meta_json={"payout_request_id": str(payout.id), "reason": reason or "rejected"},
        )
        AuditService(self.db).audit(
            event_type="partner_payout_rejected",
            entity_type="partner_payout_request",
            entity_id=str(payout.id),
            action="partner_payout_rejected",
            after={"partner_org_id": payout.partner_org_id, "reason": reason},
            request_ctx=self.request_ctx,
        )

    def mark_paid(self, *, payout: PartnerPayoutRequest) -> PartnerPayoutRequest:
        if payout.status not in {PartnerPayoutRequestStatus.REQUESTED, PartnerPayoutRequestStatus.APPROVED}:
            raise ValueError("invalid_status")
        payout.status = PartnerPayoutRequestStatus.PAID
        payout.processed_at = datetime.now(timezone.utc)
        account = self.get_account(partner_org_id=payout.partner_org_id, currency=payout.currency)
        self._apply_delta(account, BalanceDelta(blocked=-payout.amount))
        self.post_entry(
            partner_org_id=payout.partner_org_id,
            entry_type=PartnerLedgerEntryType.PAYOUT_PAID,
            amount=payout.amount,
            currency=payout.currency,
            direction=PartnerLedgerDirection.DEBIT,
            meta_json={"payout_request_id": str(payout.id)},
            apply_balance=False,
        )
        AuditService(self.db).audit(
            event_type="partner_payout_paid",
            entity_type="partner_payout_request",
            entity_id=str(payout.id),
            action="partner_payout_paid",
            after={"partner_org_id": payout.partner_org_id, "amount": str(payout.amount)},
            request_ctx=self.request_ctx,
        )
        enqueue_notification_message(
            self.db,
            event_type="partner_payout_paid",
            subject_type=NotificationSubjectType.PARTNER,
            subject_id=payout.partner_org_id,
            template_code="partner_payout_paid",
            template_vars={"amount": str(payout.amount), "currency": payout.currency},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"partner_payout_paid:{payout.id}",
            channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        )
        return payout

    def _record_transfer_ledger(
        self,
        *,
        partner_org_id: str,
        amount: Decimal,
        currency: str,
        entry_type: PartnerLedgerEntryType,
        meta_json: dict | None,
    ) -> None:
        self.post_entry(
            partner_org_id=partner_org_id,
            entry_type=entry_type,
            amount=amount,
            currency=currency,
            direction=PartnerLedgerDirection.DEBIT,
            meta_json={**(meta_json or {}), "bucket": "available"},
            apply_balance=False,
        )
        self.post_entry(
            partner_org_id=partner_org_id,
            entry_type=entry_type,
            amount=amount,
            currency=currency,
            direction=PartnerLedgerDirection.CREDIT,
            meta_json={**(meta_json or {}), "bucket": "blocked"},
            apply_balance=False,
        )

    def ensure_monthly_documents(
        self,
        *,
        partner_org_id: str,
        period_from: date,
        period_to: date,
        currency: str,
    ) -> tuple[PartnerInvoice, PartnerAct]:
        legal_service = PartnerLegalService(self.db, request_ctx=self.request_ctx)
        tax_context = legal_service.build_tax_context(
            profile=legal_service.get_profile(partner_id=partner_org_id)
        )
        tax_context_payload = tax_context.to_dict() if tax_context else None
        invoice = (
            self.db.query(PartnerInvoice)
            .filter(
                PartnerInvoice.partner_org_id == partner_org_id,
                PartnerInvoice.period_from == period_from,
                PartnerInvoice.period_to == period_to,
                PartnerInvoice.currency == currency,
            )
            .one_or_none()
        )
        act = (
            self.db.query(PartnerAct)
            .filter(
                PartnerAct.partner_org_id == partner_org_id,
                PartnerAct.period_from == period_from,
                PartnerAct.period_to == period_to,
                PartnerAct.currency == currency,
            )
            .one_or_none()
        )
        if invoice and act:
            return invoice, act

        total = self._calculate_period_earnings(
            partner_org_id=partner_org_id,
            period_from=period_from,
            period_to=period_to,
            currency=currency,
        )
        if invoice is None:
            invoice = PartnerInvoice(
                partner_org_id=partner_org_id,
                period_from=period_from,
                period_to=period_to,
                currency=currency,
                status=PartnerDocumentStatus.DRAFT,
                total_amount=total,
                tax_context=tax_context_payload,
            )
            self.db.add(invoice)
        elif invoice.tax_context is None and tax_context_payload is not None:
            invoice.tax_context = tax_context_payload
        if act is None:
            act = PartnerAct(
                partner_org_id=partner_org_id,
                period_from=period_from,
                period_to=period_to,
                currency=currency,
                status=PartnerDocumentStatus.DRAFT,
                total_amount=total,
                tax_context=tax_context_payload,
            )
            self.db.add(act)
        elif act.tax_context is None and tax_context_payload is not None:
            act.tax_context = tax_context_payload
        return invoice, act

    def _calculate_period_earnings(
        self,
        *,
        partner_org_id: str,
        period_from: date,
        period_to: date,
        currency: str,
    ) -> Decimal:
        entries = (
            self.db.query(PartnerLedgerEntry)
            .filter(
                PartnerLedgerEntry.partner_org_id == partner_org_id,
                PartnerLedgerEntry.currency == currency,
                PartnerLedgerEntry.created_at >= datetime.combine(period_from, datetime.min.time(), tzinfo=timezone.utc),
                PartnerLedgerEntry.created_at
                <= datetime.combine(period_to, datetime.max.time(), tzinfo=timezone.utc),
                PartnerLedgerEntry.entry_type.in_(
                    [PartnerLedgerEntryType.EARNED, PartnerLedgerEntryType.SLA_PENALTY]
                ),
            )
            .all()
        )
        total = Decimal("0")
        for entry in entries:
            sign = Decimal("1") if entry.direction == PartnerLedgerDirection.CREDIT else Decimal("-1")
            total += Decimal(entry.amount) * sign
        return total


__all__ = ["PartnerFinanceService"]
