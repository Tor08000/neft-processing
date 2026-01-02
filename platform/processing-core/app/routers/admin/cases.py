from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.cases import Case, CaseEvent, CaseStatus
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
from app.services.admin_auth import require_admin
from app.services.case_events_service import (
    CaseEventChainIntegrityResult,
    CaseEventSignatureIntegrityResult,
    list_case_events,
    verify_case_event_chain,
    verify_case_event_signatures,
)
from app.services.cases_service import close_case, update_case

router = APIRouter(prefix="/cases", tags=["admin-cases"])


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
    actor = None
    if event.actor_user_id or event.actor_email:
        actor = CaseEventActor(id=event.actor_user_id, email=event.actor_email)
    meta = None
    if changes or payload.get("reason") is not None or export_ref:
        meta = CaseEventMeta(
            changes=[CaseEventChange.model_validate(item) for item in changes] if changes else None,
            reason=payload.get("reason"),
            export_ref=CaseEventArtifact.model_validate(export_ref) if export_ref else None,
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
    token: dict = Depends(require_admin),
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


@router.post("/{case_id}/close", response_model=CaseWithEventResponse)
def close_case_endpoint(
    case_id: str,
    payload: CaseCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> CaseWithEventResponse:
    case = _get_case(db, case_id)
    request_id, trace_id = _request_ids(request)
    actor = token.get("user_id") or token.get("sub") or token.get("email")
    closed = close_case(
        db,
        case=case,
        actor=actor,
        resolution_note=payload.resolution_note,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    db.refresh(closed)
    return _case_with_event(closed, _latest_case_event(db, case_id))


__all__ = ["router"]
