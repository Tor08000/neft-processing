from __future__ import annotations

import re

from fastapi import HTTPException

from app.domains.client.onboarding.models import ClientOnboardingApplication, OnboardingApplicationStatus

_DIGITS_RE = re.compile(r"^\d+$")
_PHONE_ALLOWED_RE = re.compile(r"^\+?[\d\s\-()]+$")


class OnboardingValidationError(HTTPException):
    def __init__(self, reason_code: str, status_code: int = 422):
        super().__init__(status_code=status_code, detail={"reason_code": reason_code})


def validate_inn(inn: str | None) -> None:
    if inn is None or inn == "":
        return
    if not _DIGITS_RE.fullmatch(inn) or len(inn) not in {10, 12}:
        raise OnboardingValidationError("invalid_inn")


def validate_ogrn(ogrn: str | None) -> None:
    if ogrn is None or ogrn == "":
        return
    if not _DIGITS_RE.fullmatch(ogrn) or len(ogrn) not in {13, 15}:
        raise OnboardingValidationError("invalid_ogrn")


def validate_phone(phone: str | None) -> None:
    if phone is None or phone == "":
        return
    if not _PHONE_ALLOWED_RE.fullmatch(phone):
        raise OnboardingValidationError("invalid_phone")
    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 15:
        raise OnboardingValidationError("invalid_phone")


def validate_patch_fields(patch: dict[str, object]) -> None:
    validate_phone(patch.get("phone") if isinstance(patch.get("phone"), str) else None)
    validate_inn(patch.get("inn") if isinstance(patch.get("inn"), str) else None)
    validate_ogrn(patch.get("ogrn") if isinstance(patch.get("ogrn"), str) else None)


def ensure_draft_editable(application: ClientOnboardingApplication) -> None:
    if application.status != OnboardingApplicationStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail={"reason_code": "application_not_editable"})


def ensure_submit_allowed(application: ClientOnboardingApplication) -> None:
    ensure_draft_editable(application)
    required_fields = {
        "email": application.email,
        "company_name": application.company_name,
        "inn": application.inn,
        "org_type": application.org_type,
    }
    missing = [name for name, value in required_fields.items() if not value]
    if missing:
        raise HTTPException(status_code=400, detail={"reason_code": "missing_required_fields", "fields": missing})
    validate_inn(application.inn)
    validate_ogrn(application.ogrn)
    validate_phone(application.phone)
