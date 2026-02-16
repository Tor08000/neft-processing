from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMAuditEvent
from app.schemas.audit import AuditListOut

router = APIRouter(prefix="/audit", tags=["crm-audit"])


@router.get("", response_model=AuditListOut)
def list_audit(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    query = select(CRMAuditEvent).where(CRMAuditEvent.tenant_id == auth.tenant_id)
    if entity_type:
        query = query.where(CRMAuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.where(CRMAuditEvent.entity_id == entity_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMAuditEvent.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return AuditListOut(items=items, limit=limit, offset=offset, total=total)
