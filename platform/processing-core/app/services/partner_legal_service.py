from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.partner_legal import (
    PartnerLegalDetails,
    PartnerLegalProfile,
    PartnerLegalStatus,
    PartnerLegalType,
    PartnerTaxPolicy,
    PartnerTaxRegime,
)
from app.services.audit_service import AuditService, AuditVisibility, RequestContext


LEGAL_DETAILS_COOLDOWN_DAYS = 3


class PartnerLegalError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PartnerTaxContext:
    legal_type: str | None
    tax_regime: str | None
    tax_rate: float | None
    vat: bool | None
    vat_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_type": self.legal_type,
            "tax_regime": self.tax_regime,
            "tax_rate": self.tax_rate,
            "vat": self.vat,
            "vat_rate": self.vat_rate,
        }


class PartnerLegalService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def get_profile(self, *, partner_id: str) -> PartnerLegalProfile | None:
        return self.db.query(PartnerLegalProfile).filter(PartnerLegalProfile.partner_id == partner_id).one_or_none()

    def get_details(self, *, partner_id: str) -> PartnerLegalDetails | None:
        return self.db.query(PartnerLegalDetails).filter(PartnerLegalDetails.partner_id == partner_id).one_or_none()

    def get_tax_policy(
        self, *, legal_type: PartnerLegalType | None, tax_regime: PartnerTaxRegime | None
    ) -> PartnerTaxPolicy | None:
        if not legal_type or not tax_regime:
            return None
        return (
            self.db.query(PartnerTaxPolicy)
            .filter(PartnerTaxPolicy.legal_type == legal_type, PartnerTaxPolicy.tax_regime == tax_regime)
            .one_or_none()
        )

    def upsert_profile(
        self,
        *,
        partner_id: str,
        legal_type: PartnerLegalType,
        country: str | None,
        tax_residency: str | None,
        tax_regime: PartnerTaxRegime | None,
        vat_applicable: bool,
        vat_rate: float | None,
    ) -> PartnerLegalProfile:
        profile = self.get_profile(partner_id=partner_id)
        if profile is None:
            profile = PartnerLegalProfile(partner_id=partner_id, legal_status=PartnerLegalStatus.DRAFT)
            self.db.add(profile)
        profile.legal_type = legal_type
        profile.country = country
        profile.tax_residency = tax_residency
        profile.tax_regime = tax_regime
        profile.vat_applicable = vat_applicable
        profile.vat_rate = vat_rate
        if profile.legal_status == PartnerLegalStatus.BLOCKED:
            profile.legal_status = PartnerLegalStatus.PENDING_REVIEW
        return profile

    def upsert_details(
        self,
        *,
        partner_id: str,
        legal_name: str | None,
        inn: str | None,
        kpp: str | None,
        ogrn: str | None,
        passport: str | None,
        bank_account: str | None,
        bank_bic: str | None,
        bank_name: str | None,
    ) -> PartnerLegalDetails:
        details = self.get_details(partner_id=partner_id)
        if details is None:
            details = PartnerLegalDetails(partner_id=partner_id)
            self.db.add(details)
        details.legal_name = legal_name
        details.inn = inn
        details.kpp = kpp
        details.ogrn = ogrn
        details.passport = passport
        details.bank_account = bank_account
        details.bank_bic = bank_bic
        details.bank_name = bank_name
        return details

    def update_status(
        self,
        *,
        partner_id: str,
        status: PartnerLegalStatus,
        comment: str | None = None,
    ) -> PartnerLegalProfile:
        profile = self.get_profile(partner_id=partner_id)
        if profile is None:
            raise PartnerLegalError("legal_profile_missing")
        profile.legal_status = status
        AuditService(self.db).audit(
            event_type="partner_legal_status_changed",
            entity_type="partner_legal_profile",
            entity_id=partner_id,
            action="partner_legal_status_changed",
            visibility=AuditVisibility.INTERNAL,
            after={
                "partner_id": partner_id,
                "status": status.value,
                "comment": comment,
            },
            request_ctx=self.request_ctx,
        )
        return profile

    def build_tax_context(self, *, profile: PartnerLegalProfile | None) -> PartnerTaxContext | None:
        if profile is None:
            return None
        policy = self.get_tax_policy(legal_type=profile.legal_type, tax_regime=profile.tax_regime)
        tax_rate = float(policy.income_tax_rate) if policy and policy.income_tax_rate is not None else None
        vat_rate = None
        if profile.vat_rate is not None:
            vat_rate = float(profile.vat_rate)
        elif policy and policy.vat_rate is not None:
            vat_rate = float(policy.vat_rate)
        return PartnerTaxContext(
            legal_type=profile.legal_type.value,
            tax_regime=profile.tax_regime.value if profile.tax_regime else None,
            tax_rate=tax_rate,
            vat=bool(profile.vat_applicable) if profile.vat_applicable is not None else None,
            vat_rate=vat_rate,
        )

    def ensure_payout_allowed(self, *, partner_id: str) -> list[str]:
        profile = self.get_profile(partner_id=partner_id)
        if profile is None:
            raise PartnerLegalError("legal_profile_missing")
        if profile.legal_status != PartnerLegalStatus.VERIFIED:
            raise PartnerLegalError("legal_status_not_verified")
        details = self.get_details(partner_id=partner_id)
        if details is None:
            raise PartnerLegalError("legal_details_missing")
        if not self._details_complete(details, profile.legal_type):
            raise PartnerLegalError("legal_details_incomplete")
        warnings = self._collect_warnings(profile=profile, details=details)
        if warnings:
            AuditService(self.db).audit(
                event_type="partner_legal_payout_warning",
                entity_type="partner_legal_profile",
                entity_id=partner_id,
                action="partner_legal_payout_warning",
                visibility=AuditVisibility.INTERNAL,
                after={"partner_id": partner_id, "warnings": warnings},
                request_ctx=self.request_ctx,
            )
        return warnings

    def _details_complete(self, details: PartnerLegalDetails, legal_type: PartnerLegalType) -> bool:
        required_fields = [details.legal_name, details.bank_account, details.bank_bic, details.bank_name]
        if legal_type == PartnerLegalType.INDIVIDUAL:
            required_fields.append(details.passport)
        else:
            required_fields.append(details.inn)
        if legal_type == PartnerLegalType.LEGAL_ENTITY:
            required_fields.append(details.kpp)
            required_fields.append(details.ogrn)
        return all(value for value in required_fields)

    def _collect_warnings(self, *, profile: PartnerLegalProfile, details: PartnerLegalDetails) -> list[str]:
        warnings: list[str] = []
        tax_policy = self.get_tax_policy(legal_type=profile.legal_type, tax_regime=profile.tax_regime)
        if profile.tax_regime and tax_policy is None:
            warnings.append("tax_regime_unconfirmed")
        updated_at = details.updated_at or details.created_at
        if updated_at:
            now = datetime.now(timezone.utc)
            if now - updated_at < timedelta(days=LEGAL_DETAILS_COOLDOWN_DAYS):
                warnings.append("legal_details_recently_changed")
        return warnings

    def collect_warnings(self, *, profile: PartnerLegalProfile, details: PartnerLegalDetails) -> list[str]:
        return self._collect_warnings(profile=profile, details=details)


__all__ = ["PartnerLegalError", "PartnerLegalService", "PartnerTaxContext"]
