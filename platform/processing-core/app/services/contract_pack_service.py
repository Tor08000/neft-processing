from __future__ import annotations

import hashlib
import io
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import MetaData, Table, desc, inspect, insert, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.schema import DB_SCHEMA
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.s3_storage import S3Storage


CONTRACT_PACK_NAMESPACE = uuid.UUID("3f0c1a9f-8f57-4df1-bb11-0b7f1b56c1d9")


@dataclass(frozen=True)
class ContractPackPayload:
    contract_pack_id: str
    pack_hash: str
    object_key: str
    download_url: str
    entitlements_snapshot_hash: str


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    inspector = inspect(db.get_bind())
    return inspector.has_table(name, schema=DB_SCHEMA)


def _as_of_datetime(as_of: date) -> datetime:
    return datetime.combine(as_of, time.min, tzinfo=timezone.utc)


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _deterministic_contract_pack_id(
    *,
    org_id: int,
    as_of: date,
    entitlements_hash: str,
    format: str,
    language: str,
    include_pricing: bool,
    include_legal_terms: bool,
) -> str:
    seed = f"{org_id}:{as_of.isoformat()}:{entitlements_hash}:{format}:{language}:{include_pricing}:{include_legal_terms}"
    return str(uuid.uuid5(CONTRACT_PACK_NAMESPACE, seed))


def _resolve_pricing_record(
    db: Session,
    *,
    item_type: str,
    item_id: int,
    as_of: datetime,
) -> dict[str, Any] | None:
    pricing_catalog = _table(db, "pricing_catalog")
    record = (
        db.execute(
            select(pricing_catalog)
            .where(
                pricing_catalog.c.item_type == item_type,
                pricing_catalog.c.item_id == item_id,
                pricing_catalog.c.effective_from <= as_of,
                or_(pricing_catalog.c.effective_to.is_(None), pricing_catalog.c.effective_to > as_of),
            )
            .order_by(desc(pricing_catalog.c.effective_from))
            .limit(1)
        )
        .mappings()
        .first()
    )
    return dict(record) if record else None


def _build_zip(
    *,
    pdf_bytes: bytes,
    contract_json: bytes,
    entitlements_json: bytes,
    pricing_json: bytes,
    readme_text: str,
    as_of: date,
) -> bytes:
    buffer = io.BytesIO()
    zip_timestamp = (as_of.year, as_of.month, as_of.day, 0, 0, 0)
    with ZipFile(buffer, mode="w") as archive:
        for name, payload, content_type in [
            ("contract_specification.pdf", pdf_bytes, "application/pdf"),
            ("contract_specification.json", contract_json, "application/json"),
            ("entitlements_snapshot.json", entitlements_json, "application/json"),
            ("pricing_breakdown.json", pricing_json, "application/json"),
            ("README.txt", readme_text.encode("utf-8"), "text/plain"),
        ]:
            info = ZipInfo(filename=name, date_time=zip_timestamp)
            info.compress_type = ZIP_DEFLATED
            info.extra = b""
            info.comment = b""
            archive.writestr(info, payload)
    return buffer.getvalue()


def _pdf_line(pdf: canvas.Canvas, text: str, *, x: float, y: float) -> float:
    pdf.drawString(x, y, text)
    return y - 6 * mm


