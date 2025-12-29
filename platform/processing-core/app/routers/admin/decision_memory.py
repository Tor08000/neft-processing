from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.decision_memory import DecisionMemoryEntityType
from app.schemas.admin.decision_memory import (
    DecisionActionStatsOut,
    DecisionCooldownOut,
    DecisionOutcomeOut,
)
from app.services.decision_memory import cooldown as memory_cooldown
from app.services.decision_memory import defaults as memory_defaults
from app.services.decision_memory import repository as memory_repository
from app.services.decision_memory import stats as memory_stats

router = APIRouter(prefix="/decision-memory", tags=["admin", "decision-memory"])


@router.get("/outcomes", response_model=list[DecisionOutcomeOut])
def list_outcomes(
    *,
    entity_type: DecisionMemoryEntityType = Query(...),
    entity_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DecisionOutcomeOut]:
    items = memory_repository.list_outcomes_for_entity(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [DecisionOutcomeOut.model_validate(item) for item in items]


@router.get("/stats", response_model=list[DecisionActionStatsOut])
def list_stats(
    *,
    tenant_id: int = Query(..., ge=1),
    action_code: str = Query(...),
    window_days: int = Query(memory_defaults.MEMORY_WINDOW_DAYS, ge=1),
    entity_type: DecisionMemoryEntityType | None = Query(None),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[DecisionActionStatsOut]:
    if entity_type:
        stats = [
            memory_stats.compute_action_stats(
                db,
                tenant_id=tenant_id,
                action_code=action_code,
                entity_type=entity_type,
                window_days=window_days,
                client_id=client_id,
            )
        ]
    else:
        stats = memory_stats.list_action_stats(
            db,
            tenant_id=tenant_id,
            action_code=action_code,
            window_days=window_days,
            client_id=client_id,
        )
    return [DecisionActionStatsOut(**item.__dict__) for item in stats]


@router.get("/cooldown", response_model=DecisionCooldownOut)
def get_cooldown(
    *,
    entity_type: DecisionMemoryEntityType = Query(...),
    entity_id: str = Query(...),
    action_code: str = Query(...),
    db: Session = Depends(get_db),
) -> DecisionCooldownOut:
    status = memory_cooldown.evaluate_cooldown(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action_code=action_code,
    )
    return DecisionCooldownOut(
        action_code=action_code,
        entity_type=entity_type,
        entity_id=entity_id,
        cooldown=status.cooldown,
        reason=status.reason,
        recent_count=status.recent_count,
        failed_streak=status.failed_streak,
    )


__all__ = ["router"]
