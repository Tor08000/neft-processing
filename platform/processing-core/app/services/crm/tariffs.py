from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMTariffPlan
from app.schemas.crm import CRMTariffCreate, CRMTariffUpdate
from app.services.crm import repository


def create_tariff(db: Session, *, payload: CRMTariffCreate) -> CRMTariffPlan:
    tariff = CRMTariffPlan(
        id=payload.id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        billing_period=payload.billing_period,
        base_fee_minor=payload.base_fee_minor,
        currency=payload.currency,
        features=payload.features,
        limits_defaults=payload.limits_defaults,
        definition=payload.definition,
    )
    return repository.add_tariff(db, tariff)


def update_tariff(db: Session, *, tariff: CRMTariffPlan, payload: CRMTariffUpdate) -> CRMTariffPlan:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tariff, field, value)
    return repository.update_tariff(db, tariff)


__all__ = ["create_tariff", "update_tariff"]
