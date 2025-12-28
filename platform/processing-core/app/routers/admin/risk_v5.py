from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.risk_v5_label import RiskV5LabelRecord
from app.models.risk_v5_shadow_decision import RiskV5ShadowDecision
from app.schemas.admin.risk_v5 import (
    RiskV5ABAssignmentCreate,
    RiskV5ABAssignmentRead,
    RiskV5ModelActivate,
    RiskV5RetrainingResponse,
    RiskV5RetrainingRun,
)
from app.services.risk_v5.ab import create_assignment
from app.services.risk_v5.features import FEATURES_SCHEMA_VERSION
from app.services.risk_v5.registry_client import activate_model
from app.services.risk_v5.retraining.schedule import run_retraining


router = APIRouter(prefix="/risk-v5", tags=["admin"])


@router.post("/ab/assignments", response_model=RiskV5ABAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_ab_assignment(
    body: RiskV5ABAssignmentCreate,
    db: Session = Depends(get_db),
) -> RiskV5ABAssignmentRead:
    assignment = create_assignment(
        db,
        tenant_id=body.tenant_id,
        client_id=body.client_id,
        subject_type=body.subject_type,
        bucket=body.bucket,
        weight=body.weight,
        active=body.active,
    )
    return RiskV5ABAssignmentRead.model_validate(assignment)


@router.post("/models/activate")
def activate_model_version(body: RiskV5ModelActivate) -> dict:
    return activate_model(subject_type=body.subject_type, model_version=body.model_version)


@router.post("/retraining/run", response_model=RiskV5RetrainingResponse)
def run_retraining_job(
    body: RiskV5RetrainingRun,
    db: Session = Depends(get_db),
) -> RiskV5RetrainingResponse:
    rows = (
        db.query(RiskV5ShadowDecision)
        .order_by(RiskV5ShadowDecision.created_at.desc())
        .limit(body.shadow_limit)
        .all()
    )
    decision_ids = [row.decision_id for row in rows]
    labels = []
    if decision_ids:
        labels = (
            db.query(RiskV5LabelRecord)
            .filter(RiskV5LabelRecord.decision_id.in_(decision_ids))
            .all()
        )
    labels_by_decision = {label.decision_id: label for label in labels}

    shadow_rows = []
    for row in rows:
        label = labels_by_decision.get(row.decision_id)
        shadow_rows.append(
            {
                "decision_id": row.decision_id,
                "features": row.features_snapshot,
                "score": row.v5_score,
                "model_version": row.v5_model_version,
                "predicted_outcome": row.v5_predicted_outcome,
                "label": label.label.value if label else None,
                "label_source": label.label_source.value if label else None,
            }
        )

    result = run_retraining(shadow_rows=shadow_rows, schema_version=FEATURES_SCHEMA_VERSION)
    return RiskV5RetrainingResponse(
        published=result.publish.published,
        model_version=result.publish.model_version,
    )


__all__ = ["router"]
