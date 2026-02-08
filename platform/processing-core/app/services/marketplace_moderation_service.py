from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.orm import Session

from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_moderation import (
    MarketplaceModerationAction,
    MarketplaceModerationAudit,
    MarketplaceModerationEntityType,
)
from app.models.marketplace_offers import MarketplaceOffer
from app.schemas.marketplace.moderation import ModerationEntityType
from app.services.audit_service import RequestContext


class MarketplaceModerationService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def list_queue(
        self,
        *,
        entity_type: ModerationEntityType | None = None,
        status: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        like = f"%{query_text}%" if query_text else None
        queries = []

        def _base_filters(model, title_field):
            filters = []
            if status:
                filters.append(model.status == status)
            if like is not None:
                filters.append(title_field.ilike(like))
            return filters

        if entity_type in (None, ModerationEntityType.PRODUCT):
            product = MarketplaceProductCard
            queries.append(
                select(
                    literal(MarketplaceModerationEntityType.PRODUCT.value).label("type"),
                    product.id.label("id"),
                    product.partner_id.label("partner_id"),
                    product.title.label("title"),
                    product.status.label("status"),
                    func.coalesce(product.updated_at, product.created_at).label("submitted_at"),
                    product.updated_at.label("updated_at"),
                ).where(*_base_filters(product, product.title))
            )

        if entity_type in (None, ModerationEntityType.SERVICE):
            service = MarketplaceService
            queries.append(
                select(
                    literal(MarketplaceModerationEntityType.SERVICE.value).label("type"),
                    service.id.label("id"),
                    service.partner_id.label("partner_id"),
                    service.title.label("title"),
                    service.status.label("status"),
                    func.coalesce(service.updated_at, service.created_at).label("submitted_at"),
                    service.updated_at.label("updated_at"),
                ).where(*_base_filters(service, service.title))
            )

        if entity_type in (None, ModerationEntityType.OFFER):
            offer = MarketplaceOffer
            title_expr = func.coalesce(offer.title_override, literal("Offer"))
            queries.append(
                select(
                    literal(MarketplaceModerationEntityType.OFFER.value).label("type"),
                    offer.id.label("id"),
                    offer.partner_id.label("partner_id"),
                    title_expr.label("title"),
                    offer.status.label("status"),
                    func.coalesce(offer.updated_at, offer.created_at).label("submitted_at"),
                    offer.updated_at.label("updated_at"),
                ).where(*_base_filters(offer, title_expr))
            )

        if not queries:
            return [], 0

        union_query = union_all(*queries).subquery()
        total = self.db.execute(select(func.count()).select_from(union_query)).scalar_one()
        ordered = (
            select(union_query)
            .order_by(union_query.c.submitted_at.desc().nullslast(), union_query.c.updated_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        rows = self.db.execute(ordered).mappings().all()
        items = [
            {
                "type": row["type"],
                "id": str(row["id"]),
                "partner_id": str(row["partner_id"]),
                "title": row["title"],
                "status": row["status"],
                "submitted_at": row["submitted_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return items, total

    def record_audit(
        self,
        *,
        entity_type: MarketplaceModerationEntityType,
        entity_id: str,
        action: MarketplaceModerationAction,
        reason_code: str | None = None,
        comment: str | None = None,
        before_status: str | None = None,
        after_status: str | None = None,
        meta: dict | None = None,
    ) -> MarketplaceModerationAudit:
        actor_id = self.request_ctx.actor_id if self.request_ctx else None
        actor_role = None
        if self.request_ctx and self.request_ctx.actor_roles:
            actor_role = self.request_ctx.actor_roles[0]
        audit = MarketplaceModerationAudit(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_id,
            actor_role=actor_role,
            action=action,
            reason_code=reason_code,
            comment=comment,
            before_status=before_status,
            after_status=after_status,
            meta=meta,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.flush()
        return audit

    def list_audit(
        self,
        *,
        entity_type: MarketplaceModerationEntityType,
        entity_id: str,
    ) -> list[MarketplaceModerationAudit]:
        return (
            self.db.query(MarketplaceModerationAudit)
            .filter(
                MarketplaceModerationAudit.entity_type == entity_type,
                MarketplaceModerationAudit.entity_id == entity_id,
            )
            .order_by(MarketplaceModerationAudit.created_at.desc(), MarketplaceModerationAudit.id.desc())
            .all()
        )
