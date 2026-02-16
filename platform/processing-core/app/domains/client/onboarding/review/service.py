from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import jwt

from app.domains.client.onboarding.documents.models import DocStatus
from app.domains.client.onboarding.models import OnboardingApplicationStatus
from app.domains.client.onboarding.review.policy import can_approve
from app.domains.client.onboarding.review.repo import OnboardingReviewRepository

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_user_id(admin_user: dict) -> str:
    return str(admin_user.get("user_id") or admin_user.get("sub") or "admin")


def _emit_onboarding_event(
    *, event_type: str, application_id: str, admin_user: dict, client_id: str | None = None, user_id: str | None = None
) -> None:
    logger.info(
        "onboarding_event",
        extra={
            "event_type": event_type,
            "application_id": application_id,
            "admin_user_id": _as_user_id(admin_user),
            "client_id": client_id,
            "user_id": user_id,
        },
    )


def start_review(repo: OnboardingReviewRepository, application_id: str, admin_user: dict):
    application = repo.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    if application.status != OnboardingApplicationStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail={"reason_code": "invalid_status_transition"})

    application.status = OnboardingApplicationStatus.IN_REVIEW.value
    application.reviewed_by_user_id = _as_user_id(admin_user)
    application.reviewed_at = _now()
    application.updated_at = _now()
    return repo.save(application)


def set_document_status(
    repo: OnboardingReviewRepository,
    doc_id: str,
    status: str,
    reason: str | None,
    admin_user: dict,
):
    del admin_user
    document = repo.get_document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"reason_code": "document_not_found"})
    application = repo.get_application(document.client_application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    if application.status not in {OnboardingApplicationStatus.SUBMITTED.value, OnboardingApplicationStatus.IN_REVIEW.value}:
        raise HTTPException(status_code=409, detail={"reason_code": "document_status_locked"})

    if status == DocStatus.REJECTED.value and not reason:
        raise HTTPException(status_code=400, detail={"reason_code": "rejection_reason_required"})

    document.status = status
    document.rejection_reason = reason if status == DocStatus.REJECTED.value else None
    document.updated_at = _now()
    return repo.save(document)


def approve_application(repo: OnboardingReviewRepository, application_id: str, admin_user: dict, comment: str | None = None):
    application = repo.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    if application.status == OnboardingApplicationStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail={"reason_code": "application_already_approved"})
    if application.status not in {OnboardingApplicationStatus.IN_REVIEW.value, OnboardingApplicationStatus.SUBMITTED.value}:
        raise HTTPException(status_code=409, detail={"reason_code": "invalid_status_transition"})

    documents = repo.list_documents(application_id)
    policy_result = can_approve(application, documents)
    if not policy_result.ok:
        payload = {"reason_code": policy_result.reason_code}
        if policy_result.missing_doc_types:
            payload["missing_doc_types"] = policy_result.missing_doc_types
        raise HTTPException(status_code=409, detail=payload)

    if not application.company_name:
        raise HTTPException(status_code=400, detail={"reason_code": "company_name_required"})
    if not application.inn:
        raise HTTPException(status_code=400, detail={"reason_code": "inn_required"})
    if not application.org_type:
        raise HTTPException(status_code=400, detail={"reason_code": "org_type_required"})

    client = repo.get_client_by_inn(application.inn)
    if client is not None:
        raise HTTPException(status_code=409, detail={"reason_code": "client_already_exists"})

    client = repo.create_client(
        company_name=application.company_name,
        inn=application.inn,
        ogrn=application.ogrn,
    )

    applicant_user_id = application.created_by_user_id or f"onboarding:{application.email}"
    repo.ensure_client_user_membership(client_id=str(client.id), user_id=str(applicant_user_id), status="ACTIVE")
    repo.ensure_client_user_role(client_id=str(client.id), user_id=str(applicant_user_id), role="CLIENT_OWNER")

    application.client_id = str(client.id)
    application.status = OnboardingApplicationStatus.APPROVED.value
    application.decision_reason = comment
    now = _now()
    application.reviewed_by_user_id = _as_user_id(admin_user)
    application.approved_by_user_id = _as_user_id(admin_user)
    application.reviewed_at = now
    application.approved_at = now
    application.rejected_at = None
    application.updated_at = now

    _emit_onboarding_event(
        event_type="APPLICATION_APPROVED",
        application_id=str(application.id),
        admin_user=admin_user,
        client_id=str(client.id),
        user_id=str(applicant_user_id),
    )
    _emit_onboarding_event(
        event_type="CLIENT_CREATED",
        application_id=str(application.id),
        admin_user=admin_user,
        client_id=str(client.id),
        user_id=str(applicant_user_id),
    )
    _emit_onboarding_event(
        event_type="CLIENT_OWNER_ASSIGNED",
        application_id=str(application.id),
        admin_user=admin_user,
        client_id=str(client.id),
        user_id=str(applicant_user_id),
    )

    return repo.save(application)


def reject_application(repo: OnboardingReviewRepository, application_id: str, admin_user: dict, reason: str):
    application = repo.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    if application.status == OnboardingApplicationStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail={"reason_code": "application_already_approved"})
    if application.status not in {OnboardingApplicationStatus.IN_REVIEW.value, OnboardingApplicationStatus.SUBMITTED.value}:
        raise HTTPException(status_code=409, detail={"reason_code": "invalid_status_transition"})
    if not reason.strip():
        raise HTTPException(status_code=400, detail={"reason_code": "reason_required"})

    application.status = OnboardingApplicationStatus.REJECTED.value
    application.decision_reason = reason.strip()
    application.reviewed_by_user_id = _as_user_id(admin_user)
    application.reviewed_at = _now()
    application.rejected_at = _now()
    application.approved_at = None
    application.updated_at = _now()
    return repo.save(application)


def issue_client_token(application, *, role: str = "CLIENT_OWNER") -> str:
    if application.status != OnboardingApplicationStatus.APPROVED.value or not application.client_id:
        raise HTTPException(status_code=409, detail={"reason_code": "application_not_approved"})

    secret = os.getenv("CLIENT_TOKEN_SECRET") or os.getenv("CLIENT_PUBLIC_KEY") or os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail={"reason_code": "client_token_secret_not_configured"})

    now = datetime.now(timezone.utc)
    issuer = os.getenv("NEFT_CLIENT_ISSUER", os.getenv("CLIENT_AUTH_ISSUER", "neft-client"))
    audience = os.getenv("NEFT_CLIENT_AUDIENCE", os.getenv("CLIENT_AUTH_AUDIENCE", "neft-client"))
    payload = {
        "sub": application.created_by_user_id or f"onboarding:{application.email}",
        "user_id": application.created_by_user_id or f"onboarding:{application.email}",
        "subject_type": "client_user",
        "portal": "client",
        "role": role,
        "roles": [role],
        "client_id": application.client_id,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=os.getenv("CLIENT_TOKEN_ALG", "HS256"))
