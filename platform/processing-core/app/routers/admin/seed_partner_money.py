from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import MetaData, Table, inspect, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.models.partner import Partner
from app.models.partner_finance import (
    PartnerAccount,
    PartnerPayoutRequest,
    PartnerPayoutRequestStatus,
)
from app.models.partner_management import PartnerUserRole
from app.models.partner_legal import (
    PartnerLegalDetails,
    PartnerLegalProfile,
    PartnerLegalStatus,
    PartnerLegalType,
    PartnerTaxRegime,
)
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.schemas.admin.seed_partner_money import PartnerMoneySeedRequest, PartnerMoneySeedResponse
from app.services.bootstrap import _lookup_auth_user_id
from app.services.entitlements_v2_service import get_org_entitlements_snapshot

router = APIRouter(prefix="/seed", tags=["admin-seed"])
DEFAULT_DEMO_PARTNER_ORG_UUID = "00000000-0000-0000-0000-000000000001"
DEFAULT_DEMO_FINANCE_ORG_ID = 1
_PARTNER_FINANCE_FEATURES = (
    "feature.partner.core",
    "feature.partner.settlements",
    "feature.partner.payouts",
)
_PARTNER_MARKETPLACE_FEATURES = (
    "feature.partner.catalog",
    "feature.partner.pricing",
    "feature.partner.orders",
    "feature.partner.analytics",
)
logger = logging.getLogger(__name__)


def _is_dev_env() -> bool:
    env = (os.getenv("NEFT_ENV") or "local").lower()
    return env in {"local", "dev", "development", "test"}


def _demo_org_id() -> str:
    raw = (os.getenv("NEFT_DEMO_ORG_ID") or os.getenv("DEMO_ORG_ID") or "").strip()
    if not raw or raw == "1":
        return DEFAULT_DEMO_PARTNER_ORG_UUID
    try:
        return str(UUID(raw))
    except ValueError:
        return str(uuid5(NAMESPACE_URL, f"neft-demo-partner-org:{raw}"))


def _demo_finance_org_id() -> int:
    raw = (
        os.getenv("NEFT_DEMO_FINANCE_ORG_ID")
        or os.getenv("NEFT_BOOTSTRAP_ORG_ID")
        or os.getenv("NEFT_DEMO_ORG_NUM")
        or str(DEFAULT_DEMO_FINANCE_ORG_ID)
    ).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_DEMO_FINANCE_ORG_ID


def _bind(db: Session):
    try:
        return db.connection()
    except Exception:
        return db.get_bind()


def _table(db: Session, name: str) -> Table:
    bind = _bind(db)
    try:
        return Table(name, MetaData(), autoload_with=bind, schema=DB_SCHEMA)
    except Exception:
        if bind.dialect.name == "postgresql":
            raise
        return Table(name, MetaData(), autoload_with=bind)


def _table_exists(db: Session, name: str) -> bool:
    bind = _bind(db)
    try:
        inspector = inspect(bind)
        if inspector.has_table(name, schema=DB_SCHEMA):
            return True
        if bind.dialect.name == "postgresql":
            return False
        return inspector.has_table(name)
    except Exception:
        return False


def _column_names(table: Table) -> set[str]:
    return {column.name for column in table.c}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_finance_org_role(db: Session, *, finance_org_id: int) -> None:
    if not _table_exists(db, "orgs"):
        return
    orgs = _table(db, "orgs")
    columns = _column_names(orgs)
    if "id" not in columns or "roles" not in columns:
        return
    row = db.execute(select(orgs).where(orgs.c.id == finance_org_id)).mappings().first()
    if not row:
        now = _now()
        values = {
            "id": finance_org_id,
            "roles": ["PARTNER"],
        }
        if "name" in columns:
            values["name"] = "demo-partner-finance"
        if "status" in columns:
            values["status"] = "ACTIVE"
        if "created_at" in columns:
            values["created_at"] = now
        if "updated_at" in columns:
            values["updated_at"] = now
        db.execute(insert(orgs).values(**values))
        return
    existing_roles = row.get("roles") or []
    if isinstance(existing_roles, str):
        existing_roles = [existing_roles]
    normalized = {str(role).upper() for role in existing_roles if role}
    normalized.add("PARTNER")
    db.execute(update(orgs).where(orgs.c.id == finance_org_id).values(roles=sorted(normalized)))


