from __future__ import annotations

import app.routers.partner_onboarding as partner_onboarding_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.error_handlers import add_exception_handlers
from app.fastapi_utils import generate_unique_id
from app.models.audit_log import AuditLog
from app.models.partner import Partner
from app.models.partner_legal import (
    PartnerLegalDetails,
    PartnerLegalProfile,
    PartnerLegalStatus,
    PartnerLegalType,
)
from app.models.partner_management import PartnerUserRole
from app.routers.partner_onboarding import router as partner_onboarding_router
from app.services.partner_auth import require_partner_user


def _make_client() -> tuple[TestClient, sessionmaker, dict[str, str]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)
    PartnerLegalProfile.__table__.create(bind=engine)
    PartnerLegalDetails.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    add_exception_handlers(app)
    app.include_router(partner_onboarding_router, prefix="/api/core")

    token = {"user_id": "partner-owner-1", "portal": "partner", "partner_id": ""}

    def override_get_db():
        db = testing_session_local()
        try:
          yield db
        finally:
          db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_partner_user] = lambda: token

    return TestClient(app), testing_session_local, token


def _seed_pending_partner(session_factory: sessionmaker, token: dict[str, str]) -> str:
    db = session_factory()
    try:
        partner = Partner(
            code="partner-onboarding",
            legal_name="Pending Partner",
            brand_name=None,
            partner_type="OTHER",
            status="PENDING",
            contacts={},
        )
        db.add(partner)
        db.flush()
        db.add(PartnerUserRole(partner_id=partner.id, user_id="partner-owner-1", roles=["PARTNER_OWNER"]))
        db.commit()
        token["partner_id"] = str(partner.id)
        return str(partner.id)
    finally:
        db.close()


def _seed_unlinked_pending_partner(session_factory: sessionmaker, token: dict[str, str]) -> str:
    db = session_factory()
    try:
        partner = Partner(
            code="partner-onboarding-unlinked",
            legal_name="Pending Partner",
            brand_name=None,
            partner_type="OTHER",
            status="PENDING",
            contacts={},
        )
        db.add(partner)
        db.commit()
        token["partner_id"] = str(partner.id)
        token["sub"] = "partner@neft.local"
        return str(partner.id)
    finally:
        db.close()


def test_partner_onboarding_snapshot_reports_blockers(monkeypatch) -> None:
    monkeypatch.setattr(partner_onboarding_module, "legal_gate_required_codes", lambda: [])
    client, session_factory, token = _make_client()
    _seed_pending_partner(session_factory, token)

    response = client.get("/api/core/partner/onboarding")
    assert response.status_code == 200
    payload = response.json()

    assert payload["partner"]["status"] == "PENDING"
    assert payload["checklist"]["activation_ready"] is False
    assert "profile_incomplete" in payload["checklist"]["blocked_reasons"]
    assert "legal_profile_missing" in payload["checklist"]["blocked_reasons"]
    assert "legal_details_missing" in payload["checklist"]["blocked_reasons"]
    assert "legal_review_pending" in payload["checklist"]["blocked_reasons"]


def test_partner_onboarding_profile_patch_updates_pending_partner(monkeypatch) -> None:
    monkeypatch.setattr(partner_onboarding_module, "legal_gate_required_codes", lambda: [])
    client, session_factory, token = _make_client()
    partner_id = _seed_pending_partner(session_factory, token)

    response = client.patch(
        "/api/core/partner/onboarding/profile",
        json={"brand_name": "NEFT Partner", "contacts": {"email": "owner@partner.test", "phone": "+7 900 000 00 00"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["brand_name"] == "NEFT Partner"
    assert payload["contacts"]["email"] == "owner@partner.test"

    db = session_factory()
    try:
        partner = db.get(Partner, partner_id)
        assert partner is not None
        assert partner.brand_name == "NEFT Partner"
        assert partner.contacts["phone"] == "+7 900 000 00 00"
        event_types = {
            row[0]
            for row in db.query(AuditLog.event_type)
            .filter(AuditLog.entity_type == "partner", AuditLog.entity_id == partner_id)
            .all()
        }
        assert "PARTNER_ONBOARDING_STARTED" in event_types
        assert "PARTNER_ONBOARDING_PROFILE_UPDATED" in event_types
    finally:
        db.close()


def test_partner_onboarding_activate_requires_ready_checklist(monkeypatch) -> None:
    monkeypatch.setattr(partner_onboarding_module, "legal_gate_required_codes", lambda: [])
    client, session_factory, token = _make_client()
    _seed_pending_partner(session_factory, token)

    response = client.post("/api/core/partner/onboarding/activate")
    assert response.status_code == 409
    assert response.json()["error"] == "partner_onboarding_incomplete"
    assert "profile_incomplete" in response.json()["blocked_reasons"]


def test_partner_onboarding_activate_sets_partner_active_when_ready(monkeypatch) -> None:
    monkeypatch.setattr(partner_onboarding_module, "legal_gate_required_codes", lambda: [])
    client, session_factory, token = _make_client()
    partner_id = _seed_pending_partner(session_factory, token)

    db = session_factory()
    try:
        partner = db.get(Partner, partner_id)
        assert partner is not None
        partner.brand_name = "NEFT Partner"
        partner.contacts = {"email": "owner@partner.test"}
        db.add(
            PartnerLegalProfile(
                partner_id=partner_id,
                legal_type=PartnerLegalType.LEGAL_ENTITY,
                country="RU",
                tax_residency="RU",
                legal_status=PartnerLegalStatus.VERIFIED,
            )
        )
        db.add(
            PartnerLegalDetails(
                partner_id=partner_id,
                legal_name="Pending Partner LLC",
                inn="7701000000",
                kpp="770101001",
                ogrn="1027700000000",
                bank_account="40702810900000000001",
                bank_bic="044525225",
                bank_name="Neft Bank",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/core/partner/onboarding/activate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["partner"]["status"] == "ACTIVE"
    assert payload["checklist"]["activation_ready"] is True

    db = session_factory()
    try:
        partner = db.get(Partner, partner_id)
        assert partner is not None
        assert partner.status == "ACTIVE"
        event_types = {
            row[0]
            for row in db.query(AuditLog.event_type)
            .filter(AuditLog.entity_type == "partner", AuditLog.entity_id == partner_id)
            .all()
        }
        assert "PARTNER_ACTIVATED" in event_types
    finally:
        db.close()


def test_partner_onboarding_snapshot_can_use_repaired_demo_partner_link(monkeypatch) -> None:
    monkeypatch.setattr(partner_onboarding_module, "legal_gate_required_codes", lambda: [])
    client, session_factory, token = _make_client()
    partner_id = _seed_unlinked_pending_partner(session_factory, token)

    def _repairing_resolver(db, *, claims):
        row = db.query(PartnerUserRole).filter(PartnerUserRole.user_id == "partner-owner-1").first()
        if row is None:
            row = PartnerUserRole(partner_id=partner_id, user_id="partner-owner-1", roles=["PARTNER_OWNER"])
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    monkeypatch.setattr(partner_onboarding_module, "resolve_partner_user_link", _repairing_resolver)

    response = client.get("/api/core/partner/onboarding")
    assert response.status_code == 200
    payload = response.json()
    assert payload["partner"]["id"] == partner_id
    assert "profile_incomplete" in payload["checklist"]["blocked_reasons"]
