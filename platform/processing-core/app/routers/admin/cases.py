from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin_capability import require_admin_capability
from app.db import get_db
from app.models.cases import Case, CaseEvent, CaseStatus
from app.models.case_exports import CaseExport
from app.schemas.admin.decision_memory import DecisionMemoryEntryOut, DecisionMemoryListResponse
from app.schemas.admin.case_exports import CaseExportListResponse, CaseExportOut
from app.schemas.admin.case_events import (
    CaseCloseRequest,
    CaseEventsResponse,
    CaseEventsVerifyResponse,
    CaseEventOut,
    CaseEventActor,
    CaseEventArtifact,
    CaseEventChange,
    CaseEventMeta,
    CaseEventsVerifyChain,
    CaseEventsVerifySignatures,
    CaseStatusUpdateRequest,
    CaseWithEventResponse,
)
from app.schemas.cases import CaseResponse
from app.services.case_events_service import (
    CaseEventChainIntegrityResult,
    CaseEventSignatureIntegrityResult,
    list_case_events,
    verify_case_event_chain,
    verify_case_event_signatures,
)
from app.services.cases_service import close_case, update_case
from app.services.decision_memory.records import list_decision_memory_for_case
from app.services.audit_signing import AuditSigningService

router = APIRouter(
    prefix="/cases",
    tags=["admin-cases"],
    dependencies=[Depends(require_admin_capability("cases"))],
)


def _get_case(db: Session, case_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id).one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")
    return case


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


def _parse_status(value: str) -> CaseStatus:
    if value == "OPEN":
        return CaseStatus.TRIAGE
    try:
        return CaseStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_status") from exc


def _event_to_schema(event: CaseEvent) -> CaseEventOut:
    payload = event.payload_redacted or {}
    changes = payload.get("changes")
    export_ref = payload.get("artifact")
    content_sha256 = payload.get("content_sha256")
    actor = None
    if event.actor_user_id or event.actor_email:
        actor = CaseEventActor(id=event.actor_user_id, email=event.actor_email)
    meta = None
    if changes or payload.get("reason") is not None or export_ref or content_sha256:
        meta = CaseEventMeta(
            changes=[CaseEventChange.model_validate(item) for item in changes] if changes else None,
            reason=payload.get("reason"),
            export_ref=CaseEventArtifact.model_validate(export_ref) if export_ref else None,
            content_sha256=content_sha256,
        )
    return CaseEventOut(
        id=event.id,
        at=event.at,
        type=event.type.value,
        actor=actor,
        request_id=event.request_id,
        trace_id=event.trace_id,
        source="backend",
        prev_hash=event.prev_hash,
        hash=event.hash,
        signature=event.signature,
        signature_alg=event.signature_alg,
        signing_key_id=event.signing_key_id,
        signed_at=event.signed_at,
        meta=meta,
    )


def _case_with_event(case: Case, event: CaseEvent | None) -> CaseWithEventResponse:
    case_payload = CaseResponse.model_validate(case).model_dump()
    event_out = _event_to_schema(event) if event else None
    return CaseWithEventResponse(**case_payload, event=event_out)


def _latest_case_event(db: Session, case_id: str) -> CaseEvent | None:
    return (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.desc())
        .first()
    )


def _export_to_schema(export: CaseExport) -> CaseExportOut:
    return CaseExportOut(
        id=str(export.id),
        kind=export.kind,
        case_id=str(export.case_id) if export.case_id else None,
        content_type=export.content_type,
        content_sha256=export.content_sha256,
        artifact_signature=export.artifact_signature,
        artifact_signature_alg=export.artifact_signature_alg,
        artifact_signing_key_id=export.artifact_signing_key_id,
        artifact_signed_at=export.artifact_signed_at,
        size_bytes=export.size_bytes,
        created_at=export.created_at,
        deleted_at=export.deleted_at,
        delete_reason=export.delete_reason,
    )


def _verify_event_signature(event: CaseEvent | None) -> bool:
    if not event or not event.signature or not event.signature_alg or not event.signing_key_id:
        return False
    try:
        message = bytes.fromhex(event.hash)
    except ValueError:
        return False
    signing_service = AuditSigningService()
    return signing_service.verify(
        message=message,
        signature_b64=event.signature,
        alg=event.signature_alg,
        key_id=event.signing_key_id,
    )


def _verify_export_signature(export: CaseExport | None) -> bool | None:
    if not export:
        return None
    if not export.artifact_signature or not export.artifact_signature_alg or not export.artifact_signing_key_id:
        return False
    try:
        message = bytes.fromhex(export.content_sha256)
    except ValueError:
        return False
    signing_service = AuditSigningService()
    return signing_service.verify(
        message=message,
        signature_b64=export.artifact_signature,
        alg=export.artifact_signature_alg,
        key_id=export.artifact_signing_key_id,
    )


