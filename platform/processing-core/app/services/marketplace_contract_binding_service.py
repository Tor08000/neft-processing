from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.marketplace_contracts import Contract, ContractStatus, ContractVersion
from app.models.marketplace_order_sla import MarketplaceOrderContractLink
from app.services.audit_service import AuditService, RequestContext
from app.services.decision_memory.records import record_decision_memory


def _resolve_contract_version(db: Session, *, contract_id: str) -> int | None:
    version = (
        db.query(func.max(ContractVersion.version))
        .filter(ContractVersion.contract_id == contract_id)
        .scalar()
    )
    return int(version) if version is not None else None


def _match_contract(db: Session, *, client_id: str, partner_id: str) -> Contract | None:
    contract = (
        db.query(Contract)
        .filter(Contract.status == ContractStatus.ACTIVE.value)
        .filter(func.lower(Contract.contract_type).in_(["marketplace", "service"]))
        .filter(
            or_(
                and_(Contract.party_a_id == client_id, Contract.party_b_id == partner_id),
                and_(Contract.party_a_id == partner_id, Contract.party_b_id == client_id),
            )
        )
        .order_by(Contract.effective_from.desc(), Contract.created_at.desc())
        .first()
    )
    return contract


def bind_contract_for_order(
    db: Session,
    *,
    order_id: str,
    client_id: str | None,
    partner_id: str | None,
    request_ctx: RequestContext | None = None,
) -> str | None:
    existing = (
        db.query(MarketplaceOrderContractLink)
        .filter(MarketplaceOrderContractLink.order_id == order_id)
        .one_or_none()
    )
    if existing:
        return str(existing.contract_id)

    if not client_id or not partner_id:
        audit = AuditService(db).audit(
            event_type="ORDER_NO_CONTRACT",
            entity_type="marketplace_order",
            entity_id=order_id,
            action="ORDER_NO_CONTRACT",
            after={"order_id": order_id, "client_id": client_id, "partner_id": partner_id},
            request_ctx=request_ctx,
        )
        record_decision_memory(
            db,
            case_id=None,
            decision_type="order_contract_binding",
            decision_ref_id=order_id,
            decision_at=datetime.now(timezone.utc),
            decided_by_user_id=request_ctx.actor_id if request_ctx else None,
            context_snapshot={"order_id": order_id, "reason": "missing_party_context"},
            rationale="No contract binding because order party context is missing.",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )
        return None

    contract = _match_contract(db, client_id=client_id, partner_id=partner_id)
    if not contract:
        audit = AuditService(db).audit(
            event_type="ORDER_NO_CONTRACT",
            entity_type="marketplace_order",
            entity_id=order_id,
            action="ORDER_NO_CONTRACT",
            after={"order_id": order_id, "client_id": client_id, "partner_id": partner_id},
            request_ctx=request_ctx,
        )
        record_decision_memory(
            db,
            case_id=None,
            decision_type="order_contract_binding",
            decision_ref_id=order_id,
            decision_at=datetime.now(timezone.utc),
            decided_by_user_id=request_ctx.actor_id if request_ctx else None,
            context_snapshot={"order_id": order_id, "client_id": client_id, "partner_id": partner_id},
            rationale="No active marketplace contract found for order parties.",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )
        return None

    version = _resolve_contract_version(db, contract_id=str(contract.id))
    audit = AuditService(db).audit(
        event_type="ORDER_CONTRACT_BOUND",
        entity_type="marketplace_order",
        entity_id=order_id,
        action="ORDER_CONTRACT_BOUND",
        after={
            "order_id": order_id,
            "contract_id": str(contract.id),
            "sla_policy_version": version,
        },
        request_ctx=request_ctx,
    )
    link = MarketplaceOrderContractLink(
        order_id=order_id,
        contract_id=str(contract.id),
        sla_policy_version=version,
        audit_event_id=audit.id,
    )
    db.add(link)
    record_decision_memory(
        db,
        case_id=None,
        decision_type="order_contract_binding",
        decision_ref_id=order_id,
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=request_ctx.actor_id if request_ctx else None,
        context_snapshot={
            "order_id": order_id,
            "contract_id": str(contract.id),
            "sla_policy_version": version,
        },
        rationale="Order bound to active marketplace contract.",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(audit.id),
    )
    return str(contract.id)


__all__ = ["bind_contract_for_order"]