def _ensure_finance_org_overrides(db: Session, *, finance_org_id: int) -> None:
    required_tables = {"org_subscriptions", "org_subscription_overrides"}
    if not all(_table_exists(db, name) for name in required_tables):
        return
    org_subscriptions = _table(db, "org_subscriptions")
    overrides = _table(db, "org_subscription_overrides")
    subscription = (
        db.execute(select(org_subscriptions).where(org_subscriptions.c.org_id == finance_org_id))
        .mappings()
        .first()
    )
    if not subscription:
        return
    override_columns = _column_names(overrides)
    subscription_id = subscription.get("id")
    now = _now()
    for feature_key in (*_PARTNER_FINANCE_FEATURES, *_PARTNER_MARKETPLACE_FEATURES):
        existing = (
            db.execute(
                select(overrides).where(
                    overrides.c.org_subscription_id == subscription_id,
                    overrides.c.feature_key == feature_key,
                )
            )
            .mappings()
            .first()
        )
        values = {
            "org_subscription_id": subscription_id,
            "feature_key": feature_key,
            "availability": "ENABLED",
            "limits_json": None,
            "updated_at": now,
        }
        if "created_at" in override_columns:
            values["created_at"] = now
        values = {key: value for key, value in values.items() if key in override_columns}
        if existing:
            db.execute(
                update(overrides)
                .where(
                    overrides.c.org_subscription_id == subscription_id,
                    overrides.c.feature_key == feature_key,
                )
                .values(**values)
            )
            continue
        db.execute(insert(overrides).values(**values))


def _ensure_partner_legal_alias(
    db: Session,
    *,
    partner_id: str,
    legal_name: str,
    inn: str,
) -> None:
    profile = db.query(PartnerLegalProfile).filter(PartnerLegalProfile.partner_id == partner_id).one_or_none()
    if profile is None:
        profile = PartnerLegalProfile(
            partner_id=partner_id,
            legal_type=PartnerLegalType.LEGAL_ENTITY,
            country="RU",
            tax_residency="RU",
            tax_regime=PartnerTaxRegime.OSNO,
            vat_applicable=True,
            vat_rate=20,
            legal_status=PartnerLegalStatus.VERIFIED,
        )
        db.add(profile)
    else:
        profile.legal_type = PartnerLegalType.LEGAL_ENTITY
        profile.country = profile.country or "RU"
        profile.tax_residency = profile.tax_residency or "RU"
        profile.tax_regime = profile.tax_regime or PartnerTaxRegime.OSNO
        profile.vat_applicable = True
        profile.vat_rate = profile.vat_rate if profile.vat_rate is not None else 20
        profile.legal_status = PartnerLegalStatus.VERIFIED

    details = db.query(PartnerLegalDetails).filter(PartnerLegalDetails.partner_id == partner_id).one_or_none()
    if details is None:
        details = PartnerLegalDetails(partner_id=partner_id)
        db.add(details)
    details.legal_name = legal_name or details.legal_name
    details.inn = inn or details.inn
    details.kpp = details.kpp or "770101001"
    details.ogrn = details.ogrn or "1027700132195"
    details.bank_account = details.bank_account or "40702810900000000001"
    details.bank_bic = details.bank_bic or "044525225"
    details.bank_name = details.bank_name or "Demo Bank"


def _seed_demo_finance_access(
    db: Session,
    *,
    finance_org_id: int,
    partner_storage_id: str,
    legal_name: str,
    inn: str,
) -> None:
    _ensure_finance_org_role(db, finance_org_id=finance_org_id)
    _ensure_finance_org_overrides(db, finance_org_id=finance_org_id)
    _ensure_partner_legal_alias(db, partner_id=partner_storage_id, legal_name=legal_name, inn=inn)
    if str(finance_org_id) != str(partner_storage_id):
        _ensure_partner_legal_alias(db, partner_id=str(finance_org_id), legal_name=legal_name, inn=inn)
    try:
        get_org_entitlements_snapshot(db, org_id=finance_org_id, force_new_version=True)
    except Exception:
        # Dev seed must stay additive and tolerate partial local schemas.
        return


def _ensure_demo_settlement_snapshot(
    db: Session,
    *,
    partner_id: str,
    currency: str = "RUB",
) -> None:
    if not partner_id:
        return
    try:
        UUID(str(partner_id))
    except (TypeError, ValueError):
        return

    period = (
        db.query(SettlementPeriod)
        .filter(
            SettlementPeriod.partner_id == partner_id,
            SettlementPeriod.currency == currency,
        )
        .order_by(SettlementPeriod.period_end.desc())
        .first()
    )
    if period is not None:
        return

    now = _now()
    db.add(
        SettlementPeriod(
            partner_id=partner_id,
            currency=currency,
            period_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            period_end=now,
            status=SettlementPeriodStatus.APPROVED,
            total_gross=Decimal("12000.0000"),
            total_fees=Decimal("0"),
            total_refunds=Decimal("0"),
            net_amount=Decimal("12000.0000"),
            approved_at=now,
            snapshot_payload={
                "source": "seed_partner_money",
                "mode": "dev_compat",
            },
        )
    )


