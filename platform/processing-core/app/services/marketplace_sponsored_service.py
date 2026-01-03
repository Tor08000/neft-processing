from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import MarketplaceProduct
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_sponsored import (
    SponsoredCampaign,
    SponsoredCampaignObjective,
    SponsoredCampaignStatus,
    SponsoredEvent,
    SponsoredEventType,
    SponsoredSpendDirection,
    SponsoredSpendLedger,
    SponsoredSpendType,
)
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class SponsoredRankingConfig:
    max_candidates: int = 200
    max_boost: Decimal = Decimal("0.15")
    max_bid: Decimal = Decimal("100")
    sponsored_slots: int = 3
    attribution_window_days: int = 7
    click_dedupe_minutes: int = 30


class MarketplaceSponsoredService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)
        self.config = SponsoredRankingConfig()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _audit(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
        external_refs: dict | None = None,
    ):
        return self.audit_service.audit(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            reason=reason,
            external_refs=external_refs,
            request_ctx=self.request_ctx,
        )

    @staticmethod
    def _decimal(value: object | None) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _remaining_budget(self, campaign: SponsoredCampaign) -> Decimal:
        return self._decimal(campaign.total_budget) - self._decimal(campaign.spent_budget)

    def _daily_spend(self, campaign_id: str) -> Decimal:
        day_start = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
        total = (
            self.db.query(func.coalesce(func.sum(SponsoredSpendLedger.amount), 0))
            .filter(
                SponsoredSpendLedger.campaign_id == campaign_id,
                SponsoredSpendLedger.direction == SponsoredSpendDirection.DEBIT,
                SponsoredSpendLedger.created_at >= day_start,
            )
            .scalar()
        )
        return self._decimal(total)

    def _remaining_daily_cap(self, campaign: SponsoredCampaign) -> Decimal | None:
        if campaign.daily_cap is None:
            return None
        remaining = self._decimal(campaign.daily_cap) - self._daily_spend(str(campaign.id))
        return max(remaining, Decimal("0"))

    def _in_schedule(self, campaign: SponsoredCampaign, *, now: datetime | None = None) -> bool:
        if now is None:
            now = self._now()
        if campaign.starts_at and campaign.starts_at > now:
            return False
        if campaign.ends_at and campaign.ends_at < now:
            return False
        return True

    def _is_active(self, campaign: SponsoredCampaign, *, now: datetime | None = None) -> bool:
        status_value = campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status)
        if status_value != SponsoredCampaignStatus.ACTIVE.value:
            return False
        if not self._in_schedule(campaign, now=now):
            return False
        if self._remaining_budget(campaign) <= 0:
            return False
        remaining_daily = self._remaining_daily_cap(campaign)
        if remaining_daily is not None and remaining_daily <= 0:
            return False
        return True

    def create_campaign(
        self,
        *,
        tenant_id: str,
        partner_id: str,
        payload: dict,
    ) -> SponsoredCampaign:
        now = self._now()
        campaign_id = new_uuid_str()
        audit = self._audit(
            event_type="SPONSORED_CAMPAIGN_CREATED",
            entity_type="sponsored_campaign",
            entity_id=campaign_id,
            action="SPONSORED_CAMPAIGN_CREATED",
            after={
                "title": payload["title"],
                "objective": payload["objective"],
                "status": SponsoredCampaignStatus.DRAFT.value,
                "bid": str(payload["bid"]),
                "total_budget": str(payload["total_budget"]),
            },
        )
        campaign = SponsoredCampaign(
            id=campaign_id,
            tenant_id=tenant_id,
            partner_id=partner_id,
            title=payload["title"],
            objective=payload["objective"],
            status=SponsoredCampaignStatus.DRAFT.value,
            currency=payload.get("currency", "RUB"),
            targeting=payload.get("targeting", {}),
            scope=payload["scope"],
            bid=payload["bid"],
            daily_cap=payload.get("daily_cap"),
            total_budget=payload["total_budget"],
            spent_budget=Decimal("0"),
            starts_at=payload["starts_at"],
            ends_at=payload.get("ends_at"),
            created_at=now,
            updated_at=now,
        )
        self.db.add(campaign)
        self.db.flush()
        if audit:
            campaign.updated_at = now
        return campaign

    def update_campaign(
        self,
        *,
        campaign: SponsoredCampaign,
        payload: dict,
    ) -> SponsoredCampaign:
        before = {
            "title": campaign.title,
            "targeting": campaign.targeting,
            "scope": campaign.scope,
            "bid": str(campaign.bid),
            "daily_cap": str(campaign.daily_cap) if campaign.daily_cap is not None else None,
            "total_budget": str(campaign.total_budget),
            "starts_at": campaign.starts_at,
            "ends_at": campaign.ends_at,
        }
        for key, value in payload.items():
            if value is None:
                continue
            setattr(campaign, key, value)
        campaign.updated_at = self._now()
        after = {
            "title": campaign.title,
            "targeting": campaign.targeting,
            "scope": campaign.scope,
            "bid": str(campaign.bid),
            "daily_cap": str(campaign.daily_cap) if campaign.daily_cap is not None else None,
            "total_budget": str(campaign.total_budget),
            "starts_at": campaign.starts_at,
            "ends_at": campaign.ends_at,
        }
        self._audit(
            event_type="SPONSORED_CAMPAIGN_UPDATED",
            entity_type="sponsored_campaign",
            entity_id=str(campaign.id),
            action="SPONSORED_CAMPAIGN_UPDATED",
            before=before,
            after=after,
        )
        self.db.flush()
        return campaign

    def set_campaign_status(
        self,
        *,
        campaign: SponsoredCampaign,
        status: SponsoredCampaignStatus,
        reason: str | None = None,
    ) -> SponsoredCampaign:
        before = {"status": campaign.status}
        campaign.status = status.value if hasattr(status, "value") else str(status)
        campaign.updated_at = self._now()
        after = {"status": campaign.status}
        self._audit(
            event_type="SPONSORED_CAMPAIGN_STATUS_CHANGED",
            entity_type="sponsored_campaign",
            entity_id=str(campaign.id),
            action="SPONSORED_CAMPAIGN_STATUS_CHANGED",
            before=before,
            after=after,
            reason=reason,
        )
        self.db.flush()
        return campaign

    def list_campaigns(
        self,
        *,
        tenant_id: str | None = None,
        partner_id: str | None = None,
        status: SponsoredCampaignStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SponsoredCampaign], int]:
        query = self.db.query(SponsoredCampaign)
        if tenant_id:
            query = query.filter(SponsoredCampaign.tenant_id == tenant_id)
        if partner_id:
            query = query.filter(SponsoredCampaign.partner_id == partner_id)
        if status:
            query = query.filter(SponsoredCampaign.status == status)
        total = query.count()
        items = (
            query.order_by(SponsoredCampaign.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_campaign(self, campaign_id: str) -> SponsoredCampaign | None:
        return self.db.query(SponsoredCampaign).filter(SponsoredCampaign.id == campaign_id).one_or_none()

    def campaign_stats(self, *, campaign_id: str) -> dict:
        impressions = (
            self.db.query(func.count(SponsoredEvent.id))
            .filter(SponsoredEvent.campaign_id == campaign_id, SponsoredEvent.event_type == SponsoredEventType.IMPRESSION)
            .scalar()
        )
        clicks = (
            self.db.query(func.count(SponsoredEvent.id))
            .filter(SponsoredEvent.campaign_id == campaign_id, SponsoredEvent.event_type == SponsoredEventType.CLICK)
            .scalar()
        )
        conversions = (
            self.db.query(func.count(SponsoredEvent.id))
            .filter(
                SponsoredEvent.campaign_id == campaign_id,
                SponsoredEvent.event_type == SponsoredEventType.CONVERSION,
            )
            .scalar()
        )
        spend = (
            self.db.query(func.coalesce(func.sum(SponsoredSpendLedger.amount), 0))
            .filter(SponsoredSpendLedger.campaign_id == campaign_id, SponsoredSpendLedger.direction == SponsoredSpendDirection.DEBIT)
            .scalar()
        )
        return {
            "impressions": int(impressions or 0),
            "clicks": int(clicks or 0),
            "conversions": int(conversions or 0),
            "spend": self._decimal(spend),
        }

    def _matches_targeting(self, *, campaign: SponsoredCampaign, placement: str | None, category: str | None) -> bool:
        targeting = campaign.targeting or {}
        placements = targeting.get("placements")
        if placement and placements and placement not in placements:
            return False
        categories = targeting.get("categories")
        if category and categories and category not in categories:
            return False
        return True

    def _matches_scope(self, *, campaign: SponsoredCampaign, product: MarketplaceProduct) -> bool:
        scope = campaign.scope or {}
        product_ids = scope.get("product_ids") or []
        if product_ids:
            return str(product.id) in {str(item) for item in product_ids}
        category_codes = scope.get("category_codes") or []
        if category_codes:
            return product.category in category_codes
        if scope.get("store"):
            return str(product.partner_id) == str(campaign.partner_id)
        return False

    def _eligible_campaigns(
        self,
        *,
        tenant_id: str | None,
        placement: str | None,
        category: str | None,
        now: datetime,
    ) -> list[SponsoredCampaign]:
        query = self.db.query(SponsoredCampaign).filter(SponsoredCampaign.status == SponsoredCampaignStatus.ACTIVE)
        if tenant_id:
            query = query.filter(SponsoredCampaign.tenant_id == tenant_id)
        query = query.filter(
            and_(
                SponsoredCampaign.starts_at <= now,
                or_(SponsoredCampaign.ends_at.is_(None), SponsoredCampaign.ends_at >= now),
            )
        )
        campaigns = query.all()
        eligible: list[SponsoredCampaign] = []
        for campaign in campaigns:
            if not self._is_active(campaign, now=now):
                continue
            if not self._matches_targeting(campaign=campaign, placement=placement, category=category):
                continue
            eligible.append(campaign)
        return eligible

    def _pick_campaign_for_product(
        self,
        *,
        product: MarketplaceProduct,
        campaigns: Iterable[SponsoredCampaign],
    ) -> SponsoredCampaign | None:
        best = None
        best_score = Decimal("0")
        for campaign in campaigns:
            if not self._matches_scope(campaign=campaign, product=product):
                continue
            quality_score = Decimal("1")
            score = self._decimal(campaign.bid) * quality_score
            if score > best_score:
                best_score = score
                best = campaign
        return best

    def apply_sponsored_ranking(
        self,
        *,
        products: list[MarketplaceProduct],
        tenant_id: str | None,
        placement: str | None,
        category: str | None,
        context: dict,
        client_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        now = self._now()
        candidates = products[: self.config.max_candidates]
        campaigns = self._eligible_campaigns(tenant_id=tenant_id, placement=placement, category=category, now=now)
        ranked: list[dict] = []
        for idx, product in enumerate(candidates):
            base_score = Decimal("1") / Decimal(str(idx + 1))
            campaign = self._pick_campaign_for_product(product=product, campaigns=campaigns)
            boost = Decimal("0")
            campaign_id = None
            if campaign:
                normalized_bid = min(self._decimal(campaign.bid) / self.config.max_bid, Decimal("1"))
                boost = min(self.config.max_boost, normalized_bid * self.config.max_boost)
                campaign_id = str(campaign.id)
            final_score = base_score * (Decimal("1") + boost)
            ranked.append(
                {
                    "product": product,
                    "base_score": base_score,
                    "final_score": final_score,
                    "campaign_id": campaign_id,
                    "boost": boost,
                }
            )
        ranked.sort(key=lambda item: item["final_score"], reverse=True)
        sponsored = 0
        results: list[dict] = []
        for item in ranked:
            sponsored_flag = False
            sponsored_badge = None
            campaign_id = item["campaign_id"]
            if campaign_id and sponsored < self.config.sponsored_slots:
                sponsored_flag = True
                sponsored_badge = "Реклама"
                sponsored += 1
            results.append(
                {
                    "product": item["product"],
                    "sponsored": sponsored_flag,
                    "sponsored_badge": sponsored_badge,
                    "sponsored_campaign_id": campaign_id if sponsored_flag else None,
                }
            )
        self._log_impressions(
            items=results,
            tenant_id=tenant_id,
            client_id=client_id,
            user_id=user_id,
            context=context,
        )
        return results

    def _log_impressions(
        self,
        *,
        items: list[dict],
        tenant_id: str | None,
        client_id: str | None,
        user_id: str | None,
        context: dict,
    ) -> None:
        for item in items:
            campaign_id = item.get("sponsored_campaign_id")
            if not campaign_id:
                continue
            product = item["product"]
            event_tenant_id = tenant_id
            if event_tenant_id is None:
                campaign = self.get_campaign(campaign_id)
                event_tenant_id = str(campaign.tenant_id) if campaign else None
            if event_tenant_id is None:
                continue
            event = SponsoredEvent(
                id=new_uuid_str(),
                tenant_id=event_tenant_id,
                campaign_id=campaign_id,
                partner_id=product.partner_id,
                client_id=client_id,
                user_id=user_id,
                product_id=product.id,
                event_type=SponsoredEventType.IMPRESSION,
                event_ts=self._now(),
                context=context,
                meta=None,
            )
            self.db.add(event)
            self._audit(
                event_type="SPONSORED_IMPRESSION_LOGGED",
                entity_type="sponsored_event",
                entity_id=str(event.id),
                action="SPONSORED_IMPRESSION_LOGGED",
                external_refs={"campaign_id": campaign_id, "product_id": str(product.id)},
            )
        self.db.flush()

    def log_event(
        self,
        *,
        tenant_id: str | None,
        client_id: str | None,
        user_id: str | None,
        payload: dict,
    ) -> SponsoredEvent:
        campaign_id = payload["campaign_id"]
        product_id = payload.get("product_id")
        event_type = SponsoredEventType(payload["event_type"])
        if event_type == SponsoredEventType.CLICK:
            session_id = (payload.get("context") or {}).get("session_id")
            if session_id and product_id:
                window_start = self._now() - timedelta(minutes=self.config.click_dedupe_minutes)
                candidates = (
                    self.db.query(SponsoredEvent)
                    .filter(
                        SponsoredEvent.campaign_id == campaign_id,
                        SponsoredEvent.product_id == product_id,
                        SponsoredEvent.event_type == SponsoredEventType.CLICK,
                        SponsoredEvent.event_ts >= window_start,
                    )
                    .order_by(SponsoredEvent.event_ts.desc())
                    .limit(20)
                    .all()
                )
                existing = next(
                    (event for event in candidates if (event.context or {}).get("session_id") == session_id),
                    None,
                )
                if existing:
                    return existing
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("campaign_not_found")
        resolved_tenant_id = tenant_id or str(campaign.tenant_id)
        event = SponsoredEvent(
            id=new_uuid_str(),
            tenant_id=resolved_tenant_id,
            campaign_id=campaign_id,
            partner_id=campaign.partner_id,
            client_id=client_id,
            user_id=user_id,
            product_id=product_id,
            event_type=event_type,
            event_ts=self._now(),
            context=payload.get("context", {}),
            meta=payload.get("meta"),
        )
        self.db.add(event)
        self._audit(
            event_type=f"SPONSORED_{event_type.value}_LOGGED",
            entity_type="sponsored_event",
            entity_id=str(event.id),
            action=f"SPONSORED_{event_type.value}_LOGGED",
            external_refs={"campaign_id": campaign_id, "product_id": product_id},
        )
        self.db.flush()
        return event

    def _attribute_campaign_for_order(
        self,
        *,
        tenant_id: str | None,
        product_id: str,
        partner_id: str,
        client_id: str | None,
    ) -> SponsoredCampaign | None:
        window_start = self._now() - timedelta(days=self.config.attribution_window_days)
        query = self.db.query(SponsoredEvent).filter(
            SponsoredEvent.event_type == SponsoredEventType.CLICK,
            SponsoredEvent.product_id == product_id,
            SponsoredEvent.partner_id == partner_id,
            SponsoredEvent.event_ts >= window_start,
        )
        if tenant_id:
            query = query.filter(SponsoredEvent.tenant_id == tenant_id)
        if client_id:
            query = query.filter(SponsoredEvent.client_id == client_id)
        event = query.order_by(SponsoredEvent.event_ts.desc()).first()
        if not event:
            return None
        campaign = self.get_campaign(str(event.campaign_id))
        if not campaign or SponsoredCampaignObjective(str(campaign.objective)) != SponsoredCampaignObjective.CPA:
            return None
        self._audit(
            event_type="SPONSORED_ATTRIBUTED",
            entity_type="sponsored_campaign",
            entity_id=str(campaign.id),
            action="SPONSORED_ATTRIBUTED",
            external_refs={"order_product_id": product_id, "click_event_id": str(event.id)},
        )
        return campaign

    def charge_cpa_for_order_paid(
        self,
        *,
        order_id: str,
        paid_amount: Decimal,
        currency: str,
    ) -> SponsoredSpendLedger | None:
        order = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()
        if not order:
            raise ValueError("order_not_found")
        campaign = self._attribute_campaign_for_order(
            tenant_id=str(self.request_ctx.tenant_id) if self.request_ctx and self.request_ctx.tenant_id is not None else None,
            product_id=str(order.product_id),
            partner_id=str(order.partner_id),
            client_id=str(order.client_id) if order.client_id else None,
        )
        if not campaign:
            return None
        if not self._is_active(campaign):
            return None
        existing = (
            self.db.query(SponsoredSpendLedger)
            .filter(
                SponsoredSpendLedger.spend_type == SponsoredSpendType.CPA_ORDER,
                SponsoredSpendLedger.ref_id == order_id,
                SponsoredSpendLedger.direction == SponsoredSpendDirection.DEBIT,
            )
            .one_or_none()
        )
        if existing:
            return existing
        remaining_budget = self._remaining_budget(campaign)
        remaining_daily = self._remaining_daily_cap(campaign)
        amount = min(self._decimal(campaign.bid), remaining_budget)
        if remaining_daily is not None:
            amount = min(amount, remaining_daily)
        if amount <= 0:
            if campaign.status != SponsoredCampaignStatus.EXHAUSTED:
                self.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus.EXHAUSTED, reason="budget_exhausted")
            return None
        ledger = SponsoredSpendLedger(
            id=new_uuid_str(),
            tenant_id=campaign.tenant_id,
            campaign_id=campaign.id,
            partner_id=campaign.partner_id,
            spend_type=SponsoredSpendType.CPA_ORDER,
            amount=amount,
            currency=currency,
            ref_type="ORDER",
            ref_id=order_id,
            direction=SponsoredSpendDirection.DEBIT,
            created_at=self._now(),
        )
        self.db.add(ledger)
        campaign.spent_budget = self._decimal(campaign.spent_budget) + amount
        self._audit(
            event_type="SPONSORED_CHARGED",
            entity_type="sponsored_spend_ledger",
            entity_id=str(ledger.id),
            action="SPONSORED_CHARGED",
            external_refs={"order_id": order_id, "campaign_id": str(campaign.id)},
        )
        if self._remaining_budget(campaign) <= 0:
            if campaign.status != SponsoredCampaignStatus.EXHAUSTED:
                self.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus.EXHAUSTED, reason="budget_exhausted")
                self._audit(
                    event_type="SPONSORED_BUDGET_STATUS_CHANGED",
                    entity_type="sponsored_campaign",
                    entity_id=str(campaign.id),
                    action="SPONSORED_BUDGET_STATUS_CHANGED",
                    after={"status": campaign.status},
                )
        conversion = SponsoredEvent(
            id=new_uuid_str(),
            tenant_id=campaign.tenant_id,
            campaign_id=campaign.id,
            partner_id=campaign.partner_id,
            client_id=order.client_id,
            user_id=None,
            product_id=order.product_id,
            event_type=SponsoredEventType.CONVERSION,
            event_ts=self._now(),
            context={"order_id": order_id},
            meta={"paid_amount": str(paid_amount), "currency": currency},
        )
        self.db.add(conversion)
        self.db.flush()
        return ledger

    def reverse_cpa_for_refund(
        self,
        *,
        order_id: str,
        refunded_amount: Decimal,
        paid_amount: Decimal,
        currency: str,
    ) -> SponsoredSpendLedger | None:
        debit = (
            self.db.query(SponsoredSpendLedger)
            .filter(
                SponsoredSpendLedger.ref_id == order_id,
                SponsoredSpendLedger.spend_type == SponsoredSpendType.CPA_ORDER,
                SponsoredSpendLedger.direction == SponsoredSpendDirection.DEBIT,
            )
            .one_or_none()
        )
        if not debit:
            return None
        existing_credit = (
            self.db.query(SponsoredSpendLedger)
            .filter(
                SponsoredSpendLedger.ref_id == order_id,
                SponsoredSpendLedger.spend_type == SponsoredSpendType.CPA_ORDER,
                SponsoredSpendLedger.direction == SponsoredSpendDirection.CREDIT,
            )
            .one_or_none()
        )
        if existing_credit:
            return existing_credit
        ratio = Decimal("1")
        if paid_amount > 0:
            ratio = min(self._decimal(refunded_amount) / self._decimal(paid_amount), Decimal("1"))
        credit_amount = (self._decimal(debit.amount) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if credit_amount <= 0:
            return None
        campaign = self.get_campaign(str(debit.campaign_id))
        credit = SponsoredSpendLedger(
            id=new_uuid_str(),
            tenant_id=debit.tenant_id,
            campaign_id=debit.campaign_id,
            partner_id=debit.partner_id,
            spend_type=debit.spend_type,
            amount=credit_amount,
            currency=currency,
            ref_type="ORDER",
            ref_id=order_id,
            direction=SponsoredSpendDirection.CREDIT,
            reversal_of=debit.id,
            created_at=self._now(),
        )
        self.db.add(credit)
        if campaign:
            campaign.spent_budget = max(self._decimal(campaign.spent_budget) - credit_amount, Decimal("0"))
            if campaign.status == SponsoredCampaignStatus.EXHAUSTED and self._remaining_budget(campaign) > 0:
                if self._in_schedule(campaign):
                    self.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus.ACTIVE, reason="budget_restored")
        self._audit(
            event_type="SPONSORED_REVERSED",
            entity_type="sponsored_spend_ledger",
            entity_id=str(credit.id),
            action="SPONSORED_REVERSED",
            external_refs={"order_id": order_id, "reversal_of": str(debit.id)},
        )
        self.db.flush()
        return credit
