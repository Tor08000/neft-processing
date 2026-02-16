from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMComment
from app.schemas.comments import CommentCreate, CommentListOut, CommentOut
from app.services.audit_service import audit_comment

router = APIRouter(prefix="/comments", tags=["crm-comments"])


@router.get("", response_model=CommentListOut)
def list_comments(
    entity_type: str,
    entity_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    query = select(CRMComment).where(
        CRMComment.tenant_id == auth.tenant_id,
        CRMComment.entity_type == entity_type,
        CRMComment.entity_id == entity_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMComment.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return CommentListOut(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=CommentOut)
def create_comment(payload: CommentCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = CRMComment(tenant_id=auth.tenant_id, created_by_user_id=auth.actor.actor_id, **payload.model_dump())
    db.add(model)
    audit_comment(db, auth.tenant_id, payload.entity_type, payload.entity_id, auth.actor, {"body": payload.body})
    db.commit()
    db.refresh(model)
    return model
