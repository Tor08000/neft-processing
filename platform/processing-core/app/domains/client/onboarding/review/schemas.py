from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domains.client.onboarding.documents.schemas import DocumentItem
from app.domains.client.onboarding.schemas import OnboardingApplicationResponse


class AdminDecisionCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = None


class AdminRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str


class DocumentStatusResponse(DocumentItem):
    pass


class AdminApplicationDetailsResponse(BaseModel):
    application: OnboardingApplicationResponse
    documents: list[DocumentItem]


class ApprovalResponse(BaseModel):
    application: OnboardingApplicationResponse
    client_id: str


class ClientDecisionResponse(BaseModel):
    status: str
    decision_reason: str | None = None
    client_id: str | None = None
    next_action: str | None = None


class IssueClientTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
