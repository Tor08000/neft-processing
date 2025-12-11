from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.contract_limits import TariffPrice


@dataclass
class PriceQuote:
    """Resolved price for a tariff/product combination."""

    client_price_per_liter: Decimal
    cost_price_per_liter: Decimal | None
    currency: str
    tariff_price: TariffPrice


def _to_decimal(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _pick_price(
    db: Session,
    *,
    tariff_id: str,
    product_id: str,
    occurred_at: datetime,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
) -> TariffPrice | None:
    query = (
        db.query(TariffPrice)
        .filter(TariffPrice.tariff_id == tariff_id)
        .filter(TariffPrice.product_id == product_id)
        .filter(or_(TariffPrice.valid_from.is_(None), TariffPrice.valid_from <= occurred_at))
        .filter(or_(TariffPrice.valid_to.is_(None), TariffPrice.valid_to >= occurred_at))
    )

    if azs_id is not None:
        scoped = (
            query.filter(TariffPrice.azs_id == azs_id)
            .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            return scoped

    if partner_id is not None:
        scoped = (
            query.filter(TariffPrice.partner_id == partner_id)
            .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            return scoped

    return (
        query.filter(TariffPrice.partner_id.is_(None)).filter(TariffPrice.azs_id.is_(None))
        .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
        .first()
    )


def get_effective_price(
    db: Session,
    *,
    tariff_id: str,
    product_id: str,
    occurred_at: datetime,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
) -> PriceQuote:
    """
    Resolve the most specific price for the provided context.

    Priority of resolution:
    1) AZS-specific price when ``azs_id`` is provided.
    2) Partner-scoped price when ``partner_id`` is provided.
    3) General tariff price (no partner/azs bindings).

    Within the scope, prices are ordered by ascending ``priority`` and then by
    the most recent ``valid_from`` value.
    """

    price = _pick_price(
        db,
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        occurred_at=occurred_at,
    )
    if not price:
        raise ValueError("PRICE_NOT_FOUND")

    return PriceQuote(
        client_price_per_liter=_to_decimal(price.price_per_liter),
        cost_price_per_liter=_to_decimal(price.cost_price_per_liter)
        if price.cost_price_per_liter is not None
        else None,
        currency=price.currency,
        tariff_price=price,
    )
