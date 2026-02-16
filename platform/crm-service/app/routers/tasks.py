from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMTask
from app.schemas.tasks import TaskCreate, TaskListOut, TaskOut, TaskUpdate
from app.services.audit_service import audit_create, audit_update

router = APIRouter(prefix="/tasks", tags=["crm-tasks"])


@router.get("", response_model=TaskListOut)
def list_tasks(
    deal_id: str | None = None,
    contact_id: str | None = None,
    status: str | None = None,
    assignee_user_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    query = select(CRMTask).where(CRMTask.tenant_id == auth.tenant_id)
    if deal_id:
        query = query.where(CRMTask.deal_id == deal_id)
    if contact_id:
        query = query.where(CRMTask.contact_id == contact_id)
    if status:
        query = query.where(CRMTask.status == status)
    if assignee_user_id:
        query = query.where(CRMTask.assignee_user_id == assignee_user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMTask.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return TaskListOut(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=TaskOut)
def create_task(payload: TaskCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = CRMTask(tenant_id=auth.tenant_id, created_by_user_id=auth.actor.actor_id, **payload.model_dump())
    db.add(model)
    db.flush()
    audit_create(db, auth.tenant_id, "task", model.id, auth.actor, payload.model_dump())
    db.commit()
    db.refresh(model)
    return model


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMTask, task_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return model


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: str, payload: TaskUpdate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMTask, task_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    before = TaskOut.model_validate(model).model_dump(mode="json")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(model, k, v)
    after = TaskOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "task", model.id, auth.actor, before, after)
    db.commit()
    db.refresh(model)
    return model


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    return _change_task_status(task_id, "done", auth, db)


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    return _change_task_status(task_id, "canceled", auth, db)


def _change_task_status(task_id: str, status: str, auth: AuthContext, db: Session) -> CRMTask:
    model = db.get(CRMTask, task_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    before = TaskOut.model_validate(model).model_dump(mode="json")
    model.status = status
    after = TaskOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "task", model.id, auth.actor, before, after, action="status_change")
    db.commit()
    db.refresh(model)
    return model
