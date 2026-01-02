from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.marketplace_contracts import (
    Contract,
    ContractEvent,
    ContractObligation,
    SLAResult,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.audit_signing import AuditSignature, AuditSigningError, AuditSigningService
from app.services.case_event_redaction import redact_deep
from app.services.decision_memory.records import record_decision_memory
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService


@dataclass(frozen=True)
class SLAEvaluationSummary:
    results: list[SLAResult]
    violations: list[SLAResult]


def _canonical_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_metric(metric: str) -> str:
    return (metric or "").strip().lower()


def _order_key(payload: dict) -> str | None:
    for key in ("order_id", "service_id", "delivery_id", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _event_payload(event: ContractEvent) -> dict:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _pair_durations(
    events: Iterable[ContractEvent],
    *,
    start_type: str,
    end_type: str,
) -> list[float]:
    starts: dict[str, datetime] = {}
    durations: list[float] = []
    for event in events:
        payload = _event_payload(event)
        key = _order_key(payload)
        if not key:
            continue
        if event.event_type == start_type:
            starts[key] = event.occurred_at
        if event.event_type == end_type and key in starts:
            durations.append((event.occurred_at - starts[key]).total_seconds())
    return durations


def _metric_delivery_time(events: Iterable[ContractEvent]) -> Decimal:
    durations = _pair_durations(events, start_type="ORDER_PLACED", end_type="DELIVERY_CONFIRMED")
    if not durations:
        return Decimal("0")
    return Decimal(str(sum(durations) / len(durations)))


def _metric_response_time(events: Iterable[ContractEvent]) -> Decimal:
    durations = _pair_durations(events, start_type="ORDER_PLACED", end_type="SERVICE_STARTED")
    if not durations:
        return Decimal("0")
    return Decimal(str(sum(durations) / len(durations)))


def _metric_completion_rate(events: Iterable[ContractEvent]) -> Decimal:
    started = sum(1 for event in events if event.event_type == "SERVICE_STARTED")
    completed = sum(
        1
        for event in events
        if event.event_type in {"SERVICE_COMPLETED", "DELIVERY_CONFIRMED"}
    )
    if started <= 0:
        return Decimal("0")
    return Decimal(str(completed / started))


def _metric_uptime(events: Iterable[ContractEvent], *, period_start: datetime, period_end: datetime) -> Decimal:
    total_seconds = (period_end - period_start).total_seconds()
    if total_seconds <= 0:
        return Decimal("100")
    downtime = Decimal("0")
    for event in events:
        if event.event_type != "INCIDENT_REPORTED":
            continue
        payload = _event_payload(event)
        value = payload.get("downtime_seconds") or payload.get("downtime") or 0
        try:
            downtime += Decimal(str(value))
        except Exception:
            continue
    uptime = max(Decimal("0"), (Decimal(str(total_seconds)) - downtime) / Decimal(str(total_seconds)) * 100)
    return uptime


def _evaluate_obligation(
    obligation: ContractObligation,
    *,
    events: Iterable[ContractEvent],
    period_start: datetime,
    period_end: datetime,
) -> Decimal:
    metric = _normalize_metric(obligation.metric)
    if metric in {"delivery_time", "latency"}:
        return _metric_delivery_time(events)
    if metric in {"response_time"}:
        return _metric_response_time(events)
    if metric in {"completion_rate"}:
        return _metric_completion_rate(events)
    if metric in {"uptime"}:
        return _metric_uptime(events, period_start=period_start, period_end=period_end)
    return Decimal("0")


def _compare(value: Decimal, threshold: Decimal, comparison: str) -> bool:
    if comparison == "<=":
        return value <= threshold
    if comparison == ">=":
        return value >= threshold
    raise ValueError("unsupported_comparison")


def _resolve_client_id(contract: Contract) -> str | None:
    if contract.party_a_type == "client":
        return str(contract.party_a_id)
    if contract.party_b_type == "client":
        return str(contract.party_b_id)
    return None


def _apply_penalty(
    db: Session,
    *,
    contract: Contract,
    obligation: ContractObligation,
    sla_result: SLAResult,
    request_ctx: RequestContext | None,
) -> None:
    tenant_id = int(request_ctx.tenant_id or 0) if request_ctx else 0
    client_id = _resolve_client_id(contract)
    if not client_id:
        return

    amount = Decimal(str(obligation.penalty_value))
    if amount <= 0:
        return
    if amount != amount.to_integral_value():
        raise ValueError("penalty_amount_must_be_integer")
    amount_int = int(amount)

    ledger_service = InternalLedgerService(db)
    penalty_id = new_uuid_str()
    if obligation.penalty_type == "fee":
        debit = InternalLedgerLine(
            account_type=InternalLedgerAccountType.CLIENT_AR,
            client_id=client_id,
            direction=InternalLedgerEntryDirection.DEBIT,
            amount=amount_int,
            currency=contract.currency,
            meta={"sla_result_id": str(sla_result.id), "penalty_type": "fee"},
        )
        credit = InternalLedgerLine(
            account_type=InternalLedgerAccountType.PLATFORM_FEES,
            client_id=None,
            direction=InternalLedgerEntryDirection.CREDIT,
            amount=amount_int,
            currency=contract.currency,
            meta={"sla_result_id": str(sla_result.id), "penalty_type": "fee"},
        )
    else:
        debit = InternalLedgerLine(
            account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
            client_id=None,
            direction=InternalLedgerEntryDirection.DEBIT,
            amount=amount_int,
            currency=contract.currency,
            meta={"sla_result_id": str(sla_result.id), "penalty_type": obligation.penalty_type},
        )
        credit = InternalLedgerLine(
            account_type=InternalLedgerAccountType.CLIENT_AR,
            client_id=client_id,
            direction=InternalLedgerEntryDirection.CREDIT,
            amount=amount_int,
            currency=contract.currency,
            meta={"sla_result_id": str(sla_result.id), "penalty_type": obligation.penalty_type},
        )

    ledger_service.post_transaction(
        tenant_id=tenant_id,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="SLA_PENALTY",
        external_ref_id=penalty_id,
        idempotency_key=f"sla:penalty:{sla_result.id}",
        posted_at=sla_result.created_at,
        meta={
            "contract_id": str(contract.id),
            "obligation_id": str(obligation.id),
            "sla_result_id": str(sla_result.id),
            "penalty_type": obligation.penalty_type,
        },
        entries=[debit, credit],
    )


def create_contract_event(
    db: Session,
    *,
    contract_id: str,
    event_type: str,
    occurred_at: datetime,
    payload: dict,
    request_ctx: RequestContext | None,
) -> ContractEvent:
    redacted_payload = redact_deep(payload, "payload", include_hash=True)
    payload_hash = _hash_payload(
        {
            "contract_id": contract_id,
            "event_type": event_type,
            "occurred_at": occurred_at.isoformat(),
            "payload": redacted_payload,
        }
    )
    signature: AuditSignature | None = None
    signing_service = AuditSigningService()
    try:
        signature = signing_service.sign(bytes.fromhex(payload_hash))
    except AuditSigningError:
        raise

    audit = AuditService(db).audit(
        event_type="CONTRACT_EVENT_RECORDED",
        entity_type="contract_event",
        entity_id=contract_id,
        action=event_type,
        after={"event_type": event_type, "occurred_at": occurred_at.isoformat(), "payload": redacted_payload},
        request_ctx=request_ctx,
    )

    event = ContractEvent(
        id=new_uuid_str(),
        contract_id=contract_id,
        event_type=event_type,
        occurred_at=occurred_at,
        payload=redacted_payload,
        hash=payload_hash,
        signature=signature.signature if signature else None,
        signature_alg=signature.alg if signature else None,
        signing_key_id=signature.key_id if signature else None,
        signed_at=signature.signed_at if signature else None,
        audit_event_id=audit.id,
    )
    db.add(event)
    return event


def evaluate_sla(
    db: Session,
    *,
    contract_id: str,
    period_start: datetime,
    period_end: datetime,
    request_ctx: RequestContext | None,
) -> SLAEvaluationSummary:
    contract = db.query(Contract).filter(Contract.id == contract_id).one()
    obligations = (
        db.query(ContractObligation)
        .filter(ContractObligation.contract_id == contract_id)
        .all()
    )
    events = (
        db.query(ContractEvent)
        .filter(ContractEvent.contract_id == contract_id)
        .filter(ContractEvent.occurred_at >= period_start)
        .filter(ContractEvent.occurred_at <= period_end)
        .order_by(ContractEvent.occurred_at.asc())
        .all()
    )

    results: list[SLAResult] = []
    violations: list[SLAResult] = []
    for obligation in obligations:
        measured_value = _evaluate_obligation(
            obligation,
            events=events,
            period_start=period_start,
            period_end=period_end,
        )
        threshold = Decimal(str(obligation.threshold))
        try:
            ok = _compare(measured_value, threshold, obligation.comparison)
        except ValueError:
            ok = False
        status = "OK" if ok else "VIOLATION"

        audit = AuditService(db).audit(
            event_type="SLA_EVALUATED",
            entity_type="sla_result",
            entity_id=str(obligation.id),
            action="SLA_EVALUATED",
            after={
                "contract_id": str(contract_id),
                "obligation_id": str(obligation.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "measured_value": str(measured_value),
                "status": status,
            },
            request_ctx=request_ctx,
        )

        created_at = datetime.now(timezone.utc)
        result = SLAResult(
            id=new_uuid_str(),
            contract_id=contract_id,
            obligation_id=obligation.id,
            period_start=period_start,
            period_end=period_end,
            measured_value=measured_value,
            status=status,
            created_at=created_at,
            audit_event_id=audit.id,
        )
        db.add(result)
        results.append(result)

        record_decision_memory(
            db,
            case_id=None,
            decision_type="sla_evaluation",
            decision_ref_id=result.id,
            decision_at=created_at,
            decided_by_user_id=request_ctx.actor_id if request_ctx else None,
            context_snapshot={
                "contract_id": str(contract_id),
                "obligation_id": str(obligation.id),
                "status": status,
                "measured_value": str(measured_value),
            },
            rationale=None,
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )

        if status == "VIOLATION":
            violation_audit = AuditService(db).audit(
                event_type="SLA_VIOLATION",
                entity_type="sla_result",
                entity_id=str(result.id),
                action="SLA_VIOLATION",
                after={
                    "contract_id": str(contract_id),
                    "obligation_id": str(obligation.id),
                    "measured_value": str(measured_value),
                    "threshold": str(threshold),
                },
                request_ctx=request_ctx,
            )
            record_decision_memory(
                db,
                case_id=None,
                decision_type="sla_violation",
                decision_ref_id=result.id,
                decision_at=created_at,
                decided_by_user_id=request_ctx.actor_id if request_ctx else None,
                context_snapshot={
                    "contract_id": str(contract_id),
                    "obligation_id": str(obligation.id),
                    "measured_value": str(measured_value),
                },
                rationale=f"SLA breach on contract {contract.contract_number}",
                score_snapshot=None,
                mastery_snapshot=None,
                audit_event_id=str(violation_audit.id),
            )
            _apply_penalty(
                db,
                contract=contract,
                obligation=obligation,
                sla_result=result,
                request_ctx=request_ctx,
            )
            penalty_audit = AuditService(db).audit(
                event_type="PENALTY_APPLIED",
                entity_type="sla_result",
                entity_id=str(result.id),
                action="PENALTY_APPLIED",
                after={
                    "contract_id": str(contract_id),
                    "obligation_id": str(obligation.id),
                    "penalty_type": obligation.penalty_type,
                    "penalty_value": str(obligation.penalty_value),
                },
                request_ctx=request_ctx,
            )
            record_decision_memory(
                db,
                case_id=None,
                decision_type="sla_penalty",
                decision_ref_id=result.id,
                decision_at=created_at,
                decided_by_user_id=request_ctx.actor_id if request_ctx else None,
                context_snapshot={
                    "contract_id": str(contract_id),
                    "obligation_id": str(obligation.id),
                    "penalty_type": obligation.penalty_type,
                },
                rationale=f"Penalty applied for SLA breach on contract {contract.contract_number}",
                score_snapshot=None,
                mastery_snapshot=None,
                audit_event_id=str(penalty_audit.id),
            )
            violations.append(result)

    return SLAEvaluationSummary(results=results, violations=violations)


__all__ = [
    "SLAEvaluationSummary",
    "create_contract_event",
    "evaluate_sla",
]
