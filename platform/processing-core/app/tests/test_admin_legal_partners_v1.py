from __future__ import annotations

from app.api.dependencies.admin import require_admin_user
from app.models.audit_log import AuditLog
from app.models.partner import Partner
from app.models.partner_legal import (
    PartnerLegalDetails,
    PartnerLegalProfile,
    PartnerLegalStatus,
    PartnerLegalType,
)
from app.routers.admin.legal_partners import router as legal_partners_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


LEGAL_PARTNER_STATUS_TEST_TABLES = (
    AuditLog.__table__,
    Partner.__table__,
    PartnerLegalProfile.__table__,
    PartnerLegalDetails.__table__,
)


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": "admin-legal-1",
        "sub": "admin-legal-1",
        "email": "legal@example.com",
        "roles": list(roles),
    }


def test_admin_legal_partner_status_update_returns_verified_snapshot() -> None:
    with scoped_session_context(tables=LEGAL_PARTNER_STATUS_TEST_TABLES) as session:
        partner = Partner(
            code="partner-legal-review",
            legal_name="Partner Legal Review LLC",
            partner_type="OTHER",
            status="PENDING",
            contacts={},
        )
        session.add(partner)
        session.flush()
        partner_id = str(partner.id)
        session.add(
            PartnerLegalProfile(
                partner_id=partner_id,
                legal_type=PartnerLegalType.LEGAL_ENTITY,
                country="RU",
                tax_residency="RU",
                legal_status=PartnerLegalStatus.PENDING_REVIEW,
                vat_applicable=False,
            )
        )
        session.add(
            PartnerLegalDetails(
                partner_id=partner_id,
                legal_name="Partner Legal Review LLC",
                inn="7701234567",
                kpp="770101001",
                ogrn="1027700000000",
                bank_account="40702810900000000001",
                bank_bic="044525225",
                bank_name="Neft Bank",
            )
        )
        session.commit()

        with router_client_context(
            router=legal_partners_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_LEGAL")},
        ) as client:
            response = client.post(
                f"/api/core/v1/admin/legal/partners/{partner_id}/status",
                json={"status": "VERIFIED", "reason": "smoke legal verification"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["partner_id"] == partner_id
        assert payload["legal_status"] == "VERIFIED"
        session.refresh(partner)
        profile = session.get(PartnerLegalProfile, partner_id)
        assert profile is not None
        assert profile.legal_status == PartnerLegalStatus.VERIFIED
