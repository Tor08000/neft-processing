from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.client import Client
from app.models.contract_limits import ClientTariff, CommissionRule
from app.services.pricing_service import PriceQuote, get_effective_price


class TariffResolutionError(RuntimeError):
    """Raised when tariff resolution cannot provide a usable snapshot."""


def _as_decimal(value: Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _serialize_decimal(value: Decimal | None) -> Optional[str]:
    if value is None:
        return None
    normalized = value.normalize()
    # Avoid scientific notation for JSON friendliness
    return format(normalized, "f")


def _pick_client_tariff(
    db: Session,
    *,
    client_id: str | UUID,
    occurred_at: datetime,
) -> tuple[str, list[str]]:
    """Resolve tariff for client using assignment table or client fallback."""

    client_id_str = str(client_id)
    client_uuid: UUID | None = None
    try:
        client_uuid = UUID(client_id_str)
    except (TypeError, ValueError):
        client_uuid = None

    assignment = (
        db.query(ClientTariff)
        .filter(ClientTariff.client_id == client_id_str)
        .filter(or_(ClientTariff.valid_from.is_(None), ClientTariff.valid_from <= occurred_at))
        .filter(or_(ClientTariff.valid_to.is_(None), ClientTariff.valid_to >= occurred_at))
        .order_by(ClientTariff.priority.asc(), ClientTariff.valid_from.desc().nullslast())
        .first()
    )

    trace: list[str] = []
    if assignment:
        trace.append(f"client_tariff:{assignment.id}")
        return assignment.tariff_id, trace

    client = db.query(Client).filter(Client.id == (client_uuid or client_id_str)).first()
    if client and client.tariff_plan:
        trace.append("client.tariff_plan")
        return client.tariff_plan, trace

    raise TariffResolutionError("TARIFF_NOT_ASSIGNED")


def _pick_commission_rule(
    db: Session,
    *,
    tariff_id: str,
    product_id: str,
    occurred_at: datetime,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
) -> tuple[CommissionRule | None, list[str]]:
    """Pick commission rule with priority similar to pricing resolution."""

    query = (
        db.query(CommissionRule)
        .filter(CommissionRule.tariff_id == tariff_id)
        .filter(or_(CommissionRule.product_id.is_(None), CommissionRule.product_id == product_id))
        .filter(or_(CommissionRule.valid_from.is_(None), CommissionRule.valid_from <= occurred_at))
        .filter(or_(CommissionRule.valid_to.is_(None), CommissionRule.valid_to >= occurred_at))
    )

    trace: list[str] = []

    if azs_id is not None:
        scoped = (
            query.filter(CommissionRule.azs_id == azs_id)
            .order_by(CommissionRule.priority.asc(), CommissionRule.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            trace.append(f"commission.azs:{azs_id}")
            return scoped, trace

    if partner_id is not None:
        scoped = (
            query.filter(CommissionRule.partner_id == partner_id)
            .order_by(CommissionRule.priority.asc(), CommissionRule.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            trace.append(f"commission.partner:{partner_id}")
            return scoped, trace

    general = (
        query.filter(CommissionRule.partner_id.is_(None)).filter(CommissionRule.azs_id.is_(None))
        .order_by(CommissionRule.priority.asc(), CommissionRule.valid_from.desc().nullslast())
        .first()
    )
    if general:
        trace.append("commission.general")
    return general, trace


@dataclass
class CommissionSnapshot:
    platform_rate: Decimal
    partner_rate: Decimal | None
    promo_rate: Decimal | None
    source: str
    commission_rule_id: int | None

    def model_dump(self) -> dict:
        return {
            "platform_rate": _serialize_decimal(self.platform_rate),
            "partner_rate": _serialize_decimal(self.partner_rate),
            "promo_rate": _serialize_decimal(self.promo_rate),
            "source": self.source,
            "commission_rule_id": self.commission_rule_id,
        }


@dataclass
class TariffResolvedSnapshot:
    tariff_id: str
    tariff_price_id: int
    unit_price: Decimal
    currency: str
    commission: CommissionSnapshot
    taxes: list
    trace: list[str]

    def model_dump(self) -> dict:
        return {
            "tariff_id": self.tariff_id,
            "tariff_price_id": self.tariff_price_id,
            "unit_price": _serialize_decimal(self.unit_price),
            "currency": self.currency,
            "commission": self.commission.model_dump(),
            "taxes": self.taxes,
            "trace": self.trace,
        }


def resolve_tariff_snapshot(
    db: Session,
    *,
    client_id: str | UUID,
    partner_id: Optional[str],
    azs_id: Optional[str],
    product_id: str,
    occurred_at: datetime,
) -> TariffResolvedSnapshot:
    """
    Resolve tariff, price, and commission snapshot for a transaction context.

    The snapshot is designed to be persisted on the operation to make
    subsequent calculations independent of mutable tariff state.
    """

    tariff_id, tariff_trace = _pick_client_tariff(db, client_id=client_id, occurred_at=occurred_at)

    price_quote: PriceQuote = get_effective_price(
        db,
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        occurred_at=occurred_at,
    )
    trace: list[str] = tariff_trace + [f"price:{price_quote.tariff_price.id}"]

    rule, commission_trace = _pick_commission_rule(
        db,
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        occurred_at=occurred_at,
    )

    if rule:
        commission = CommissionSnapshot(
            platform_rate=_as_decimal(rule.platform_rate) or Decimal(settings.NEFT_COMMISSION_RATE),
            partner_rate=_as_decimal(rule.partner_rate),
            promo_rate=_as_decimal(rule.promo_rate),
            source="COMMISSION_RULE",
            commission_rule_id=rule.id,
        )
        trace.extend(commission_trace)
    else:
        commission = CommissionSnapshot(
            platform_rate=_as_decimal(settings.NEFT_COMMISSION_RATE) or Decimal("0"),
            partner_rate=None,
            promo_rate=None,
            source="DEFAULT_COMMISSION",
            commission_rule_id=None,
        )
        trace.append("commission.default")

    return TariffResolvedSnapshot(
        tariff_id=tariff_id,
        tariff_price_id=price_quote.tariff_price.id,
        unit_price=price_quote.client_price_per_liter,
        currency=price_quote.currency,
        commission=commission,
        taxes=[],
        trace=trace,
    )
