from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.clients.document_service import DocumentServiceRenderClient
from app.db import get_db
from app.domains.client.generated_docs.repo import ClientGeneratedDocumentsRepository
from app.domains.client.generated_docs.schemas import GeneratedDocumentItem, GeneratedDocumentsListResponse
from app.domains.client.generated_docs.service import ClientGeneratedDocsService
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.onboarding.security import OnboardingTokenError, unauthorized, verify_application_access_token

router = APIRouter(prefix="", tags=["client-generated-docs-v1"])
_security = HTTPBearer(auto_error=False)


def _repo(db: Session = Depends(get_db)) -> ClientOnboardingRepository:
    return ClientOnboardingRepository(db=db)


def _docs_repo(db: Session = Depends(get_db)) -> ClientGeneratedDocumentsRepository:
    return ClientGeneratedDocumentsRepository(db=db)


def _svc(docs_repo: ClientGeneratedDocumentsRepository = Depends(_docs_repo)) -> ClientGeneratedDocsService:
    return ClientGeneratedDocsService(
        docs_repo=docs_repo,
        document_client=DocumentServiceRenderClient(),
        storage=OnboardingDocumentsStorage.from_env(),
    )


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


@router.post("/applications/{application_id}/generate-docs", response_model=GeneratedDocumentsListResponse)
def generate_application_documents(
    application_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    svc: ClientGeneratedDocsService = Depends(_svc),
) -> GeneratedDocumentsListResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})

    items = [GeneratedDocumentItem.model_validate(item) for item in svc.generate_for_application(application=application)]
    return GeneratedDocumentsListResponse(items=items)


@router.get("/applications/{application_id}/generated-docs", response_model=GeneratedDocumentsListResponse)
def list_application_generated_documents(
    application_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    docs_repo: ClientGeneratedDocumentsRepository = Depends(_docs_repo),
) -> GeneratedDocumentsListResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    items = [GeneratedDocumentItem.model_validate(item) for item in docs_repo.list_by_application_id(application_id)]
    return GeneratedDocumentsListResponse(items=items)


@router.get("/generated-docs/{doc_id}/download")
def download_generated_document(
    doc_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    docs_repo: ClientGeneratedDocumentsRepository = Depends(_docs_repo),
):
    document = docs_repo.get_by_id(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"reason_code": "document_not_found"})
    if not document.client_application_id:
        raise HTTPException(status_code=409, detail={"reason_code": "document_not_attached_to_application"})
    _check_access_or_403(token_payload, document.client_application_id)
    application = repo.get_by_id(document.client_application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})

    bucket = os.getenv("MINIO_BUCKET_CLIENT_GENERATED_DOCS", "client-generated-documents")
    storage = OnboardingDocumentsStorage.from_env()
    stream = storage.get_object_stream(bucket, document.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{document.filename}"'}
    return StreamingResponse(stream, media_type=document.mime, headers=headers)
