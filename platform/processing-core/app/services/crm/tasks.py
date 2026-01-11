from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMTask
from app.schemas.crm import CRMTaskCreate, CRMTaskUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def create_task(
    db: Session,
    *,
    payload: CRMTaskCreate,
    request_ctx: RequestContext | None,
) -> CRMTask:
    task = CRMTask(
        tenant_id=payload.tenant_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        due_at=payload.due_at,
        assigned_to=payload.assigned_to,
        created_by=payload.created_by,
    )
    task = repository.add_task(db, task)
    events.audit_event(
        db,
        event_type=events.CRM_TASK_CREATED,
        entity_type="crm_task",
        entity_id=str(task.id),
        payload={"status": task.status.value, "priority": task.priority.value},
        request_ctx=request_ctx,
    )
    return task


def update_task(
    db: Session,
    *,
    task: CRMTask,
    payload: CRMTaskUpdate,
    request_ctx: RequestContext | None,
) -> CRMTask:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    task = repository.update_task(db, task)
    events.audit_event(
        db,
        event_type=events.CRM_TASK_UPDATED,
        entity_type="crm_task",
        entity_id=str(task.id),
        payload={"status": task.status.value, "priority": task.priority.value},
        request_ctx=request_ctx,
    )
    return task


__all__ = ["create_task", "update_task"]
