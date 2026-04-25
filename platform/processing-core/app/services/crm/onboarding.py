from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.client_actions import DocumentAcknowledgement
from app.models.crm import (
    ClientOnboardingEvent,
    ClientOnboardingEventType,
    ClientOnboardingState,
    ClientOnboardingStateEnum,
    CRMClient,
    CRMSubscription,
)
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


class OnboardingAction(str, Enum):
    QUALIFY_LEAD = "QUALIFY_LEAD"
    REQUEST_LEGAL = "REQUEST_LEGAL"
    GENERATE_CONTRACT = "GENERATE_CONTRACT"
    SIGN_CONTRACT = "SIGN_CONTRACT"
    ASSIGN_SUBSCRIPTION = "ASSIGN_SUBSCRIPTION"
    APPLY_LIMITS_PROFILE = "APPLY_LIMITS_PROFILE"
    ISSUE_CARDS = "ISSUE_CARDS"
    SKIP_CARDS = "SKIP_CARDS"
    ACTIVATE_CLIENT = "ACTIVATE_CLIENT"
    ALLOW_FIRST_OPERATION = "ALLOW_FIRST_OPERATION"


@dataclass(frozen=True)
class OnboardingFacts:
    legal_accepted: bool
    contract_signed: bool
    subscription_assigned: bool
    limits_applied: bool
    cards_issued: bool
    client_activated: bool
    first_operation_allowed: bool
    cards_skipped: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_client(db: Session, client_id: str) -> CRMClient | None:
    return db.query(CRMClient).filter(CRMClient.id == client_id).one_or_none()


def _gather_facts(db: Session, *, client_id: str, meta: dict[str, Any] | None) -> OnboardingFacts:
    meta = meta or {}
    legal_accepted = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.client_id == client_id)
        .count()
        > 0
    )
    active_contract = repository.get_active_contract(db, client_id=client_id)
    contract_signed = active_contract is not None
    subscription_assigned = (
        db.query(CRMSubscription)
        .filter(CRMSubscription.client_id == client_id)
        .count()
        > 0
    )
    limits_applied = bool(active_contract and active_contract.limit_profile_id)
    cards_issued = (
        db.query(Card)
        .filter(Card.client_id == client_id)
        .count()
        > 0
    ) or bool(meta.get("cards_issued"))
    cards_skipped = bool(meta.get("cards_skipped"))
    client = _get_client(db, client_id)
    client_activated = bool(client and client.status.value == "ACTIVE")
    first_operation_allowed = bool(meta.get("first_operation_allowed"))
    return OnboardingFacts(
        legal_accepted=legal_accepted or bool(meta.get("legal_accepted")),
        contract_signed=contract_signed or bool(meta.get("contract_signed")),
        subscription_assigned=subscription_assigned or bool(meta.get("subscription_assigned")),
        limits_applied=limits_applied or bool(meta.get("limits_applied")),
        cards_issued=cards_issued,
        client_activated=client_activated or bool(meta.get("client_activated")),
        first_operation_allowed=first_operation_allowed,
        cards_skipped=cards_skipped,
    )


def _derive_state(facts: OnboardingFacts) -> ClientOnboardingStateEnum:
    if facts.first_operation_allowed:
        return ClientOnboardingStateEnum.FIRST_OPERATION_ALLOWED
    if facts.client_activated:
        return ClientOnboardingStateEnum.CLIENT_ACTIVATED
    if facts.cards_issued or facts.cards_skipped:
        return ClientOnboardingStateEnum.CARDS_ISSUED
    if facts.limits_applied:
        return ClientOnboardingStateEnum.LIMITS_APPLIED
    if facts.subscription_assigned:
        return ClientOnboardingStateEnum.SUBSCRIPTION_ASSIGNED
    if facts.contract_signed:
        return ClientOnboardingStateEnum.CONTRACT_SIGNED
    if facts.legal_accepted:
        return ClientOnboardingStateEnum.LEGAL_ACCEPTED
    return ClientOnboardingStateEnum.LEGAL_ACCEPTANCE_PENDING


def get_or_init_state(db: Session, *, client_id: str) -> ClientOnboardingState:
    existing = repository.get_onboarding_state(db, client_id=client_id)
    if existing:
        return existing
    return repository.initialize_onboarding_state(db, client_id=client_id)


def recompute(
    db: Session,
    *,
    client_id: str,
    request_ctx: RequestContext | None,
) -> tuple[ClientOnboardingState, OnboardingFacts]:
    state = get_or_init_state(db, client_id=client_id)
    facts = _gather_facts(db, client_id=client_id, meta=state.meta)
    new_state = _derive_state(facts)
    if new_state != state.state:
        previous = state.state
        state.state = new_state
        state.state_entered_at = _now()
        state.is_blocked = False
        state.block_reason = None
        repository.upsert_onboarding_state(db, state)
        repository.add_onboarding_event(
            db,
            ClientOnboardingEvent(
                client_id=client_id,
                event_type=ClientOnboardingEventType.STATE_CHANGED,
                from_state=previous,
                to_state=new_state,
                actor_id=request_ctx.actor_id if request_ctx else None,
                payload={"facts": facts.__dict__},
            ),
        )
        events.audit_event(
            db,
            event_type=events.ONBOARDING_STATE_CHANGED,
            entity_type="client_onboarding",
            entity_id=client_id,
            payload={"from": previous.value, "to": new_state.value},
            request_ctx=request_ctx,
        )
    return state, facts


