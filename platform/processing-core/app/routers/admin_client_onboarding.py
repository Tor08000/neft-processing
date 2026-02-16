from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.domains.client.onboarding.review.repo import OnboardingReviewRepository
from app.domains.client.onboarding.review.schemas import AdminApproveApplicationResponse
from app.domains.client.onboarding.review.service import approve_application

router = APIRouter(prefix="/admin/client-onboarding", tags=["admin-client-onboarding"])


@router.post("/{application_id}/approve", response_model=AdminApproveApplicationResponse)
def approve_client_onboarding_application(
    application_id: str,
    admin_user: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AdminApproveApplicationResponse:
    repo = OnboardingReviewRepository(db=db)
    item = approve_application(repo, application_id, admin_user, comment=None)
    return AdminApproveApplicationResponse(application_id=str(item.id), status=str(item.status), client_id=str(item.client_id))
