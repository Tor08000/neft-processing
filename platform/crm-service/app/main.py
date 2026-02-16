from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import Principal, get_principal
from .db import Base, engine, get_db
from .models import CRMAuditLog, CRMComment, CRMContact, CRMDeal, CRMPipeline, CRMStage, CRMTask, OutboxEvent
from .schemas import (
    CloseDealIn,
    CommentIn,
    ContactIn,
    ContactPatch,
    DealIn,
    DealPatch,
    MoveStageIn,
    PipelineIn,
    StageIn,
    TaskIn,
    TaskPatch,
)

SERVICE_NAME = "crm-service"
SERVICE_VERSION = "v1"
METRIC_PREFIX = "crm_service"

app = FastAPI(title="CRM Service")
Base.metadata.create_all(bind=engine)

CRM_SERVICE_UP = Gauge(f"{METRIC_PREFIX}_up", "CRM service up")
CRM_SERVICE_HTTP_REQUESTS_TOTAL = Counter(
    f"{METRIC_PREFIX}_http_requests_total", "Total HTTP requests handled by CRM", ["method", "path", "status"]
)
crm_deals_total = Counter("crm_deals_total", "Created deals")
crm_deals_won_total = Counter("crm_deals_won_total", "Won deals")
crm_deals_lost_total = Counter("crm_deals_lost_total", "Lost deals")
crm_open_tasks_total = Gauge("crm_open_tasks_total", "Open CRM tasks")
CRM_SERVICE_UP.set(1)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(method=request.method, path=request.url.path, status="500").inc()
        raise
    CRM_SERVICE_HTTP_REQUESTS_TOTAL.labels(method=request.method, path=request.url.path, status=str(response.status_code)).inc()
    return response


def _check_access(principal: Principal, owner_id: str) -> None:
    if "admin" in principal.roles:
        return
    if "sales_manager" in principal.roles:
        if owner_id == principal.user_id or owner_id in principal.subordinate_ids:
            return
    if "sales_user" in principal.roles and owner_id == principal.user_id:
        return
    raise HTTPException(status_code=403, detail="RBAC denied")


def _validate_entity(db: Session, tenant_id: str, entity_type: str, entity_id: str) -> None:
    if entity_type not in {"client", "partner"}:
        raise HTTPException(status_code=400, detail="entity_type must be client or partner")
    table = "clients" if entity_type == "client" else "partners"
    row = db.execute(
        text(f"SELECT 1 FROM {table} WHERE id = :entity_id AND CAST(tenant_id AS TEXT) = :tenant_id LIMIT 1"),
        {"entity_id": entity_id, "tenant_id": tenant_id},
    ).first()
    if not row:
        raise HTTPException(status_code=400, detail=f"{entity_type} not found for tenant")


def _audit(db: Session, principal: Principal, entity_type: str, entity_id: str, action: str, old_data: dict | None, new_data: dict | None) -> None:
    db.add(
        CRMAuditLog(
            tenant_id=principal.tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_data=old_data,
            new_data=new_data,
            actor_id=principal.user_id,
        )
    )


def _refresh_open_tasks(db: Session) -> None:
    count = db.query(CRMTask).filter(CRMTask.status == "open").count()
    crm_open_tasks_total.set(count)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/crm/pipelines")
