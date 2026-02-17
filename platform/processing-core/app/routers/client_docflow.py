from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.client.docflow.schemas import (
    CreateDocumentsPackageRequest,
    CreateDocumentsPackageResponse,
    CreatePackageRequest,
    DocumentsPackageStatusResponse,
    NotificationOut,
    NotificationsResponse,
    PackageOut,
    PackagesResponse,
    TimelineEventOut,
    TimelineResponse,
)
from app.domains.client.docflow.service import ClientDocflowService
from app.domains.client.onboarding.security import OnboardingTokenError, unauthorized, verify_application_access_token

router = APIRouter(prefix="/client", tags=["client-docflow"])
_security = HTTPBearer(auto_error=False)


def _token_payload(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized("missing_onboarding_token")
    try:
        return verify_application_access_token(credentials.credentials)
    except OnboardingTokenError as exc:
        raise unauthorized(str(exc)) from exc


def _docflow(db: Session = Depends(get_db)) -> ClientDocflowService:
    return ClientDocflowService(db)


def _user_id(token_payload: dict) -> str:
    return str(token_payload.get("sub") or token_payload.get("app_id"))


@router.get("/docflow/timeline", response_model=TimelineResponse)
def list_timeline(
    application_id: str | None = None,
    doc_id: str | None = None,
    limit: int = 50,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> TimelineResponse:
    app_id = str(token_payload.get("app_id"))
    if application_id and application_id != app_id:
        raise HTTPException(status_code=403, detail={"reason_code": "onboarding_token_app_mismatch"})
    items = svc.timeline.list_events(application_id=application_id or app_id, doc_id=doc_id, client_id=None, limit=limit)
    return TimelineResponse(
        items=[
            TimelineEventOut(
                id=str(item.id),
                client_id=str(item.client_id) if item.client_id else None,
                application_id=str(item.application_id) if item.application_id else None,
                doc_id=str(item.doc_id) if item.doc_id else None,
                event_type=item.event_type,
                actor_user_id=str(item.actor_user_id) if item.actor_user_id else None,
                actor_type=item.actor_type,
                created_at=item.created_at,
                meta_json=item.meta_json or {},
            )
            for item in items
        ]
    )


@router.get("/onboarding/applications/{application_id}/timeline", response_model=TimelineResponse)
def list_timeline_for_application(
    application_id: str,
    limit: int = 50,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> TimelineResponse:
    if str(token_payload.get("app_id")) != application_id:
        raise HTTPException(status_code=403, detail={"reason_code": "onboarding_token_app_mismatch"})
    items = svc.timeline.list_events(application_id=application_id, doc_id=None, client_id=None, limit=limit)
    return TimelineResponse(
        items=[
            TimelineEventOut(
                id=str(item.id),
                client_id=str(item.client_id) if item.client_id else None,
                application_id=str(item.application_id) if item.application_id else None,
                doc_id=str(item.doc_id) if item.doc_id else None,
                event_type=item.event_type,
                actor_user_id=str(item.actor_user_id) if item.actor_user_id else None,
                actor_type=item.actor_type,
                created_at=item.created_at,
                meta_json=item.meta_json or {},
            )
            for item in items
        ]
    )


@router.post("/docflow/packages", response_model=PackageOut)
def create_package(
    payload: CreatePackageRequest,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> PackageOut:
    package = svc.packages.create_onboarding_signed_package(
        client_id=str(token_payload.get("client_id") or token_payload.get("app_id")),
        application_id=payload.application_id or str(token_payload.get("app_id")),
        created_by_user_id=_user_id(token_payload),
        doc_ids=payload.doc_ids,
        package_kind=payload.package_kind,
    )
    svc.notifications.create(
        client_id=str(token_payload.get("client_id") or token_payload.get("app_id")),
        user_id=_user_id(token_payload),
        kind="PACKAGE_READY",
        title="Пакет документов готов",
        message=f"Пакет {package.filename or package.id} готов к скачиванию",
        payload={"package_id": package.id},
    )
    return PackageOut.model_validate(package, from_attributes=True)


@router.get("/docflow/packages", response_model=PackagesResponse)
def list_packages(
    application_id: str | None = None,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> PackagesResponse:
    if application_id and application_id != str(token_payload.get("app_id")):
        raise HTTPException(status_code=403, detail={"reason_code": "onboarding_token_app_mismatch"})
    items = svc.packages.list_packages(
        client_id=str(token_payload.get("client_id") or token_payload.get("app_id")),
        application_id=application_id or str(token_payload.get("app_id")),
    )
    return PackagesResponse(items=[PackageOut.model_validate(item, from_attributes=True) for item in items])


@router.get("/docflow/packages/{package_id}/download")
def download_package(
    package_id: str,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
):
    package = svc.packages.get_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail={"reason_code": "package_not_found"})
    if str(package.client_id) != str(token_payload.get("client_id") or token_payload.get("app_id")):
        raise HTTPException(status_code=403, detail={"reason_code": "package_forbidden"})
    if package.status != "READY" or not package.storage_key:
        raise HTTPException(status_code=409, detail={"reason_code": "package_not_ready"})
    stream = svc.packages.storage.get_object_stream("client-generated-documents", package.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{package.filename or "package.zip"}"'}
    return StreamingResponse(stream, media_type="application/zip", headers=headers)


@router.post("/documents/package", response_model=CreateDocumentsPackageResponse, status_code=202)
def create_documents_package(
    payload: CreateDocumentsPackageRequest,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> CreateDocumentsPackageResponse:
    client_id = str(token_payload.get("client_id") or token_payload.get("app_id"))
    package = svc.packages.create_documents_package(
        client_id=client_id,
        created_by_user_id=_user_id(token_payload),
        doc_ids=payload.ids,
    )
    try:
        from app.tasks.document_packages import build_document_package

        build_document_package.delay(package.id)
    except Exception:
        svc.packages.build_package(package.id)
        svc.notifications.create(
            client_id=client_id,
            user_id=_user_id(token_payload),
            kind="PACKAGE_READY",
            title="Пакет документов готов",
            message=f"Пакет {package.id} готов к скачиванию",
            payload={"package_id": package.id},
            dedupe_key=f"package-ready:{package.id}",
        )
    return CreateDocumentsPackageResponse(package_id=package.id, status="CREATING")


@router.get("/documents/package/{package_id}", response_model=DocumentsPackageStatusResponse)
def get_documents_package_status(
    package_id: str,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> DocumentsPackageStatusResponse:
    package = svc.packages.get_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail={"reason_code": "package_not_found"})
    if str(package.client_id) != str(token_payload.get("client_id") or token_payload.get("app_id")):
        raise HTTPException(status_code=403, detail={"reason_code": "package_forbidden"})
    url = None
    if package.status == "READY":
        url = f"/api/core/client/documents/package/{package_id}/download"
    return DocumentsPackageStatusResponse(package_id=package_id, status=package.status, download_url=url)


@router.get("/documents/package/{package_id}/download")
def download_documents_package(
    package_id: str,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
):
    return download_package(package_id=package_id, token_payload=token_payload, svc=svc)


@router.get("/docflow/notifications", response_model=NotificationsResponse)
def list_notifications(
    limit: int = 20,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> NotificationsResponse:
    client_id = str(token_payload.get("client_id") or token_payload.get("app_id"))
    user_id = _user_id(token_payload)
    items = svc.notifications.list_for_client(client_id=client_id, user_id=user_id, limit=limit)
    unread_count = svc.notifications.unread_count(client_id=client_id, user_id=user_id)
    return NotificationsResponse(
        unread_count=unread_count,
        items=[NotificationOut.model_validate(item, from_attributes=True) for item in items],
    )


@router.post("/docflow/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    token_payload: dict = Depends(_token_payload),
    svc: ClientDocflowService = Depends(_docflow),
) -> NotificationOut:
    item = svc.notifications.mark_read(
        notification_id=notification_id,
        client_id=str(token_payload.get("client_id") or token_payload.get("app_id")),
        user_id=_user_id(token_payload),
    )
    if item is None:
        raise HTTPException(status_code=404, detail={"reason_code": "notification_not_found"})
    return NotificationOut.model_validate(item, from_attributes=True)
