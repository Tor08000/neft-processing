from __future__ import annotations

from dataclasses import dataclass

from app.models.risk_types import RiskSubjectType
from app.services.decision.context import DecisionContext
from app.services.decision.versions import DecisionAction


ACTION_TO_SUBJECT: dict[str, RiskSubjectType] = {
    DecisionAction.PAYMENT_AUTHORIZE.value: RiskSubjectType.PAYMENT,
    DecisionAction.PAYMENT_CAPTURE.value: RiskSubjectType.PAYMENT,
    DecisionAction.INVOICE_ISSUE.value: RiskSubjectType.INVOICE,
    DecisionAction.INVOICE_ADJUST.value: RiskSubjectType.INVOICE,
    DecisionAction.CREDIT_NOTE_CREATE.value: RiskSubjectType.INVOICE,
    DecisionAction.PAYOUT_EXPORT.value: RiskSubjectType.PAYOUT,
    DecisionAction.ACCOUNTING_EXPORT.value: RiskSubjectType.EXPORT,
    DecisionAction.DOCUMENT_FINALIZE.value: RiskSubjectType.DOCUMENT,
}


@dataclass(frozen=True)
class RiskV5Context:
    decision_context: DecisionContext
    subject_type: RiskSubjectType
    subject_id: str

    @classmethod
    def from_decision_context(cls, ctx: DecisionContext) -> "RiskV5Context":
        subject_type = _subject_type_from_context(ctx)
        subject_id = _subject_id_from_context(ctx)
        return cls(decision_context=ctx, subject_type=subject_type, subject_id=subject_id)

    @classmethod
    def from_payload(cls, payload: dict) -> "RiskV5Context":
        ctx = DecisionContext(
            tenant_id=payload.get("tenant_id") or 0,
            client_id=payload.get("client_id"),
            action=payload.get("action") or "UNKNOWN",
            actor_type=payload.get("actor_type") or "SYSTEM",
            amount=payload.get("amount"),
            currency=payload.get("currency"),
            payment_method=payload.get("payment_method"),
            invoice_id=payload.get("invoice_id"),
            billing_period_id=payload.get("billing_period_id"),
            age=payload.get("age"),
            history=payload.get("history") or {},
            metadata=payload.get("metadata") or {},
        )
        return cls.from_decision_context(ctx)


def _subject_type_from_context(ctx: DecisionContext) -> RiskSubjectType:
    raw = ctx.metadata.get("subject_type")
    if raw:
        try:
            return RiskSubjectType(raw)
        except ValueError:
            pass
    action_value = ctx.action.value if hasattr(ctx.action, "value") else str(ctx.action)
    return ACTION_TO_SUBJECT.get(action_value, RiskSubjectType.PAYMENT)


def _subject_id_from_context(ctx: DecisionContext) -> str:
    return (
        ctx.metadata.get("subject_id")
        or ctx.invoice_id
        or ctx.billing_period_id
        or ctx.client_id
        or "unknown"
    )


__all__ = ["RiskV5Context"]
