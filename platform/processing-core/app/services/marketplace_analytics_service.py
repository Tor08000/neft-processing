from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderStatus


class MarketplaceAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _coalesce_decimal(value: object | None) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _apply_period_filters(self, query, *, date_from, date_to):
        if date_from:
            query = query.filter(MarketplaceOrder.created_at >= date_from)
        if date_to:
            query = query.filter(MarketplaceOrder.created_at <= date_to)
        return query

    def _revenue_expr(self):
        return func.coalesce(MarketplaceOrder.final_price, MarketplaceOrder.price, 0)

    def _commission_expr(self):
        return func.coalesce(MarketplaceOrder.commission, 0)

    def summary(self, *, partner_id: str, date_from=None, date_to=None) -> dict:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
        query = self._apply_period_filters(query, date_from=date_from, date_to=date_to)
        query = query.filter(MarketplaceOrder.status == MarketplaceOrderStatus.COMPLETED)
        orders_count, revenue, commission = (
            query.with_entities(
                func.count(MarketplaceOrder.id),
                func.coalesce(func.sum(self._revenue_expr()), 0),
                func.coalesce(func.sum(self._commission_expr()), 0),
            )
            .one()
        )
        revenue_value = self._coalesce_decimal(revenue)
        commission_value = self._coalesce_decimal(commission)
        avg_check = revenue_value / orders_count if orders_count else Decimal("0")
        return {
            "orders": orders_count,
            "revenue": revenue_value,
            "commission": commission_value,
            "avg_check": avg_check,
        }

    def product_stats(self, *, partner_id: str, date_from=None, date_to=None) -> list[dict]:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
        query = self._apply_period_filters(query, date_from=date_from, date_to=date_to)
        query = query.filter(MarketplaceOrder.status == MarketplaceOrderStatus.COMPLETED)
        rows = (
            query.with_entities(
                MarketplaceOrder.product_id,
                func.count(MarketplaceOrder.id),
                func.coalesce(func.sum(self._revenue_expr()), 0),
                func.coalesce(func.sum(self._commission_expr()), 0),
            )
            .group_by(MarketplaceOrder.product_id)
            .order_by(func.sum(self._revenue_expr()).desc())
            .all()
        )
        items = []
        for product_id, orders_count, revenue, commission in rows:
            revenue_value = self._coalesce_decimal(revenue)
            commission_value = self._coalesce_decimal(commission)
            avg_check = revenue_value / orders_count if orders_count else Decimal("0")
            items.append(
                {
                    "product_id": str(product_id),
                    "orders": orders_count,
                    "revenue": revenue_value,
                    "commission": commission_value,
                    "avg_check": avg_check,
                }
            )
        return items

    def client_stats(self, *, partner_id: str, date_from=None, date_to=None) -> dict:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
        query = self._apply_period_filters(query, date_from=date_from, date_to=date_to)
        query = query.filter(MarketplaceOrder.status == MarketplaceOrderStatus.COMPLETED)
        rows = (
            query.with_entities(
                MarketplaceOrder.client_id,
                func.count(MarketplaceOrder.id),
                func.coalesce(func.sum(self._revenue_expr()), 0),
            )
            .group_by(MarketplaceOrder.client_id)
            .all()
        )
        new_clients = 0
        repeat_clients = 0
        total_revenue = Decimal("0")
        for _, orders_count, revenue in rows:
            total_revenue += self._coalesce_decimal(revenue)
            if orders_count <= 1:
                new_clients += 1
            else:
                repeat_clients += 1
        total_clients = new_clients + repeat_clients
        ltv = total_revenue / total_clients if total_clients else Decimal("0")
        return {
            "new_clients": new_clients,
            "repeat_clients": repeat_clients,
            "ltv": ltv,
        }

    def conversion(self, *, partner_id: str, date_from=None, date_to=None) -> dict:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
        query = self._apply_period_filters(query, date_from=date_from, date_to=date_to)
        created_orders = query.count()
        completed_orders = query.filter(MarketplaceOrder.status == MarketplaceOrderStatus.COMPLETED).count()
        order_to_completed = None
        if created_orders:
            order_to_completed = completed_orders / created_orders
        return {
            "created_orders": created_orders,
            "completed_orders": completed_orders,
            "order_to_completed_rate": order_to_completed,
        }
