from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.risk_training_snapshot import RiskTrainingSnapshot


@dataclass(frozen=True)
class RetrainingRequest:
    triggered_by: str
    requested_at: datetime


class RetrainingService:
    """Manual retraining trigger for offline batches."""

    def __init__(self, db: Session):
        self.db = db

    def trigger(self, *, triggered_by: str) -> RetrainingRequest:
        return RetrainingRequest(triggered_by=triggered_by, requested_at=datetime.now(timezone.utc))

    def list_training_snapshots(self, *, limit: int = 500) -> list[RiskTrainingSnapshot]:
        return (
            self.db.query(RiskTrainingSnapshot)
            .order_by(RiskTrainingSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )


__all__ = ["RetrainingRequest", "RetrainingService"]
