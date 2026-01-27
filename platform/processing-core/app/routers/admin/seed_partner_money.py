from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.partner import Partner
from app.models.partner_legal import PartnerLegalDetails
from app.schemas.admin.seed_partner_money import PartnerMoneySeedRequest, PartnerMoneySeedResponse

router = APIRouter(prefix="/seed", tags=["admin-seed"])


def _is_dev_env() -> bool:
    env = (os.getenv("NEFT_ENV") or "local").lower()
    return env in {"local", "dev", "development", "test"}


def _demo_org_id() -> str:
    return os.getenv("NEFT_DEMO_ORG_ID") or os.getenv("DEMO_ORG_ID") or "1"


@router.post("/partner-money", response_model=PartnerMoneySeedResponse, status_code=status.HTTP_200_OK)
def seed_partner_money(
    payload: PartnerMoneySeedRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> PartnerMoneySeedResponse:
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="not_found")

    partner_org_id = _demo_org_id()
    normalized_email = payload.email.strip().lower()
    created = False
    try:
        partner = db.query(Partner).filter(Partner.id == partner_org_id).one_or_none()
        if partner is None:
            partner = Partner(
                id=partner_org_id,
                name=payload.org_name.strip(),
                type="aggregator",
                allowed_ips=[],
                token=f"seed-{partner_org_id}",
                status="active",
            )
            db.add(partner)
            created = True
        else:
            partner.name = payload.org_name.strip() or partner.name
            partner.status = "active"

        details = db.query(PartnerLegalDetails).filter(PartnerLegalDetails.partner_id == partner_org_id).one_or_none()
        if details is None:
            details = PartnerLegalDetails(partner_id=partner_org_id, inn=payload.inn.strip())
            db.add(details)
        elif payload.inn.strip():
            details.inn = payload.inn.strip()

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={"error": "seed_failed", "reason_code": "SEED_FAILED", "message": str(exc)},
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={"error": "seed_failed", "reason_code": "SEED_FAILED", "message": str(exc)},
        ) from exc

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return PartnerMoneySeedResponse(
        partner_org_id=str(partner_org_id),
        partner_email=normalized_email,
    )