def create_pipeline(payload: PipelineIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pipe = CRMPipeline(tenant_id=principal.tenant_id, name=payload.name)
    db.add(pipe)
    db.commit()
    db.refresh(pipe)
    return pipe


@app.post("/crm/stages")
def create_stage(payload: StageIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pipeline = db.get(CRMPipeline, payload.pipeline_id)
    if not pipeline or pipeline.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    stage = CRMStage(**payload.model_dump())
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@app.get("/crm/contacts")
def list_contacts(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return db.execute(select(CRMContact).where(CRMContact.tenant_id == principal.tenant_id)).scalars().all()


@app.post("/crm/contacts")
def create_contact(payload: ContactIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _check_access(principal, payload.owner_id)
    _validate_entity(db, principal.tenant_id, payload.entity_type, payload.entity_id)
    contact = CRMContact(tenant_id=principal.tenant_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@app.patch("/crm/contacts/{contact_id}")
def patch_contact(contact_id: str, payload: ContactPatch, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    contact = db.get(CRMContact, contact_id)
    if not contact or contact.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    _check_access(principal, payload.owner_id or contact.owner_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return contact


@app.get("/crm/deals")
def list_deals(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    query = select(CRMDeal).where(CRMDeal.tenant_id == principal.tenant_id)
    if "admin" in principal.roles:
        pass
    elif "sales_manager" in principal.roles:
        query = query.where(CRMDeal.owner_id.in_([principal.user_id, *principal.subordinate_ids]))
    else:
        query = query.where(CRMDeal.owner_id == principal.user_id)
    return db.execute(query).scalars().all()


@app.post("/crm/deals")
def create_deal(payload: DealIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _check_access(principal, payload.owner_id)
    _validate_entity(db, principal.tenant_id, payload.entity_type, payload.entity_id)
    deal = CRMDeal(tenant_id=principal.tenant_id, **payload.model_dump())
    db.add(deal)
    db.flush()
    _audit(db, principal, "deal", deal.id, "create", None, payload.model_dump())
    crm_deals_total.inc()
    db.commit()
    db.refresh(deal)
    return deal


@app.patch("/crm/deals/{deal_id}")
def patch_deal(deal_id: str, payload: DealPatch, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    deal = db.get(CRMDeal, deal_id)
    if not deal or deal.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    _check_access(principal, payload.owner_id or deal.owner_id)
    old = {"amount": float(deal.amount), "owner_id": deal.owner_id, "status": deal.status}
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(deal, k, v)
    if payload.amount is not None:
        _audit(db, principal, "deal", deal.id, "update", {"amount": old["amount"]}, {"amount": payload.amount})
    if payload.owner_id is not None:
        _audit(db, principal, "deal", deal.id, "update", {"owner_id": old["owner_id"]}, {"owner_id": payload.owner_id})
    db.commit()
    db.refresh(deal)
    return deal


@app.post("/crm/deals/{deal_id}/move-stage")
def move_stage(deal_id: str, payload: MoveStageIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    deal = db.get(CRMDeal, deal_id)
    if not deal or deal.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    _check_access(principal, deal.owner_id)
    old_stage = deal.stage_id
    deal.stage_id = payload.stage_id
    _audit(db, principal, "deal", deal.id, "stage_change", {"stage_id": old_stage}, {"stage_id": payload.stage_id})
    db.commit()
    db.refresh(deal)
    return deal


@app.post("/crm/deals/{deal_id}/close")
def close_deal(deal_id: str, payload: CloseDealIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if payload.status not in {"won", "lost"}:
        raise HTTPException(status_code=400, detail="status must be won or lost")
    deal = db.get(CRMDeal, deal_id)
    if not deal or deal.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    _check_access(principal, deal.owner_id)
    old = {"status": deal.status}
    deal.status = payload.status
    _audit(db, principal, "deal", deal.id, "update", old, {"status": deal.status})
    _audit(db, principal, "deal", deal.id, "close", old, {"status": deal.status})
    event_type = f"crm.deal.{payload.status}"
    db.add(OutboxEvent(tenant_id=principal.tenant_id, event_type=event_type, payload={"deal_id": deal.id, "status": payload.status}))
    if payload.status == "won":
        crm_deals_won_total.inc()
    else:
        crm_deals_lost_total.inc()
    db.commit()
    db.refresh(deal)
    return deal


@app.get("/crm/tasks")
def list_tasks(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    query = select(CRMTask).where(CRMTask.tenant_id == principal.tenant_id)
    if "admin" in principal.roles:
        pass
    elif "sales_manager" in principal.roles:
        query = query.where(CRMTask.assigned_to.in_([principal.user_id, *principal.subordinate_ids]))
    else:
        query = query.where(CRMTask.assigned_to == principal.user_id)
    return db.execute(query).scalars().all()


@app.post("/crm/tasks")
def create_task(payload: TaskIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _check_access(principal, payload.assigned_to)
    task = CRMTask(tenant_id=principal.tenant_id, created_by=principal.user_id, **payload.model_dump())
    db.add(task)
    db.commit()
    _refresh_open_tasks(db)
    db.refresh(task)
    return task


@app.patch("/crm/tasks/{task_id}")
def patch_task(task_id: str, payload: TaskPatch, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    task = db.get(CRMTask, task_id)
    if not task or task.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_access(principal, payload.assigned_to or task.assigned_to)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    db.commit()
    _refresh_open_tasks(db)
    db.refresh(task)
    return task


@app.get("/crm/{related_type}/{related_id}/comments")
def list_comments(related_type: str, related_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return db.execute(
        select(CRMComment).where(
            CRMComment.tenant_id == principal.tenant_id,
            CRMComment.related_type == related_type,
            CRMComment.related_id == related_id,
        )
    ).scalars().all()


@app.post("/crm/{related_type}/{related_id}/comments")
def create_comment(
    related_type: str, related_id: str, payload: CommentIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    comment = CRMComment(
        tenant_id=principal.tenant_id,
        related_type=related_type,
        related_id=related_id,
        message=payload.message,
        author_id=principal.user_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
