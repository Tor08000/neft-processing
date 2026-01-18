from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import MetaData, Table, delete, insert, inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.schemas.commercial_admin import (
    CommercialAddonDisableRequest,
    CommercialAddonEnableRequest,
    CommercialAddonOut,
    CommercialOrgInfo,
    CommercialOrgRoleRequest,
    CommercialOrgRolesResponse,
    CommercialOrgStateOut,
    CommercialOverrideOut,
    CommercialOverrideUpsertRequest,
    CommercialPlanChangeRequest,
    CommercialRecomputeRequest,
    CommercialRecomputeResponse,
    CommercialSnapshotOut,
    CommercialStatusChangeRequest,
    CommercialSubscription,
)
from app.services.audit_service import AuditService, request_context_from_request
from app.services.entitlements_v2_service import get_org_entitlements_snapshot

router = APIRouter(prefix="/commercial", tags=["commercial-admin"])

READ_ROLES = {"NEFT_SUPERADMIN", "NEFT_FINANCE", "NEFT_SUPPORT", "NEFT_SALES"}
WRITE_ROLES = {"NEFT_SUPERADMIN", "NEFT_FINANCE", "NEFT_SALES"}


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    inspector = inspect(db.get_bind())
    return inspector.has_table(name, schema=DB_SCHEMA)


