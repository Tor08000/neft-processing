from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_completion_proofs import ServiceCompletionProof, ServiceProofDecision
from app.models.service_completion_proofs import ServiceProofAttachment, ServiceProofEvent
from app.schemas.service_completion_proofs import (
    ProofDecisionRequest,
    ProofDisputeRequest,
    ProofOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.service_completion_proof_service import ServiceCompletionProofError, ServiceCompletionProofService

router = APIRouter(prefix="/client", tags=["client-portal-v1"])


def _ensure_client_context(principal: Principal) -> str:
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "client"},
        )
    return str(principal.client_id)


def _handle_service_error(exc: ServiceCompletionProofError) -> None:
    if exc.code in {"proof_not_found", "booking_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code == "invalid_transition":
        raise HTTPException(status_code=409, detail={"error": "invalid_transition", **exc.detail}) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


def _proof_out(db: Session, proof: ServiceCompletionProof) -> ProofOut:
    attachments = (
        db.query(ServiceProofAttachment)
        .filter(ServiceProofAttachment.proof_id == proof.id)
        .order_by(ServiceProofAttachment.created_at.asc())
        .all()
    )
    events = (
        db.query(ServiceProofEvent)
        .filter(ServiceProofEvent.proof_id == proof.id)
        .order_by(ServiceProofEvent.created_at.asc())
        .all()
    )
    return ProofOut(
        id=str(proof.id),
        booking_id=str(proof.booking_id),
        partner_id=str(proof.partner_id),
        client_id=str(proof.client_id),
        vehicle_id=str(proof.vehicle_id) if proof.vehicle_id else None,
        status=proof.status.value if hasattr(proof.status, "value") else proof.status,
        work_summary=proof.work_summary,
        odometer_km=proof.odometer_km,
        performed_at=proof.performed_at,
        parts_json=proof.parts_json,
        labor_json=proof.labor_json,
        price_snapshot_json=proof.price_snapshot_json,
        proof_hash=proof.proof_hash,
        signature_json=proof.signature_json,
        submitted_at=proof.submitted_at,
        confirmed_at=proof.confirmed_at,
        disputed_at=proof.disputed_at,
        created_at=proof.created_at,
        updated_at=proof.updated_at,
        attachments=[
            {
                "id": str(item.id),
                "attachment_id": str(item.attachment_id),
                "kind": item.kind.value if hasattr(item.kind, "value") else item.kind,
                "checksum": item.checksum,
                "created_at": item.created_at,
            }
            for item in attachments
        ],
        events=[
            {
                "id": str(item.id),
                "event_type": item.event_type.value if hasattr(item.event_type, "value") else item.event_type,
                "actor_type": item.actor_type.value if hasattr(item.actor_type, "value") else item.actor_type,
                "actor_id": str(item.actor_id) if item.actor_id else None,
                "payload": item.payload,
                "created_at": item.created_at,
            }
            for item in events
        ],
    )


@router.get("/bookings/{booking_id}/proof", response_model=ProofOut)
def get_booking_proof(
    booking_id: str,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> ProofOut:
    client_id = _ensure_client_context(principal)
    proof = (
        db.query(ServiceCompletionProof)
        .filter(ServiceCompletionProof.booking_id == booking_id)
        .order_by(ServiceCompletionProof.created_at.desc())
        .first()
    )
    if not proof:
        raise HTTPException(status_code=404, detail="proof_not_found")
    if str(proof.client_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _proof_out(db, proof)


@router.get("/proofs/{proof_id}", response_model=ProofOut)
def get_proof(
    proof_id: str,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> ProofOut:
    client_id = _ensure_client_context(principal)
    proof = db.query(ServiceCompletionProof).filter(ServiceCompletionProof.id == proof_id).one_or_none()
    if not proof:
        raise HTTPException(status_code=404, detail="proof_not_found")
    if str(proof.client_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _proof_out(db, proof)


@router.post("/proofs/{proof_id}/confirm", response_model=ProofOut)
def confirm_proof(
    proof_id: str,
    payload: ProofDecisionRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> ProofOut:
    client_id = _ensure_client_context(principal)
    proof = db.query(ServiceCompletionProof).filter(ServiceCompletionProof.id == proof_id).one_or_none()
    if not proof:
        raise HTTPException(status_code=404, detail="proof_not_found")
    if str(proof.client_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service = ServiceCompletionProofService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        service.confirm_proof(
            proof=proof,
            comment=payload.comment,
            actor_id=client_id,
            decision=ServiceProofDecision.CONFIRM,
        )
    except ServiceCompletionProofError as exc:
        _handle_service_error(exc)
    db.commit()
    return _proof_out(db, proof)


@router.post("/proofs/{proof_id}/dispute", response_model=ProofOut)
def dispute_proof(
    proof_id: str,
    payload: ProofDisputeRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> ProofOut:
    client_id = _ensure_client_context(principal)
    proof = db.query(ServiceCompletionProof).filter(ServiceCompletionProof.id == proof_id).one_or_none()
    if not proof:
        raise HTTPException(status_code=404, detail="proof_not_found")
    if str(proof.client_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service = ServiceCompletionProofService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        service.confirm_proof(
            proof=proof,
            comment=payload.comment,
            actor_id=client_id,
            decision=ServiceProofDecision.DISPUTE,
        )
    except ServiceCompletionProofError as exc:
        _handle_service_error(exc)
    db.commit()
    return _proof_out(db, proof)
