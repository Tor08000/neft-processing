from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_completion_proofs import ServiceCompletionProof, ServiceCompletionProofStatus
from app.api.dependencies.admin import require_admin_user
from app.schemas.service_completion_proofs import ProofAdminResolveRequest, ProofAdminResolveResponse, ProofOut
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.service_completion_proof_service import ServiceCompletionProofError, ServiceCompletionProofService

router = APIRouter(prefix="/proofs", tags=["admin"])


def _proof_out(proof: ServiceCompletionProof) -> ProofOut:
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
        attachments=[],
        events=[],
    )


@router.get("", response_model=list[ProofOut])
def list_disputed_proofs(
    status: ServiceCompletionProofStatus = Query(ServiceCompletionProofStatus.DISPUTED),
    db: Session = Depends(get_db),
) -> list[ProofOut]:
    proofs = (
        db.query(ServiceCompletionProof)
        .filter(ServiceCompletionProof.status == status)
        .order_by(ServiceCompletionProof.created_at.desc())
        .all()
    )
    return [_proof_out(proof) for proof in proofs]


@router.post("/{proof_id}/resolve", response_model=ProofAdminResolveResponse)
def resolve_dispute(
    proof_id: str,
    payload: ProofAdminResolveRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ProofAdminResolveResponse:
    proof = db.query(ServiceCompletionProof).filter(ServiceCompletionProof.id == proof_id).one_or_none()
    if not proof:
        raise HTTPException(status_code=404, detail="proof_not_found")
    service = ServiceCompletionProofService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    approve = payload.decision == "CONFIRM"
    try:
        resolved = service.resolve_dispute(proof=proof, approve=approve, actor_id=None, reason=payload.reason)
    except ServiceCompletionProofError as exc:
        raise HTTPException(status_code=409, detail={"error": exc.code, **exc.detail}) from exc
    db.commit()
    return ProofAdminResolveResponse(
        proof_id=str(resolved.id),
        status=resolved.status.value if hasattr(resolved.status, "value") else resolved.status,
    )