def _normalize_demo_partner_payout_state(
    db: Session,
    *,
    partner_ids: tuple[str, ...],
) -> None:
    normalized_ids = tuple({str(item) for item in partner_ids if item})
    if not normalized_ids:
        return

    aged_at = _now() - timedelta(days=8)
    released_amounts: dict[tuple[str, str], Decimal] = {}
    payouts = (
        db.query(PartnerPayoutRequest)
        .filter(PartnerPayoutRequest.partner_org_id.in_(normalized_ids))
        .order_by(PartnerPayoutRequest.created_at.desc())
        .all()
    )
    for payout in payouts:
        key = (str(payout.partner_org_id), str(payout.currency or "RUB"))
        if payout.status in {
            PartnerPayoutRequestStatus.REQUESTED,
            PartnerPayoutRequestStatus.APPROVED,
        }:
            released_amounts[key] = released_amounts.get(key, Decimal("0")) + Decimal(payout.amount or 0)
            payout.status = PartnerPayoutRequestStatus.REJECTED
            payout.processed_at = aged_at
        elif payout.processed_at is not None:
            payout.processed_at = aged_at
        payout.created_at = aged_at

    for (org_id, currency), amount in released_amounts.items():
        account = (
            db.query(PartnerAccount)
            .filter(
                PartnerAccount.org_id == org_id,
                PartnerAccount.currency == currency,
            )
            .one_or_none()
        )
        if account is None:
            continue
        blocked = Decimal(account.balance_blocked or 0)
        release = min(blocked, amount)
        if release <= 0:
            continue
        account.balance_blocked = blocked - release
        account.balance_available = Decimal(account.balance_available or 0) + release


def _ensure_partner_user_binding(
    db: Session,
    *,
    partner_id: str,
    email: str,
) -> None:
    if not partner_id or not email or not _table_exists(db, "partner_user_roles"):
        return

    resolved_user_id = _lookup_auth_user_id(email, logger)
    if not resolved_user_id:
        return

    rows = db.query(PartnerUserRole).filter(PartnerUserRole.user_id == str(resolved_user_id)).all()
    if rows:
        primary_row = rows[0]
        primary_row.partner_id = str(partner_id)
        primary_row.roles = ["PARTNER_OWNER"]
        for duplicate in rows[1:]:
            db.delete(duplicate)
        return

    db.add(
        PartnerUserRole(
            partner_id=str(partner_id),
            user_id=str(resolved_user_id),
            roles=["PARTNER_OWNER"],
        )
    )


@router.post("/partner-money", response_model=PartnerMoneySeedResponse, status_code=status.HTTP_200_OK)
def seed_partner_money(
    payload: PartnerMoneySeedRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> PartnerMoneySeedResponse:
    if not _is_dev_env():
        raise HTTPException(status_code=404, detail="not_found")

    partner_org_id = _demo_org_id()
    finance_org_id = _demo_finance_org_id()
    normalized_email = payload.email.strip().lower()
    normalized_org_name = payload.org_name.strip()
    normalized_inn = payload.inn.strip()
    partner_code = f"demo-partner-{str(partner_org_id).replace('-', '')[:12]}"
    created = False
    try:
        partner = db.query(Partner).filter(Partner.code == partner_code).one_or_none()
        if partner is None:
            partner = Partner(
                id=str(partner_org_id),
                code=partner_code,
                legal_name=normalized_org_name,
                partner_type="OTHER",
                name=normalized_org_name,
                brand_name=normalized_org_name,
                inn=normalized_inn or None,
                type="aggregator",
                allowed_ips=[],
                token=f"seed-{partner_org_id}",
                contacts={"email": normalized_email},
                status="ACTIVE",
            )
            db.add(partner)
            created = True
        else:
            partner.code = partner.code or partner_code
            partner.legal_name = normalized_org_name or partner.legal_name
            partner.partner_type = partner.partner_type or "OTHER"
            partner.name = normalized_org_name or partner.name
            partner.brand_name = partner.brand_name or normalized_org_name
            partner.inn = normalized_inn or partner.inn
            partner.contacts = partner.contacts or {"email": normalized_email}
            partner.status = "ACTIVE"

        partner_storage_id = str(partner.id)

        _seed_demo_finance_access(
            db,
            finance_org_id=finance_org_id,
            partner_storage_id=partner_storage_id,
            legal_name=normalized_org_name,
            inn=normalized_inn,
        )
        _ensure_partner_user_binding(
            db,
            partner_id=partner_storage_id,
            email=normalized_email,
        )
        _normalize_demo_partner_payout_state(
            db,
            partner_ids=(partner_storage_id, str(finance_org_id)),
        )
        _ensure_demo_settlement_snapshot(db, partner_id=partner_storage_id)
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
        partner_org_id=str(partner.id),
        partner_email=normalized_email,
    )
