from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.onboarding.schemas import (
    CreateOnboardingApplicationRequest,
    CreateOnboardingApplicationResponse,
    OnboardingApplicationResponse,
    UpdateOnboardingApplicationRequest,
)
from app.domains.client.onboarding.security import (
    OnboardingTokenError,
    issue_application_access_token,
    unauthorized,
    verify_application_access_token,
)
from app.domains.client.onboarding.service import (
    ensure_draft_editable,
    ensure_submit_allowed,
    validate_patch_fields,
)
from app.routers.client_onboarding_documents_v1 import router as client_onboarding_documents_v1_router

router = APIRouter(prefix="/onboarding", tags=["client-onboarding"])
_security = HTTPBearer(auto_error=False)


def _repo(db: Session = Depends(get_db)) -> ClientOnboardingRepository:
    return ClientOnboardingRepository(db=db)


def _token_payload(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized("missing_onboarding_token")
    try:
        return verify_application_access_token(credentials.credentials)
    except OnboardingTokenError as exc:
        raise unauthorized(str(exc)) from exc


def _check_access_or_403(token_payload: dict, application_id: str) -> None:
    if token_payload.get("app_id") != application_id:
        raise HTTPException(status_code=403, detail={"reason_code": "onboarding_token_app_mismatch"})


@router.post("/applications", response_model=CreateOnboardingApplicationResponse)
def create_onboarding_application(
    payload: CreateOnboardingApplicationRequest,
    repo: ClientOnboardingRepository = Depends(_repo),
) -> CreateOnboardingApplicationResponse:
    patch = payload.model_dump()
    validate_patch_fields(patch)
    application = repo.create_draft(**patch)
    return CreateOnboardingApplicationResponse(
        application=OnboardingApplicationResponse.model_validate(application),
        access_token=issue_application_access_token(str(application.id)),
    )


@router.put("/applications/{application_id}", response_model=OnboardingApplicationResponse)
def update_onboarding_application(
    application_id: str,
    payload: UpdateOnboardingApplicationRequest,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
) -> OnboardingApplicationResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    ensure_draft_editable(application)
    patch = payload.model_dump(exclude_unset=True)
    validate_patch_fields(patch)
    application = repo.update_draft(application, patch)
    return OnboardingApplicationResponse.model_validate(application)


@router.post("/applications/{application_id}/submit", response_model=OnboardingApplicationResponse)
def submit_onboarding_application(
    application_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
) -> OnboardingApplicationResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    ensure_submit_allowed(application)
    application = repo.set_submitted(application)
    return OnboardingApplicationResponse.model_validate(application)


@router.get("/applications/{application_id}", response_model=OnboardingApplicationResponse)
def get_onboarding_application(
    application_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
) -> OnboardingApplicationResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    return OnboardingApplicationResponse.model_validate(application)


@router.get("/my-application", response_model=OnboardingApplicationResponse)
def get_my_onboarding_application(
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
) -> OnboardingApplicationResponse:
    application_id = str(token_payload.get("app_id"))
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    return OnboardingApplicationResponse.model_validate(application)


router.include_router(client_onboarding_documents_v1_router)
