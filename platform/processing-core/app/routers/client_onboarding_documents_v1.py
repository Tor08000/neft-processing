from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.client.onboarding.documents.repo import ClientOnboardingDocumentsRepository
from app.domains.client.onboarding.documents.schemas import DocumentItem, ListDocumentsResponse, UploadDocumentResponse
from app.domains.client.onboarding.documents.service import ensure_upload_allowed, parse_doc_type, prepare_upload
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.onboarding.security import OnboardingTokenError, unauthorized, verify_application_access_token

router = APIRouter(tags=["client-onboarding-documents-v1"])
_security = HTTPBearer(auto_error=False)


def _repo(db: Session = Depends(get_db)) -> ClientOnboardingRepository:
    return ClientOnboardingRepository(db=db)


def _docs_repo(db: Session = Depends(get_db)) -> ClientOnboardingDocumentsRepository:
    return ClientOnboardingDocumentsRepository(db=db)


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


@router.post("/applications/{application_id}/documents", response_model=UploadDocumentResponse, status_code=201)
async def upload_onboarding_document(
    application_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    docs_repo: ClientOnboardingDocumentsRepository = Depends(_docs_repo),
) -> UploadDocumentResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    ensure_upload_allowed(application)
    parsed_doc_type = parse_doc_type(doc_type)

    data = await file.read()
    prepared = prepare_upload(file.filename or "document", file.content_type or "application/octet-stream", data)

    document = docs_repo.create_document(
        client_application_id=application_id,
        doc_type=parsed_doc_type.value,
        storage_key="",
        bucket=os.getenv("MINIO_BUCKET_CLIENT_DOCS", "client-documents"),
        filename=prepared.filename,
        mime=prepared.mime,
        size=prepared.size,
        sha256=prepared.sha256,
        status="UPLOADED",
    )

    storage_key = f"onboarding/{application_id}/{document.id}"
    storage = OnboardingDocumentsStorage.from_env()
    storage.ensure_bucket(document.bucket)
    storage.put_object(document.bucket, storage_key, data, prepared.mime)

    document = docs_repo.update_document(document, {"storage_key": storage_key})
    return UploadDocumentResponse.model_validate(document)


@router.get("/applications/{application_id}/documents", response_model=ListDocumentsResponse)
def list_onboarding_documents(
    application_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    docs_repo: ClientOnboardingDocumentsRepository = Depends(_docs_repo),
) -> ListDocumentsResponse:
    _check_access_or_403(token_payload, application_id)
    application = repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})
    items = [DocumentItem.model_validate(item) for item in docs_repo.list_by_application_id(application_id)]
    return ListDocumentsResponse(items=items)


@router.get("/documents/{doc_id}/download")
def download_onboarding_document(
    doc_id: str,
    token_payload: dict = Depends(_token_payload),
    repo: ClientOnboardingRepository = Depends(_repo),
    docs_repo: ClientOnboardingDocumentsRepository = Depends(_docs_repo),
):
    document = docs_repo.get_by_id(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"reason_code": "document_not_found"})
    _check_access_or_403(token_payload, document.client_application_id)
    application = repo.get_by_id(document.client_application_id)
    if application is None:
        raise HTTPException(status_code=404, detail={"reason_code": "application_not_found"})

    storage = OnboardingDocumentsStorage.from_env()
    stream = storage.get_object_stream(document.bucket, document.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{document.filename}"'}
    return StreamingResponse(stream, media_type=document.mime, headers=headers)