def _render_pdf(
    *,
    payload: dict[str, Any],
    language: str,
    as_of: date,
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    width, height = A4
    x = 20 * mm
    y = height - 20 * mm

    def header(title: str) -> None:
        nonlocal y
        pdf.setFont("Helvetica-Bold", 14)
        y = _pdf_line(pdf, title, x=x, y=y)
        pdf.setFont("Helvetica", 10)
        y -= 2 * mm

    header("NEFT Contract Specification")
    meta = payload.get("meta", {})
    org = payload.get("organization", {})
    y = _pdf_line(pdf, f"Org: {org.get('name') or org.get('id')}", x=x, y=y)
    y = _pdf_line(pdf, f"Date: {as_of.isoformat()}", x=x, y=y)
    y = _pdf_line(pdf, f"Contract Pack ID: {meta.get('contract_pack_id')}", x=x, y=y)
    y = _pdf_line(pdf, f"Snapshot Hash: {meta.get('entitlements_snapshot_hash')}", x=x, y=y)
    y -= 6 * mm

    header("General Information")
    for label, key in [
        ("INN", "inn"),
        ("KPP", "kpp"),
        ("OGRN", "ogrn"),
        ("Legal Address", "legal_address"),
        ("Billing Email", "billing_email"),
        ("Currency", "currency"),
    ]:
        value = org.get(key)
        if value:
            y = _pdf_line(pdf, f"{label}: {value}", x=x, y=y)
    y -= 6 * mm

    header("Plan")
    plan = payload.get("plan", {})
    for label, key in [
        ("Plan", "plan_code"),
        ("Title", "plan_title"),
        ("Billing Cycle", "billing_cycle"),
        ("Start Date", "starts_at"),
        ("Status", "status"),
    ]:
        value = plan.get(key)
        if value:
            y = _pdf_line(pdf, f"{label}: {value}", x=x, y=y)
    y -= 6 * mm

    header("Features")
    features = payload.get("features", [])
    for feature in features:
        feature_key = feature.get("feature_key")
        availability = feature.get("availability")
        source = feature.get("source")
        limits = feature.get("limits")
        line = f"{feature_key}: {availability}"
        if source:
            line = f"{line} ({source})"
        if limits:
            line = f"{line} | limits: {limits}"
        y = _pdf_line(pdf, line, x=x, y=y)
        if y < 30 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica", 10)
    y -= 6 * mm

    header("Add-ons")
    addons = payload.get("addons", [])
    if not addons:
        y = _pdf_line(pdf, "No add-ons", x=x, y=y)
    else:
        for addon in addons:
            line = f"{addon.get('code')}: {addon.get('status')}"
            if addon.get("starts_at"):
                line = f"{line} | starts: {addon.get('starts_at')}"
            if addon.get("price"):
                line = f"{line} | price: {addon.get('price')}"
            y = _pdf_line(pdf, line, x=x, y=y)
    y -= 6 * mm

    header("SLO / SLA")
    slo = payload.get("slo", {})
    if slo:
        y = _pdf_line(pdf, f"Tier: {slo.get('code')}", x=x, y=y)
        if slo.get("targets"):
            y = _pdf_line(pdf, f"Targets: {slo.get('targets')}", x=x, y=y)
        if slo.get("penalties"):
            y = _pdf_line(pdf, f"Penalties: {slo.get('penalties')}", x=x, y=y)
        y = _pdf_line(pdf, "SLO ≠ SLA, unless stated otherwise.", x=x, y=y)
    else:
        y = _pdf_line(pdf, "No SLO tier configured.", x=x, y=y)
    y -= 6 * mm

    header("Support Plan")
    support = payload.get("support_plan", {})
    if support:
        y = _pdf_line(pdf, f"Plan: {support.get('code')}", x=x, y=y)
        if support.get("channels"):
            y = _pdf_line(pdf, f"Channels: {support.get('channels')}", x=x, y=y)
        if support.get("response_time"):
            y = _pdf_line(pdf, f"Response: {support.get('response_time')}", x=x, y=y)
        if support.get("escalation"):
            y = _pdf_line(pdf, f"Escalation: {support.get('escalation')}", x=x, y=y)
    else:
        y = _pdf_line(pdf, "No support plan configured.", x=x, y=y)
    y -= 6 * mm

    if payload.get("pricing") and language:
        header("Pricing & Terms")
        pricing = payload.get("pricing", {})
        for label, key in [
            ("Plan Price", "plan_price"),
            ("Add-ons Price", "addons_price"),
            ("Payment Period", "payment_period"),
            ("Due Terms", "due_terms"),
            ("Grace Period", "grace_period"),
            ("Suspend Terms", "suspend_terms"),
        ]:
            value = pricing.get(key)
            if value:
                y = _pdf_line(pdf, f"{label}: {value}", x=x, y=y)
        if pricing.get("usage_billing_note"):
            y = _pdf_line(pdf, f"Usage: {pricing.get('usage_billing_note')}", x=x, y=y)
        y -= 6 * mm

    header("Legal")
    legal = payload.get("legal_terms") or []
    for entry in legal:
        y = _pdf_line(pdf, f"- {entry}", x=x, y=y)
    y = _pdf_line(pdf, "Signature: ____________________", x=x, y=y)
    y = _pdf_line(pdf, "Date: _________________________", x=x, y=y)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _readme_text(language: str) -> str:
    if language == "ru":
        return (
            "Контрактный пакет NEFT.\n"
            "Файлы:\n"
            "- contract_specification.pdf\n"
            "- contract_specification.json\n"
            "- entitlements_snapshot.json\n"
            "- pricing_breakdown.json\n"
        )
    return (
        "NEFT contract pack.\n"
        "Files:\n"
        "- contract_specification.pdf\n"
        "- contract_specification.json\n"
        "- entitlements_snapshot.json\n"
        "- pricing_breakdown.json\n"
    )


class ContractPackService:
    def __init__(self, db: Session):
        self.db = db
        bucket = settings.NEFT_S3_BUCKET_DOCUMENTS or settings.NEFT_S3_BUCKET
        self.storage = S3Storage(bucket=bucket)

    def _load_org(self, org_id: int) -> dict[str, Any]:
        if not _table_exists(self.db, "orgs"):
            return {"id": org_id}
        orgs = _table(self.db, "orgs")
        record = self.db.execute(select(orgs).where(orgs.c.id == org_id)).mappings().first()
        return dict(record) if record else {"id": org_id}

    def _load_subscription(self, org_id: int) -> dict[str, Any]:
        if not _table_exists(self.db, "org_subscriptions"):
            raise ValueError("org_not_found")
        org_subscriptions = _table(self.db, "org_subscriptions")
        subscription = (
            self.db.execute(select(org_subscriptions).where(org_subscriptions.c.org_id == org_id))
            .mappings()
            .first()
        )
        if not subscription:
            raise ValueError("org_not_found")
        return dict(subscription)

    def _load_plan(self, plan_id: int) -> dict[str, Any] | None:
        if not _table_exists(self.db, "subscription_plans"):
            return None
        plans = _table(self.db, "subscription_plans")
        plan = self.db.execute(select(plans).where(plans.c.id == plan_id)).mappings().first()
        return dict(plan) if plan else None

    def _load_support_plan(self, support_plan_id: int | None) -> dict[str, Any] | None:
        if not support_plan_id or not _table_exists(self.db, "support_plans"):
            return None
        support_plans = _table(self.db, "support_plans")
        record = (
            self.db.execute(select(support_plans).where(support_plans.c.id == support_plan_id))
            .mappings()
            .first()
        )
        return dict(record) if record else None

    def _load_slo_tier(self, slo_tier_id: int | None) -> dict[str, Any] | None:
        if not slo_tier_id or not _table_exists(self.db, "slo_tiers"):
            return None
        slo_tiers = _table(self.db, "slo_tiers")
        record = (
            self.db.execute(select(slo_tiers).where(slo_tiers.c.id == slo_tier_id))
            .mappings()
            .first()
        )
        return dict(record) if record else None

    def _load_billing_account(self, org_id: int) -> dict[str, Any] | None:
        if not _table_exists(self.db, "billing_accounts"):
            return None
        billing_accounts = _table(self.db, "billing_accounts")
        record = (
            self.db.execute(select(billing_accounts).where(billing_accounts.c.org_id == org_id))
            .mappings()
            .first()
        )
        return dict(record) if record else None

    def _load_addons(self, subscription_id: int) -> list[dict[str, Any]]:
        if not (_table_exists(self.db, "org_subscription_addons") and _table_exists(self.db, "addons")):
            return []
        org_addons = _table(self.db, "org_subscription_addons")
        addons = _table(self.db, "addons")
        rows = (
            self.db.execute(
                select(
                    addons.c.code,
                    addons.c.title,
                    addons.c.description,
                    addons.c.default_price,
                    org_addons.c.status,
                    org_addons.c.starts_at,
                    org_addons.c.price_override,
                )
                .join(addons, addons.c.id == org_addons.c.addon_id)
                .where(org_addons.c.org_subscription_id == subscription_id)
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def _load_overrides(self, subscription_id: int) -> dict[str, dict[str, Any]]:
        if not _table_exists(self.db, "org_subscription_overrides"):
            return {}
        overrides = _table(self.db, "org_subscription_overrides")
        rows = (
            self.db.execute(select(overrides).where(overrides.c.org_subscription_id == subscription_id))
            .mappings()
            .all()
        )
        return {row["feature_key"]: dict(row) for row in rows}

    def _build_features(self, entitlements: dict[str, Any], overrides: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        features = entitlements.get("features") or {}
        output: list[dict[str, Any]] = []
        for feature_key in sorted(features.keys()):
            payload = features.get(feature_key, {})
            output.append(
                {
                    "feature_key": feature_key,
                    "name": payload.get("name") or feature_key,
                    "availability": payload.get("availability"),
                    "limits": payload.get("limits"),
                    "source": "CONTRACT OVERRIDE" if feature_key in overrides else None,
                }
            )
        return output

    def _build_pricing(
        self,
        *,
        as_of: date,
        subscription: dict[str, Any],
        plan: dict[str, Any] | None,
        addons: list[dict[str, Any]],
        billing_account: dict[str, Any] | None,
        include_pricing: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not include_pricing or not _table_exists(self.db, "pricing_catalog"):
            return {}, {"note": "pricing_not_included"}
        as_of_dt = _as_of_datetime(as_of)
        plan_price = None
        currency = None
        if plan:
            plan_pricing = _resolve_pricing_record(
                self.db,
                item_type="PLAN",
                item_id=plan["id"],
                as_of=as_of_dt,
            )
            if plan_pricing:
                cycle = (subscription.get("billing_cycle") or "MONTHLY").upper()
                plan_price = (
                    plan_pricing.get("price_yearly") if cycle == "YEARLY" else plan_pricing.get("price_monthly")
                )
                currency = plan_pricing.get("currency")

        addon_prices = []
        addons_total = 0
        for addon in addons:
            price = addon.get("price_override") or addon.get("default_price")
            if price is not None:
                addons_total += float(price)
            addon_prices.append(
                {
                    "code": addon.get("code"),
                    "price": price,
                    "currency": currency,
                }
            )
        plan_price_value = float(plan_price) if plan_price is not None else None
        pricing_breakdown = {
            "plan_price": plan_price_value,
            "addons_price": addons_total if addon_prices else None,
            "currency": currency or (billing_account or {}).get("currency"),
            "items": {
                "plan": plan_price_value,
                "addons": addon_prices,
            },
        }

        terms = {
            "payment_period": subscription.get("billing_cycle"),
            "due_terms": (billing_account or {}).get("payment_terms"),
            "grace_period": (billing_account or {}).get("grace_period_days"),
            "suspend_terms": (billing_account or {}).get("suspend_terms"),
            "usage_billing_note": (billing_account or {}).get("usage_billing_note"),
        }
        return terms, pricing_breakdown

    def generate(
        self,
        *,
        org_id: int,
        format: str,
        language: str,
        as_of: date,
        include_pricing: bool,
        include_legal_terms: bool,
    ) -> ContractPackPayload:
        entitlements_snapshot = get_org_entitlements_snapshot(self.db, org_id=org_id)
        subscription = self._load_subscription(org_id)
        plan = self._load_plan(subscription["plan_id"])
        support_plan = self._load_support_plan(subscription.get("support_plan_id"))
        slo_tier = self._load_slo_tier(subscription.get("slo_tier_id"))
        billing_account = self._load_billing_account(org_id)
        addons = self._load_addons(subscription["id"])
        overrides = self._load_overrides(subscription["id"])

        contract_pack_id = _deterministic_contract_pack_id(
            org_id=org_id,
            as_of=as_of,
            entitlements_hash=entitlements_snapshot.hash,
            format=format,
            language=language,
            include_pricing=include_pricing,
            include_legal_terms=include_legal_terms,
        )

        organization = self._load_org(org_id)
        org_payload = {
            "id": org_id,
            "name": organization.get("name"),
            "inn": organization.get("inn"),
            "kpp": organization.get("kpp"),
            "ogrn": organization.get("ogrn"),
            "legal_address": organization.get("legal_address") or organization.get("address"),
            "billing_email": (billing_account or {}).get("billing_email"),
            "currency": (billing_account or {}).get("currency"),
        }

        terms, pricing_breakdown = self._build_pricing(
            as_of=as_of,
            subscription=subscription,
            plan=plan,
            addons=addons,
            billing_account=billing_account,
            include_pricing=include_pricing,
        )

        legal_terms = []
        if include_legal_terms:
            legal_terms = [
                "Not a public offer.",
                "Terms apply upon contract signature.",
                "Reference to the master agreement applies.",
            ]

        plan_payload = {
            "plan_code": (plan or {}).get("code"),
            "plan_title": (plan or {}).get("title"),
            "plan_version": (plan or {}).get("version"),
            "billing_cycle": subscription.get("billing_cycle"),
            "starts_at": subscription.get("starts_at"),
            "status": subscription.get("status"),
        }

        support_payload = None
        if support_plan:
            support_payload = {
                "code": support_plan.get("code"),
                "channels": support_plan.get("channels"),
                "response_time": support_plan.get("response_time"),
                "escalation": support_plan.get("escalation"),
            }

        slo_payload = None
        if slo_tier:
            slo_payload = {
                "code": slo_tier.get("code"),
                "targets": slo_tier.get("targets"),
                "penalties": slo_tier.get("penalties"),
            }

        addons_payload = []
        for addon in addons:
            price = addon.get("price_override") or addon.get("default_price")
            addons_payload.append(
                {
                    "code": addon.get("code"),
                    "description": addon.get("description") or addon.get("title"),
                    "status": addon.get("status"),
                    "starts_at": addon.get("starts_at"),
                    "price": price if include_pricing else None,
                }
            )

        contract_payload = {
            "meta": {
                "contract_pack_id": contract_pack_id,
                "as_of": as_of.isoformat(),
                "language": language,
                "entitlements_snapshot_hash": entitlements_snapshot.hash,
            },
            "organization": org_payload,
            "plan": plan_payload,
            "features": self._build_features(entitlements_snapshot.entitlements, overrides),
            "addons": addons_payload,
            "slo": slo_payload,
            "support_plan": support_payload,
            "pricing": terms if include_pricing else None,
            "billing": (billing_account or {}),
            "legal_terms": legal_terms,
        }

        pdf_bytes = _render_pdf(payload=contract_payload, language=language, as_of=as_of)
        contract_json = _normalize_json(contract_payload)
        entitlements_json = _normalize_json(entitlements_snapshot.entitlements)
        pricing_json = _normalize_json(pricing_breakdown)

        if format == "ZIP":
            zip_bytes = _build_zip(
                pdf_bytes=pdf_bytes,
                contract_json=contract_json,
                entitlements_json=entitlements_json,
                pricing_json=pricing_json,
                readme_text=_readme_text(language),
                as_of=as_of,
            )
            pack_bytes = zip_bytes
            object_key = f"contract-packs/{org_id}/{contract_pack_id}.zip"
            content_type = "application/zip"
        else:
            pack_bytes = pdf_bytes
            object_key = f"contract-packs/{org_id}/{contract_pack_id}.pdf"
            content_type = "application/pdf"

        self.storage.ensure_bucket()
        self.storage.put_bytes(object_key, pack_bytes, content_type=content_type)
        download_url = self.storage.presign(object_key) or self.storage.public_url(object_key)
        pack_hash = _hash_bytes(pack_bytes)

        self._persist_contract_pack(
            contract_pack_id=contract_pack_id,
            org_id=org_id,
            pack_hash=pack_hash,
            entitlements_snapshot_hash=entitlements_snapshot.hash,
            format=format,
            object_key=object_key,
            as_of=as_of,
        )

        return ContractPackPayload(
            contract_pack_id=contract_pack_id,
            pack_hash=pack_hash,
            object_key=object_key,
            download_url=download_url,
            entitlements_snapshot_hash=entitlements_snapshot.hash,
        )

    def list_packs(self, *, org_id: int) -> list[dict[str, Any]]:
        if not _table_exists(self.db, "contract_packs"):
            return []
        contract_packs = _table(self.db, "contract_packs")
        rows = (
            self.db.execute(
                select(contract_packs)
                .where(contract_packs.c.org_id == org_id)
                .order_by(desc(contract_packs.c.created_at))
            )
            .mappings()
            .all()
        )
        packs = []
        for row in rows:
            payload = dict(row)
            object_key = payload.get("object_key") or ""
            download_url = self.storage.presign(object_key) or self.storage.public_url(object_key)
            packs.append(
                {
                    "contract_pack_id": payload.get("id"),
                    "org_id": payload.get("org_id"),
                    "format": payload.get("format"),
                    "download_url": download_url,
                    "hash": payload.get("hash"),
                    "entitlements_snapshot_hash": payload.get("entitlements_snapshot_hash"),
                    "as_of": payload.get("as_of"),
                    "created_at": payload.get("created_at"),
                }
            )
        return packs

    def _persist_contract_pack(
        self,
        *,
        contract_pack_id: str,
        org_id: int,
        pack_hash: str,
        entitlements_snapshot_hash: str,
        format: str,
        object_key: str,
        as_of: date,
    ) -> None:
        if not _table_exists(self.db, "contract_packs"):
            return
        contract_packs = _table(self.db, "contract_packs")
        payload = {
            "id": contract_pack_id,
            "org_id": org_id,
            "format": format,
            "object_key": object_key,
            "hash": pack_hash,
            "entitlements_snapshot_hash": entitlements_snapshot_hash,
            "as_of": as_of,
            "created_at": datetime.now(timezone.utc),
        }
        sanitized = {key: value for key, value in payload.items() if key in contract_packs.c}
        self.db.execute(insert(contract_packs).values(**sanitized))
        self.db.commit()
