from __future__ import annotations

from dataclasses import dataclass

from app.domains.client.onboarding.documents.models import ClientDocument, DocStatus
from app.domains.client.onboarding.models import ClientOnboardingApplication

_REQUIRED_DOCS_BY_ORG_TYPE: dict[str, set[str]] = {
    "DEFAULT": {"CHARTER", "EGRUL", "BANK_DETAILS"},
}


@dataclass(slots=True)
class PolicyResult:
    ok: bool
    reason_code: str | None = None
    missing_doc_types: list[str] | None = None


def required_doc_types(org_type: str | None) -> set[str]:
    key = (org_type or "").strip().upper()
    return _REQUIRED_DOCS_BY_ORG_TYPE.get(key, _REQUIRED_DOCS_BY_ORG_TYPE["DEFAULT"])


def can_approve(application: ClientOnboardingApplication, documents: list[ClientDocument]) -> PolicyResult:
    required_fields = {
        "email": application.email,
        "company_name": application.company_name,
        "inn": application.inn,
        "org_type": application.org_type,
    }
    missing_fields = [name for name, value in required_fields.items() if not value]
    if missing_fields:
        return PolicyResult(ok=False, reason_code="missing_required_fields")

    required_docs = required_doc_types(application.org_type)
    by_type: dict[str, list[ClientDocument]] = {}
    for item in documents:
        by_type.setdefault(item.doc_type, []).append(item)

    missing_types = [doc_type for doc_type in sorted(required_docs) if doc_type not in by_type]
    if missing_types:
        return PolicyResult(ok=False, reason_code="missing_required_documents", missing_doc_types=missing_types)

    for doc_type in required_docs:
        statuses = {item.status for item in by_type.get(doc_type, [])}
        if DocStatus.VERIFIED.value not in statuses:
            return PolicyResult(ok=False, reason_code="missing_verified_documents")
        if DocStatus.REJECTED.value in statuses and DocStatus.VERIFIED.value not in statuses:
            return PolicyResult(ok=False, reason_code="has_rejected_documents")

    return PolicyResult(ok=True)
