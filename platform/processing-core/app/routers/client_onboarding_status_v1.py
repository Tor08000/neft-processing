from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.onboarding.review.schemas import ClientDecisionResponse, IssueClientTokenResponse
from app.domains.client.onboarding.review.service import issue_client_token
from app.domains.client.onboarding.security import OnboardingTokenError, unauthorized, verify_application_access_token

router = APIRouter(prefix="/client/v1/onboarding", tags=["client-onboarding-status-v1"])
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


@router.get("/my-application/decision", response_model=ClientDecisionResponse)
def get_my_application_decision(
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
):
    application_id = str(token_payload.get("app_id"))
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})

    next_action = "CONTINUE_TO_CABINET" if application.status == "APPROVED" and application.client_id else None
    return ClientDecisionResponse(
        status=application.status,
        decision_reason=application.decision_reason,
        client_id=str(application.client_id) if application.client_id else None,
        next_action=next_action,
    )


@router.post("/my-application/issue-client-token", response_model=IssueClientTokenResponse)
def issue_my_client_token(
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
):
    application_id = str(token_payload.get("app_id"))
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})

    token = issue_client_token(application)
    return IssueClientTokenResponse(access_token=token)
