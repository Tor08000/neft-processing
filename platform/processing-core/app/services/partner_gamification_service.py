from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.marketplace_promotions import (
    MissionProgressStatus,
    PartnerMission,
    PartnerMissionProgress,
    PartnerTier,
    PartnerTierState,
)


class PartnerGamificationServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


class PartnerGamificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_tier_state(self, *, partner_id: str) -> tuple[PartnerTierState, PartnerTier]:
        state = self.db.query(PartnerTierState).filter(PartnerTierState.partner_id == partner_id).one_or_none()
        if state:
            tier = self.db.query(PartnerTier).filter(PartnerTier.tier_code == state.tier_code).one_or_none()
            if tier:
                return state, tier
        tier = self.db.query(PartnerTier).order_by(PartnerTier.tier_code.asc()).first()
        if not tier:
            raise PartnerGamificationServiceError("tier_not_configured")
        state = PartnerTierState(
            partner_id=partner_id,
            tier_code=tier.tier_code,
            score=0,
            metrics_snapshot={},
            evaluated_at=self._now(),
        )
        return state, tier

    def list_missions(self, *, partner_id: str) -> list[tuple[PartnerMission, PartnerMissionProgress | None]]:
        missions = self.db.query(PartnerMission).filter(PartnerMission.active.is_(True)).all()
        progress = (
            self.db.query(PartnerMissionProgress)
            .filter(PartnerMissionProgress.partner_id == partner_id)
            .all()
        )
        progress_map = {item.mission_id: item for item in progress}
        return [(mission, progress_map.get(mission.id)) for mission in missions]

    def claim_mission(self, *, partner_id: str, mission_id: str) -> PartnerMissionProgress:
        progress = (
            self.db.query(PartnerMissionProgress)
            .filter(
                PartnerMissionProgress.partner_id == partner_id,
                PartnerMissionProgress.mission_id == mission_id,
            )
            .one_or_none()
        )
        if not progress:
            raise PartnerGamificationServiceError("mission_progress_not_found")
        if progress.status not in {MissionProgressStatus.COMPLETED, MissionProgressStatus.COMPLETED.value}:
            raise PartnerGamificationServiceError("mission_not_completed")
        progress.status = MissionProgressStatus.CLAIMED
        progress.updated_at = self._now()
        self.db.flush()
        return progress

    def leaderboard(self, *, limit: int = 50) -> list[PartnerTierState]:
        return (
            self.db.query(PartnerTierState)
            .order_by(PartnerTierState.score.desc(), PartnerTierState.evaluated_at.desc())
            .limit(limit)
            .all()
        )


__all__ = ["PartnerGamificationService", "PartnerGamificationServiceError"]