@router.get("/{case_id}/events", response_model=CaseEventsResponse)
def list_case_events_endpoint(
    case_id: str,
    limit: int = Query(200, ge=1, le=500),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
) -> CaseEventsResponse:
    _get_case(db, case_id)
    offset = int(cursor or 0)
    events = list_case_events(db, case_id=case_id, limit=limit + 1, offset=offset)
    next_cursor = None
    if len(events) > limit:
        events = events[:limit]
        next_cursor = str(offset + limit)
    return CaseEventsResponse(items=[_event_to_schema(event) for event in events], next_cursor=next_cursor)


@router.post("/{case_id}/events/verify", response_model=CaseEventsVerifyResponse)
def verify_case_events_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
) -> CaseEventsVerifyResponse:
    _get_case(db, case_id)
    result: CaseEventChainIntegrityResult = verify_case_event_chain(db, case_id=case_id)
    signature_result: CaseEventSignatureIntegrityResult = verify_case_event_signatures(db, case_id=case_id)
    return CaseEventsVerifyResponse(
        chain=CaseEventsVerifyChain(
            status="verified" if result.verified else "broken",
            tail_hash=result.tail_hash,
            count=result.count,
            broken_index=result.broken_index,
            expected_hash=result.expected_hash,
            actual_hash=result.actual_hash,
        ),
        signatures=CaseEventsVerifySignatures(
            status="verified" if signature_result.verified else "broken",
            broken_index=signature_result.broken_index,
            key_id=signature_result.key_id,
        ),
    )


@router.post("/{case_id}/status", response_model=CaseWithEventResponse)
def update_case_status_endpoint(
    case_id: str,
    payload: CaseStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_capability("cases", "operate")),
) -> CaseWithEventResponse:
    case = _get_case(db, case_id)
    request_id, trace_id = _request_ids(request)
    actor = token.get("user_id") or token.get("sub") or token.get("email")
    updated = update_case(
        db,
        case=case,
        status=_parse_status(payload.status),
        assigned_to=None,
        priority=None,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    db.refresh(updated)
    return _case_with_event(updated, _latest_case_event(db, case_id))


@router.get("/{case_id}/exports", response_model=CaseExportListResponse)
def list_case_exports_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
) -> CaseExportListResponse:
    _get_case(db, case_id)
    exports = (
        db.query(CaseExport)
        .filter(CaseExport.case_id == case_id)
        .order_by(CaseExport.created_at.desc())
        .all()
    )
    return CaseExportListResponse(items=[_export_to_schema(export) for export in exports])


@router.get("/{case_id}/decisions", response_model=DecisionMemoryListResponse)
def list_case_decisions_endpoint(
    case_id: str,
    limit: int = Query(200, ge=1, le=500),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
) -> DecisionMemoryListResponse:
    _get_case(db, case_id)
    offset = int(cursor or 0)
    records = list_decision_memory_for_case(db, case_id=case_id, limit=limit + 1, offset=offset)
    next_cursor = None
    if len(records) > limit:
        records = records[:limit]
        next_cursor = str(offset + limit)

    event_ids = {record.audit_event_id for record in records}
    events = db.query(CaseEvent).filter(CaseEvent.id.in_(event_ids)).all() if event_ids else []
    event_map = {event.id: event for event in events}

    export_ids = {record.decision_ref_id for record in records}
    exports = db.query(CaseExport).filter(CaseExport.id.in_(export_ids)).all() if export_ids else []
    export_map = {export.id: export for export in exports}

    chain_result = verify_case_event_chain(db, case_id=case_id)

    items = []
    for record in records:
        event = event_map.get(record.audit_event_id)
        export = export_map.get(record.decision_ref_id)
        items.append(
            DecisionMemoryEntryOut(
                id=str(record.id),
                case_id=str(record.case_id) if record.case_id else None,
                decision_type=record.decision_type,
                decision_ref_id=str(record.decision_ref_id),
                decision_at=record.decision_at,
                decided_by_user_id=str(record.decided_by_user_id) if record.decided_by_user_id else None,
                context_snapshot=record.context_snapshot or {},
                rationale=record.rationale,
                score_snapshot=record.score_snapshot,
                mastery_snapshot=record.mastery_snapshot,
                audit_event_id=str(record.audit_event_id),
                created_at=record.created_at,
                audit_chain_verified=chain_result.verified,
                audit_signature_verified=_verify_event_signature(event),
                artifact_signature_verified=_verify_export_signature(export),
            )
        )

    return DecisionMemoryListResponse(items=items, next_cursor=next_cursor)


@router.post("/{case_id}/close", response_model=CaseWithEventResponse)
def close_case_endpoint(
    case_id: str,
    payload: CaseCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_capability("cases", "operate")),
) -> CaseWithEventResponse:
    case = _get_case(db, case_id)
    request_id, trace_id = _request_ids(request)
    actor = token.get("user_id") or token.get("sub") or token.get("email")
    closed = close_case(
        db,
        case=case,
        actor=actor,
        resolution_note=payload.resolution_note,
        score_snapshot=payload.score_snapshot,
        mastery_snapshot=payload.mastery_snapshot,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    db.refresh(closed)
    return _case_with_event(closed, _latest_case_event(db, case_id))


__all__ = ["router"]