def _block_state(
    db: Session,
    *,
    state: ClientOnboardingState,
    reason: str,
    request_ctx: RequestContext | None,
) -> ClientOnboardingState:
    state.is_blocked = True
    state.block_reason = reason
    repository.upsert_onboarding_state(db, state)
    repository.add_onboarding_event(
        db,
        ClientOnboardingEvent(
            client_id=state.client_id,
            event_type=ClientOnboardingEventType.BLOCKED,
            from_state=state.state,
            to_state=state.state,
            actor_id=request_ctx.actor_id if request_ctx else None,
            payload={"reason": reason},
        ),
    )
    events.audit_event(
        db,
        event_type=events.ONBOARDING_BLOCKED,
        entity_type="client_onboarding",
        entity_id=state.client_id,
        payload={"state": state.state.value, "reason": reason},
        request_ctx=request_ctx,
    )
    return state


def advance(
    db: Session,
    *,
    client_id: str,
    action: OnboardingAction,
    request_ctx: RequestContext | None,
) -> tuple[ClientOnboardingState, OnboardingFacts]:
    state = get_or_init_state(db, client_id=client_id)
    # JSON columns don't track repeated in-place mutations reliably.
    # Copy before each action so later onboarding steps persist cumulatively.
    meta = dict(state.meta or {})
    facts = _gather_facts(db, client_id=client_id, meta=meta)

    def _return_blocked(reason: str) -> tuple[ClientOnboardingState, OnboardingFacts]:
        blocked = _block_state(db, state=state, reason=reason, request_ctx=request_ctx)
        return blocked, facts

    if action == OnboardingAction.REQUEST_LEGAL:
        meta["legal_requested"] = True
        meta.setdefault("legal_accepted", True)
    elif action == OnboardingAction.GENERATE_CONTRACT and not facts.legal_accepted:
        return _return_blocked("legal_not_accepted")
    elif action == OnboardingAction.SIGN_CONTRACT and not facts.legal_accepted:
        return _return_blocked("legal_not_accepted")
    elif action == OnboardingAction.ASSIGN_SUBSCRIPTION and not facts.contract_signed:
        return _return_blocked("contract_not_signed")
    elif action == OnboardingAction.APPLY_LIMITS_PROFILE and not facts.subscription_assigned:
        return _return_blocked("subscription_not_assigned")
    elif action == OnboardingAction.ISSUE_CARDS and not facts.limits_applied:
        return _return_blocked("limits_not_applied")
    elif action == OnboardingAction.SKIP_CARDS and not facts.limits_applied:
        return _return_blocked("limits_not_applied")
    elif action == OnboardingAction.ACTIVATE_CLIENT and not (facts.subscription_assigned and facts.limits_applied):
        return _return_blocked("activation_prerequisites_missing")
    elif action == OnboardingAction.ALLOW_FIRST_OPERATION and not facts.client_activated:
        return _return_blocked("client_not_active")

    if action == OnboardingAction.ISSUE_CARDS:
        meta["cards_issued"] = True
    if action == OnboardingAction.SKIP_CARDS:
        meta["cards_skipped"] = True
    if action == OnboardingAction.SIGN_CONTRACT:
        meta["contract_signed"] = True
    if action == OnboardingAction.ASSIGN_SUBSCRIPTION:
        meta["subscription_assigned"] = True
    if action == OnboardingAction.APPLY_LIMITS_PROFILE:
        meta["limits_applied"] = True
    if action == OnboardingAction.ACTIVATE_CLIENT:
        meta["client_activated"] = True
    if action == OnboardingAction.ALLOW_FIRST_OPERATION:
        meta["first_operation_allowed"] = True

    state.meta = meta
    repository.upsert_onboarding_state(db, state)
    repository.add_onboarding_event(
        db,
        ClientOnboardingEvent(
            client_id=client_id,
            event_type=ClientOnboardingEventType.ACTION_APPLIED,
            from_state=state.state,
            to_state=state.state,
            actor_id=request_ctx.actor_id if request_ctx else None,
            payload={"action": action.value},
        ),
    )
    events.audit_event(
        db,
        event_type=events.ONBOARDING_ACTION_APPLIED,
        entity_type="client_onboarding",
        entity_id=client_id,
        payload={"action": action.value},
        request_ctx=request_ctx,
    )
    return recompute(db, client_id=client_id, request_ctx=request_ctx)


__all__ = [
    "OnboardingAction",
    "OnboardingFacts",
    "advance",
    "get_or_init_state",
    "recompute",
]
