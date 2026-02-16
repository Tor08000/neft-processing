from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMPipeline, CRMPipelineStage
from app.schemas.pipelines import (
    PipelineCreate,
    PipelineListOut,
    PipelineOut,
    PipelineUpdate,
    StageCreate,
    StageOut,
    StageUpdate,
)

router = APIRouter(prefix="/pipelines", tags=["crm-pipelines"])


def _ensure_default_pipeline(db: Session, tenant_id: str) -> None:
    has_default = db.scalar(select(func.count()).select_from(CRMPipeline).where(CRMPipeline.tenant_id == tenant_id, CRMPipeline.is_default))
    if not has_default:
        db.add(CRMPipeline(tenant_id=tenant_id, name="Default", is_default=True))
        db.commit()


@router.get("", response_model=PipelineListOut)
def list_pipelines(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    _ensure_default_pipeline(db, auth.tenant_id)
    query = select(CRMPipeline).options(selectinload(CRMPipeline.stages)).where(CRMPipeline.tenant_id == auth.tenant_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMPipeline.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return PipelineListOut(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=PipelineOut)
def create_pipeline(payload: PipelineCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    if payload.is_default:
        db.execute(select(CRMPipeline).where(CRMPipeline.tenant_id == auth.tenant_id)).scalars().all()
        db.query(CRMPipeline).filter(CRMPipeline.tenant_id == auth.tenant_id).update({"is_default": False})
    model = CRMPipeline(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    item = db.execute(
        select(CRMPipeline).options(selectinload(CRMPipeline.stages)).where(CRMPipeline.id == pipeline_id, CRMPipeline.tenant_id == auth.tenant_id)
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return item


@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(pipeline_id: str, payload: PipelineUpdate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    item = db.get(CRMPipeline, pipeline_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default"):
        db.query(CRMPipeline).filter(CRMPipeline.tenant_id == auth.tenant_id).update({"is_default": False})
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{pipeline_id}/stages", response_model=StageOut)
def create_stage(pipeline_id: str, payload: StageCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    pipeline = db.get(CRMPipeline, pipeline_id)
    if not pipeline or pipeline.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    model = CRMPipelineStage(pipeline_id=pipeline_id, tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.patch("/{pipeline_id}/stages/{stage_id}", response_model=StageOut)
def update_stage(
    pipeline_id: str,
    stage_id: str,
    payload: StageUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    model = db.get(CRMPipelineStage, stage_id)
    if not model or model.tenant_id != auth.tenant_id or model.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Stage not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(model, k, v)
    db.commit()
    db.refresh(model)
    return model


@router.delete("/{pipeline_id}/stages/{stage_id}")
def delete_stage(pipeline_id: str, stage_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMPipelineStage, stage_id)
    if not model or model.tenant_id != auth.tenant_id or model.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Stage not found")
    db.delete(model)
    db.commit()
    return {"status": "ok"}
