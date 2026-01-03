from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_promotions import PartnerMission
from app.schemas.marketplace.gamification import (
    PartnerLeaderboardEntry,
    PartnerLeaderboardResponse,
    PartnerMissionClaimResponse,
    PartnerMissionsResponse,
    PartnerMissionOut,
    PartnerTierOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.partner_gamification_service import (
    PartnerGamificationService,
    PartnerGamificationServiceError,
)

router = APIRouter(prefix="/partner/gamification", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _handle_service_error(exc: PartnerGamificationServiceError) -> None:
    if exc.code in {"mission_progress_not_found", "tier_not_configured"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code == "mission_not_completed":
        raise HTTPException(status_code=409, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("/tier", response_model=PartnerTierOut)
def get_partner_tier(
    principal: Principal = Depends(require_permission("partner:gamification:*")),
    db: Session = Depends(get_db),
) -> PartnerTierOut:
    partner_id = _ensure_partner_context(principal)
    service = PartnerGamificationService(db)
    try:
        state, tier = service.get_tier_state(partner_id=partner_id)
    except PartnerGamificationServiceError as exc:
        _handle_service_error(exc)
    return PartnerTierOut(
        partner_id=str(state.partner_id),
        tier_code=state.tier_code,
        title=tier.title,
        score=state.score,
        metrics_snapshot=state.metrics_snapshot,
        evaluated_at=state.evaluated_at,
        benefits=tier.benefits,
        thresholds=tier.thresholds,
    )


@router.get("/missions", response_model=PartnerMissionsResponse)
def list_partner_missions(
    principal: Principal = Depends(require_permission("partner:gamification:*")),
    db: Session = Depends(get_db),
) -> PartnerMissionsResponse:
    partner_id = _ensure_partner_context(principal)
    service = PartnerGamificationService(db)
    missions = service.list_missions(partner_id=partner_id)
    items = []
    for mission, progress in missions:
        items.append(
            PartnerMissionOut(
                mission_id=str(mission.id),
                title=mission.title,
                description=mission.description,
                rule=mission.rule,
                reward=mission.reward,
                progress=progress.progress if progress else 0,
                status=progress.status.value if progress and hasattr(progress.status, "value") else (progress.status if progress else "ACTIVE"),
                updated_at=progress.updated_at if progress else datetime.now(timezone.utc),
            )
        )
    return PartnerMissionsResponse(items=items)


@router.post("/missions/{mission_id}/claim", response_model=PartnerMissionClaimResponse)
def claim_partner_mission(
    mission_id: str,
    principal: Principal = Depends(require_permission("partner:gamification:*")),
    db: Session = Depends(get_db),
) -> PartnerMissionClaimResponse:
    partner_id = _ensure_partner_context(principal)
    service = PartnerGamificationService(db)
    try:
        progress = service.claim_mission(partner_id=partner_id, mission_id=mission_id)
    except PartnerGamificationServiceError as exc:
        _handle_service_error(exc)
    mission = db.query(PartnerMission).filter(PartnerMission.id == mission_id).one_or_none()
    db.commit()
    return PartnerMissionClaimResponse(
        mission_id=mission_id,
        status=progress.status.value if hasattr(progress.status, "value") else progress.status,
        reward=mission.reward if mission else {},
    )


@router.get("/leaderboard", response_model=PartnerLeaderboardResponse)
def get_partner_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_permission("partner:gamification:*")),
    db: Session = Depends(get_db),
) -> PartnerLeaderboardResponse:
    _ensure_partner_context(principal)
    service = PartnerGamificationService(db)
    items = service.leaderboard(limit=limit)
    return PartnerLeaderboardResponse(
        items=[
            PartnerLeaderboardEntry(
                partner_id=str(item.partner_id),
                tier_code=item.tier_code,
                score=item.score,
                metrics_snapshot=item.metrics_snapshot,
                evaluated_at=item.evaluated_at,
            )
            for item in items
        ]
    )