def _extract_roles(token: dict) -> set[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role:
        roles.append(role)
    return {str(item).upper() for item in roles}


def _ensure_role(token: dict, *, write: bool) -> None:
    allowed = WRITE_ROLES if write else READ_ROLES
    if not _extract_roles(token).intersection(allowed):
        raise HTTPException(status_code=403, detail="forbidden_admin_role")


def _load_subscription(db: Session, org_id: int) -> dict[str, Any]:
    if not _table_exists(db, "org_subscriptions"):
        raise HTTPException(status_code=404, detail="org_not_found")
    org_subscriptions = _table(db, "org_subscriptions")
    subscription = (
        db.execute(select(org_subscriptions).where(org_subscriptions.c.org_id == org_id))
        .mappings()
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="org_not_found")
    return dict(subscription)


def _load_plan(db: Session, *, plan_code: str, plan_version: int) -> dict[str, Any]:
    if not _table_exists(db, "subscription_plans"):
        raise HTTPException(status_code=404, detail="plan_not_found")
    subscription_plans = _table(db, "subscription_plans")
    plan = (
        db.execute(
            select(subscription_plans).where(
                subscription_plans.c.code == plan_code,
                subscription_plans.c.version == plan_version,
            )
        )
        .mappings()
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="plan_not_found")
    return dict(plan)


def _load_addon(db: Session, addon_code: str) -> dict[str, Any]:
    if not _table_exists(db, "addons"):
        raise HTTPException(status_code=404, detail="addon_not_found")
    addons = _table(db, "addons")
    addon = (
        db.execute(select(addons).where(addons.c.code == addon_code)).mappings().first()
    )
    if not addon:
        raise HTTPException(status_code=404, detail="addon_not_found")
    return dict(addon)


def _validate_feature_key(db: Session, feature_key: str) -> None:
    if not _table_exists(db, "subscription_plan_features"):
        raise HTTPException(status_code=404, detail="invalid_feature_key")
    plan_features = _table(db, "subscription_plan_features")
    existing = (
        db.execute(select(plan_features.c.feature_key).where(plan_features.c.feature_key == feature_key))
        .mappings()
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="invalid_feature_key")


def _load_snapshot(db: Session, org_id: int) -> CommercialSnapshotOut | None:
    if not _table_exists(db, "org_entitlements_snapshot"):
        return None
    snapshots = _table(db, "org_entitlements_snapshot")
    latest = (
        db.execute(
            select(snapshots.c.hash, snapshots.c.computed_at, snapshots.c.version)
            .where(snapshots.c.org_id == org_id)
            .order_by(snapshots.c.computed_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not latest:
        return None
    return CommercialSnapshotOut(
        hash=latest.get("hash"),
        computed_at=latest.get("computed_at"),
        version=latest.get("version"),
    )


def _latest_snapshot_version(db: Session, org_id: int) -> int:
    snapshot = _load_snapshot(db, org_id)
    return snapshot.version or 1 if snapshot else 1


def _build_org_info(db: Session, org_id: int) -> CommercialOrgInfo:
    if _table_exists(db, "orgs"):
        orgs = _table(db, "orgs")
        record = (
            db.execute(select(orgs).where(orgs.c.id == org_id)).mappings().first()
        )
        if record:
            return CommercialOrgInfo(
                id=org_id,
                name=record.get("name"),
                status=record.get("status"),
            )
    return CommercialOrgInfo(id=org_id)


def _build_state(db: Session, org_id: int) -> CommercialOrgStateOut:
    subscription = _load_subscription(db, org_id)

    plan_code = None
    plan_version = None
    if _table_exists(db, "subscription_plans"):
        subscription_plans = _table(db, "subscription_plans")
        plan = (
            db.execute(select(subscription_plans).where(subscription_plans.c.id == subscription["plan_id"]))
            .mappings()
            .first()
        )
        if plan:
            plan_code = plan.get("code")
            plan_version = plan.get("version")

    support_plan_code = None
    if subscription.get("support_plan_id") and _table_exists(db, "support_plans"):
        support_plans = _table(db, "support_plans")
        support_plan = (
            db.execute(select(support_plans).where(support_plans.c.id == subscription["support_plan_id"]))
            .mappings()
            .first()
        )
        if support_plan:
            support_plan_code = support_plan.get("code")

    slo_tier_code = None
    if subscription.get("slo_tier_id") and _table_exists(db, "slo_tiers"):
        slo_tiers = _table(db, "slo_tiers")
        slo_tier = (
            db.execute(select(slo_tiers).where(slo_tiers.c.id == subscription["slo_tier_id"]))
            .mappings()
            .first()
        )
        if slo_tier:
            slo_tier_code = slo_tier.get("code")

    addons_out: list[CommercialAddonOut] = []
    if _table_exists(db, "org_subscription_addons") and _table_exists(db, "addons"):
        org_addons = _table(db, "org_subscription_addons")
        addons = _table(db, "addons")
        addon_rows = (
            db.execute(
                select(
                    addons.c.code,
                    org_addons.c.status,
                    org_addons.c.price_override,
                    org_addons.c.starts_at,
                    org_addons.c.ends_at,
                    org_addons.c.config_json,
                )
                .join(addons, addons.c.id == org_addons.c.addon_id)
                .where(org_addons.c.org_subscription_id == subscription["id"])
            )
            .mappings()
            .all()
        )
        addons_out = [
            CommercialAddonOut(
                addon_code=row.get("code"),
                status=row.get("status"),
                price_override=row.get("price_override"),
                starts_at=row.get("starts_at"),
                ends_at=row.get("ends_at"),
                config_json=row.get("config_json"),
            )
            for row in addon_rows
        ]

    overrides_out: list[CommercialOverrideOut] = []
    if _table_exists(db, "org_subscription_overrides"):
        overrides = _table(db, "org_subscription_overrides")
        override_rows = (
            db.execute(
                select(
                    overrides.c.feature_key,
                    overrides.c.availability,
                    overrides.c.limits_json,
                ).where(overrides.c.org_subscription_id == subscription["id"])
            )
            .mappings()
            .all()
        )
        overrides_out = [
            CommercialOverrideOut(
                feature_key=row.get("feature_key"),
                availability=row.get("availability"),
                limits_json=row.get("limits_json"),
            )
            for row in override_rows
        ]

    snapshot = _load_snapshot(db, org_id)

    return CommercialOrgStateOut(
        org=_build_org_info(db, org_id),
        subscription=CommercialSubscription(
            plan_code=plan_code,
            plan_version=plan_version,
            status=subscription.get("status"),
            billing_cycle=subscription.get("billing_cycle"),
            support_plan=support_plan_code,
            slo_tier=slo_tier_code,
        ),
        addons=addons_out,
        overrides=overrides_out,
        entitlements_snapshot=snapshot,
    )


def _audit_event(
    db: Session,
    request: Request,
    token: dict,
    *,
    event_type: str,
    entity_id: str,
    before: dict | None,
    after: dict | None,
    reason: str | None,
    ) -> None:
    audit_service = AuditService(db)
    audit_service.audit(
        event_type=event_type,
        entity_type="org",
        entity_id=entity_id,
        action=event_type,
        before=before,
        after=after,
        reason=reason,
        request_ctx=request_context_from_request(request, token=token),
    )


def _normalize_org_roles(roles: Any) -> list[str]:
    if not roles:
        return []
    if isinstance(roles, str):
        roles = [roles]
    return sorted({str(role).upper() for role in roles if role})


def _load_org_roles(db: Session, org_id: int) -> list[str]:
    if not _table_exists(db, "orgs"):
        raise HTTPException(status_code=404, detail="org_roles_not_supported")
    orgs = _table(db, "orgs")
    if "roles" not in orgs.c:
        raise HTTPException(status_code=404, detail="org_roles_not_supported")
    record = db.execute(select(orgs.c.roles).where(orgs.c.id == org_id)).mappings().first()
    if not record:
        raise HTTPException(status_code=404, detail="org_not_found")
    return _normalize_org_roles(record.get("roles"))


def _save_org_roles(db: Session, *, org_id: int, roles: list[str]) -> None:
    orgs = _table(db, "orgs")
    update_values = {"roles": roles}
    if "updated_at" in orgs.c:
        update_values["updated_at"] = datetime.utcnow()
    db.execute(update(orgs).where(orgs.c.id == org_id).values(**update_values))
    db.commit()


def _audit_role_change(
    db: Session,
    *,
    request: Request,
    token: dict,
    org_id: int,
    before_roles: list[str],
    after_roles: list[str],
    action: str,
    reason: str | None,
) -> None:
    AuditService(db).audit(
        event_type="org_role_changed",
        entity_type="org",
        entity_id=str(org_id),
        action="org_role_changed",
        before={"roles": before_roles},
        after={"roles": after_roles, "action": action, "reason": reason},
        request_ctx=request_context_from_request(request, token=token),
    )


def _filter_columns(table: Table, values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in table.c}


@router.get("/orgs/{org_id}", response_model=CommercialOrgStateOut)
def get_commercial_state(
    org_id: int,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=False)
    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/roles/add", response_model=CommercialOrgRolesResponse)
def add_org_role(
    org_id: int,
    payload: CommercialOrgRoleRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgRolesResponse:
    _ensure_role(token, write=True)
    before_roles = _load_org_roles(db, org_id)
    role = payload.role.upper()
    after_roles = sorted({*before_roles, role})
    if after_roles != before_roles:
        _save_org_roles(db, org_id=org_id, roles=after_roles)
    _audit_role_change(
        db,
        request=request,
        token=token,
        org_id=org_id,
        before_roles=before_roles,
        after_roles=after_roles,
        action="add",
        reason=payload.reason,
    )
    get_org_entitlements_snapshot(db, org_id=org_id)
    return CommercialOrgRolesResponse(org_id=org_id, roles=after_roles)


@router.post("/orgs/{org_id}/roles/remove", response_model=CommercialOrgRolesResponse)
def remove_org_role(
    org_id: int,
    payload: CommercialOrgRoleRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgRolesResponse:
    _ensure_role(token, write=True)
    before_roles = _load_org_roles(db, org_id)
    role = payload.role.upper()
    after_roles = [item for item in before_roles if item != role]
    if after_roles != before_roles:
        _save_org_roles(db, org_id=org_id, roles=after_roles)
    _audit_role_change(
        db,
        request=request,
        token=token,
        org_id=org_id,
        before_roles=before_roles,
        after_roles=after_roles,
        action="remove",
        reason=payload.reason,
    )
    get_org_entitlements_snapshot(db, org_id=org_id)
    return CommercialOrgRolesResponse(org_id=org_id, roles=after_roles)


@router.post("/orgs/{org_id}/plan", response_model=CommercialOrgStateOut)
def change_plan(
    org_id: int,
    payload: CommercialPlanChangeRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)
    plan = _load_plan(db, plan_code=payload.plan_code, plan_version=payload.plan_version)

    before = {
        "plan_id": subscription.get("plan_id"),
        "billing_cycle": subscription.get("billing_cycle"),
        "status": subscription.get("status"),
    }

    org_subscriptions = _table(db, "org_subscriptions")
    update_values: dict[str, Any] = {
        "plan_id": plan["id"],
        "billing_cycle": payload.billing_cycle,
        "status": payload.status,
    }
    if payload.effective_at:
        if "effective_at" in org_subscriptions.c:
            update_values["effective_at"] = payload.effective_at
        elif "start_at" in org_subscriptions.c:
            update_values["start_at"] = payload.effective_at
        elif "starts_at" in org_subscriptions.c:
            update_values["starts_at"] = payload.effective_at

    db.execute(
        update(org_subscriptions)
        .where(org_subscriptions.c.id == subscription["id"])
        .values(**update_values)
    )

    after = {
        "plan_id": plan["id"],
        "plan_code": payload.plan_code,
        "plan_version": payload.plan_version,
        "billing_cycle": payload.billing_cycle,
        "status": payload.status,
    }

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_plan_changed",
        entity_id=str(org_id),
        before=before,
        after=after,
        reason=payload.reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/addons/enable", response_model=CommercialOrgStateOut)
def enable_addon(
    org_id: int,
    payload: CommercialAddonEnableRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)
    addon = _load_addon(db, payload.addon_code)

    org_addons = _table(db, "org_subscription_addons")
    before_row = (
        db.execute(
            select(org_addons).where(
                org_addons.c.org_subscription_id == subscription["id"],
                org_addons.c.addon_id == addon["id"],
            )
        )
        .mappings()
        .first()
    )

    values: dict[str, Any] = _filter_columns(
        org_addons,
        {
            "org_subscription_id": subscription["id"],
            "addon_id": addon["id"],
            "status": payload.status,
            "price_override": payload.price_override,
            "starts_at": payload.starts_at,
            "ends_at": payload.ends_at,
            "config_json": payload.config_json,
            "updated_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        },
    )

    stmt = pg_insert(org_addons).values(**values)
    update_values = _filter_columns(
        org_addons,
        {
            "status": payload.status,
            "price_override": payload.price_override,
            "starts_at": payload.starts_at,
            "ends_at": payload.ends_at,
            "config_json": payload.config_json,
            "updated_at": datetime.utcnow(),
        },
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["org_subscription_id", "addon_id"],
        set_=update_values,
    )
    db.execute(stmt)

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_addon_enabled",
        entity_id=str(org_id),
        before=dict(before_row) if before_row else None,
        after={
            "addon_code": payload.addon_code,
            "status": payload.status,
            "price_override": payload.price_override,
            "starts_at": payload.starts_at,
            "ends_at": payload.ends_at,
            "config_json": payload.config_json,
        },
        reason=payload.reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/addons/disable", response_model=CommercialOrgStateOut)
def disable_addon(
    org_id: int,
    payload: CommercialAddonDisableRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)
    addon = _load_addon(db, payload.addon_code)

    org_addons = _table(db, "org_subscription_addons")
    before_row = (
        db.execute(
            select(org_addons).where(
                org_addons.c.org_subscription_id == subscription["id"],
                org_addons.c.addon_id == addon["id"],
            )
        )
        .mappings()
        .first()
    )
    if before_row:
        update_values = _filter_columns(
            org_addons,
            {"status": "CANCELED", "updated_at": datetime.utcnow()},
        )
        db.execute(
            update(org_addons)
            .where(
                org_addons.c.org_subscription_id == subscription["id"],
                org_addons.c.addon_id == addon["id"],
            )
            .values(**update_values)
        )

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_addon_disabled",
        entity_id=str(org_id),
        before=dict(before_row) if before_row else None,
        after={"addon_code": payload.addon_code, "status": "CANCELED"},
        reason=payload.reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/overrides", response_model=CommercialOrgStateOut)
def upsert_override(
    org_id: int,
    payload: CommercialOverrideUpsertRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)
    _validate_feature_key(db, payload.feature_key)

    overrides = _table(db, "org_subscription_overrides")
    before_row = (
        db.execute(
            select(overrides).where(
                overrides.c.org_subscription_id == subscription["id"],
                overrides.c.feature_key == payload.feature_key,
            )
        )
        .mappings()
        .first()
    )

    values: dict[str, Any] = _filter_columns(
        overrides,
        {
            "org_subscription_id": subscription["id"],
            "feature_key": payload.feature_key,
            "availability": payload.availability,
            "limits_json": payload.limits_json,
            "updated_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        },
    )

    stmt = pg_insert(overrides).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["org_subscription_id", "feature_key"],
        set_=_filter_columns(
            overrides,
            {
                "availability": payload.availability,
                "limits_json": payload.limits_json,
                "updated_at": datetime.utcnow(),
            },
        ),
    )
    db.execute(stmt)

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_override_upserted",
        entity_id=str(org_id),
        before=dict(before_row) if before_row else None,
        after={
            "feature_key": payload.feature_key,
            "availability": payload.availability,
            "limits_json": payload.limits_json,
        },
        reason=payload.reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.delete("/orgs/{org_id}/overrides/{feature_key}", response_model=CommercialOrgStateOut)
def remove_override(
    org_id: int,
    feature_key: str,
    request: Request,
    reason: str | None = None,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)
    _validate_feature_key(db, feature_key)

    overrides = _table(db, "org_subscription_overrides")
    before_row = (
        db.execute(
            select(overrides).where(
                overrides.c.org_subscription_id == subscription["id"],
                overrides.c.feature_key == feature_key,
            )
        )
        .mappings()
        .first()
    )
    if before_row:
        db.execute(
            delete(overrides).where(
                overrides.c.org_subscription_id == subscription["id"],
                overrides.c.feature_key == feature_key,
            )
        )

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_override_removed",
        entity_id=str(org_id),
        before=dict(before_row) if before_row else None,
        after={"feature_key": feature_key},
        reason=reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/status", response_model=CommercialOrgStateOut)
def change_status(
    org_id: int,
    payload: CommercialStatusChangeRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialOrgStateOut:
    _ensure_role(token, write=True)
    subscription = _load_subscription(db, org_id)

    org_subscriptions = _table(db, "org_subscriptions")
    before = {"status": subscription.get("status")}

    db.execute(
        update(org_subscriptions)
        .where(org_subscriptions.c.id == subscription["id"])
        .values(status=payload.status)
    )

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_status_changed",
        entity_id=str(org_id),
        before=before,
        after={"status": payload.status},
        reason=payload.reason,
    )

    get_org_entitlements_snapshot(db, org_id=org_id)
    db.commit()

    return _build_state(db, org_id)


@router.post("/orgs/{org_id}/entitlements/recompute", response_model=CommercialRecomputeResponse)
def recompute_entitlements(
    org_id: int,
    payload: CommercialRecomputeRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CommercialRecomputeResponse:
    _ensure_role(token, write=True)
    _load_subscription(db, org_id)

    snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
    version = _latest_snapshot_version(db, org_id)

    _audit_event(
        db,
        request,
        token,
        event_type="commercial_entitlements_recomputed",
        entity_id=str(org_id),
        before=None,
        after={"hash": snapshot.hash, "version": version},
        reason=payload.reason,
    )

    db.commit()

    return CommercialRecomputeResponse(
        hash=snapshot.hash,
        computed_at=snapshot.computed_at,
        version=version,
    )
