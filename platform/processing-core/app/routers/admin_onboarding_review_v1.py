from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.domains.client.onboarding.documents.models import DocStatus
from app.domains.client.onboarding.documents.schemas import DocumentItem
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage
from app.domains.client.onboarding.review.repo import OnboardingReviewRepository
from app.domains.client.onboarding.review.schemas import (
    AdminApplicationDetailsResponse,
    AdminDecisionCommentRequest,
    AdminRejectRequest,
    ApprovalResponse,
    DocumentStatusResponse,
)
from app.domains.client.onboarding.review.service import (
    approve_application,
    reject_application,
    set_document_status,
    start_review,
)
from app.domains.client.onboarding.schemas import OnboardingApplicationResponse

router = APIRouter(prefix="/admin/v1/onboarding", tags=["admin-onboarding-review-v1"])


def _repo(db: Session = Depends(get_db)) -> OnboardingReviewRepository:
    return OnboardingReviewRepository(db=db)


@router.get("/applications", response_model=list[OnboardingApplicationResponse])
def list_applications(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    del admin_user
    rows = repo.list_applications(status=status, q=q, limit=limit, offset=offset)
    return [OnboardingApplicationResponse.model_validate(item) for item in rows]


@router.get("/applications/{application_id}", response_model=AdminApplicationDetailsResponse)
def get_application_details(
    application_id: str,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    del admin_user
    application = repo.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    documents = repo.list_documents(application_id)
    return AdminApplicationDetailsResponse(
        application=OnboardingApplicationResponse.model_validate(application),
        documents=[DocumentItem.model_validate(item) for item in documents],
    )


@router.post("/applications/{application_id}/start-review", response_model=OnboardingApplicationResponse)
def start_application_review(
    application_id: str,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    item = start_review(repo, application_id, admin_user)
    return OnboardingApplicationResponse.model_validate(item)


@router.post("/applications/{application_id}/approve", response_model=ApprovalResponse)
def approve_onboarding_application(
    application_id: str,
    payload: AdminDecisionCommentRequest,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    item = approve_application(repo, application_id, admin_user, comment=payload.comment)
    return ApprovalResponse(application=OnboardingApplicationResponse.model_validate(item), client_id=str(item.client_id))


@router.post("/applications/{application_id}/reject", response_model=OnboardingApplicationResponse)
def reject_onboarding_application(
    application_id: str,
    payload: AdminRejectRequest,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    item = reject_application(repo, application_id, admin_user, reason=payload.reason)
    return OnboardingApplicationResponse.model_validate(item)


@router.post("/documents/{doc_id}/verify", response_model=DocumentStatusResponse)
def verify_document(
    doc_id: str,
    payload: AdminDecisionCommentRequest,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    item = set_document_status(repo, doc_id, DocStatus.VERIFIED.value, payload.comment, admin_user)
    return DocumentStatusResponse.model_validate(item)


@router.post("/documents/{doc_id}/reject", response_model=DocumentStatusResponse)
def reject_document(
    doc_id: str,
    payload: AdminRejectRequest,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    item = set_document_status(repo, doc_id, DocStatus.REJECTED.value, payload.reason, admin_user)
    return DocumentStatusResponse.model_validate(item)


@router.get("/documents/{doc_id}/download")
def download_document(
    doc_id: str,
    admin_user: dict = Depends(require_admin_user),
    repo: OnboardingReviewRepository = Depends(_repo),
):
    del admin_user
    item = repo.get_document(doc_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"reason_code": "document_not_found"})

    storage = OnboardingDocumentsStorage.from_env()
    stream = storage.get_object_stream(item.bucket, item.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{item.filename}"'}
    return StreamingResponse(stream, media_type=item.mime, headers=headers)
