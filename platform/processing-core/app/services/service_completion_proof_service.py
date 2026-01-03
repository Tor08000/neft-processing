from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderStatus
from app.models.service_completion_proofs import (
    ServiceCompletionProof,
    ServiceCompletionProofStatus,
    ServiceProofActorType,
    ServiceProofAttachment,
    ServiceProofAttachmentKind,
    ServiceProofConfirmation,
    ServiceProofDecision,
    ServiceProofEvent,
    ServiceProofEventType,
)
from app.models.cases import Case, CaseKind, CasePriority
from app.models.vehicle_profile import VehicleRecommendation, VehicleRecommendationStatus, VehicleServiceRecord
from app.services.audit_service import RequestContext
from app.services.audit_signing import AuditSignature, AuditSigningError, AuditSigningService
from app.services.case_event_hashing import canonical_json


class ServiceCompletionProofError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class ProofSignaturePayload:
    proof_hash: str
    signature_json: dict


class ServiceCompletionProofService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _tenant_id(self) -> int:
        if self.request_ctx and self.request_ctx.tenant_id is not None:
            return int(self.request_ctx.tenant_id)
        return 0

    def _sign_hash(self, payload_hash: str) -> AuditSignature:
        signing_service = AuditSigningService()
        return signing_service.sign(bytes.fromhex(payload_hash))

    def _signature_json(self, signature: AuditSignature) -> dict[str, Any]:
        return {
            "key_id": signature.key_id,
            "algo": signature.alg,
            "signature": signature.signature,
            "signed_at": signature.signed_at.isoformat(),
        }

    def _ensure_order(self, *, booking_id: str) -> MarketplaceOrder:
        order = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.id == booking_id).one_or_none()
        if not order:
            raise ServiceCompletionProofError("booking_not_found")
        return order

    def _ensure_order_completed(self, *, order: MarketplaceOrder) -> None:
        if MarketplaceOrderStatus(order.status) != MarketplaceOrderStatus.COMPLETED:
            raise ServiceCompletionProofError("booking_not_completed")

    def _emit_event(
        self,
        *,
        proof: ServiceCompletionProof,
        event_type: ServiceProofEventType,
        actor_type: ServiceProofActorType,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> ServiceProofEvent:
        event = ServiceProofEvent(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            proof_id=proof.id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )
        self.db.add(event)
        return event

    def _build_proof_payload(self, *, proof: ServiceCompletionProof) -> dict[str, Any]:
        attachments = (
            self.db.query(ServiceProofAttachment)
            .filter(ServiceProofAttachment.proof_id == proof.id)
            .order_by(ServiceProofAttachment.created_at.asc())
            .all()
        )
        attachment_payload = [
            {"attachment_id": str(item.attachment_id), "checksum": item.checksum, "kind": item.kind.value}
            for item in attachments
        ]
        return {
            "booking_id": str(proof.booking_id),
            "partner_id": str(proof.partner_id),
            "client_id": str(proof.client_id),
            "vehicle_id": str(proof.vehicle_id) if proof.vehicle_id else None,
            "performed_at": proof.performed_at,
            "odometer_km": proof.odometer_km,
            "work_summary": proof.work_summary,
            "parts_json": proof.parts_json,
            "labor_json": proof.labor_json,
            "attachments": attachment_payload,
            "price_snapshot_json": proof.price_snapshot_json,
            "submitted_at": proof.submitted_at,
            "confirmed_at": proof.confirmed_at,
            "disputed_at": proof.disputed_at,
            "created_at": proof.created_at,
            "updated_at": proof.updated_at,
        }

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        canonical = canonical_json(payload)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _resolve_recommendation_id(self, proof: ServiceCompletionProof) -> str | None:
        snapshot = proof.price_snapshot_json or {}
        for key in ("vehicle_recommendation_id", "recommendation_id"):
            if key in snapshot and snapshot[key]:
                return str(snapshot[key])
        return None

    def create_proof(
        self,
        *,
        booking_id: str,
        work_summary: str,
        performed_at: datetime,
        odometer_km: float | None,
        parts_json: dict | None,
        labor_json: dict | None,
        vehicle_id: str | None,
        actor_id: str | None,
    ) -> ServiceCompletionProof:
        order = self._ensure_order(booking_id=booking_id)
        self._ensure_order_completed(order=order)
        if actor_id and str(order.partner_id) != str(actor_id):
            raise ServiceCompletionProofError("forbidden")
        now = self._now()
        proof = ServiceCompletionProof(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            booking_id=order.id,
            partner_id=order.partner_id,
            client_id=order.client_id,
            vehicle_id=vehicle_id,
            status=ServiceCompletionProofStatus.DRAFT,
            work_summary=work_summary,
            odometer_km=odometer_km,
            performed_at=performed_at,
            parts_json=parts_json,
            labor_json=labor_json,
            price_snapshot_json=order.price_snapshot_json or order.price_snapshot,
            proof_hash="",
            signature_json={},
            created_at=now,
            updated_at=now,
        )
        self.db.add(proof)
        self.db.flush()
        payload = self._build_proof_payload(proof=proof)
        proof.proof_hash = self._hash_payload(payload)
        proof.signature_json = {}
        self._emit_event(
            proof=proof,
            event_type=ServiceProofEventType.CREATED,
            actor_type=ServiceProofActorType.PARTNER,
            actor_id=actor_id,
            payload={"status": proof.status.value},
        )
        return proof

    def add_attachment(
        self,
        *,
        proof: ServiceCompletionProof,
        attachment_id: str,
        kind: ServiceProofAttachmentKind,
        checksum: str,
        actor_id: str | None,
    ) -> ServiceProofAttachment:
        if proof.status != ServiceCompletionProofStatus.DRAFT:
            raise ServiceCompletionProofError("attachments_locked")
        attachment = ServiceProofAttachment(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            proof_id=proof.id,
            attachment_id=attachment_id,
            kind=kind,
            checksum=checksum,
        )
        self.db.add(attachment)
        self._emit_event(
            proof=proof,
            event_type=ServiceProofEventType.ATTACHED_FILE,
            actor_type=ServiceProofActorType.PARTNER,
            actor_id=actor_id,
            payload={"attachment_id": attachment_id, "kind": kind.value, "checksum": checksum},
        )
        return attachment

    def submit_proof(self, *, proof: ServiceCompletionProof, actor_id: str | None) -> ProofSignaturePayload:
        if proof.status != ServiceCompletionProofStatus.DRAFT:
            raise ServiceCompletionProofError("invalid_transition", detail={"from": proof.status.value})
        order = self._ensure_order(booking_id=str(proof.booking_id))
        self._ensure_order_completed(order=order)
        proof.submitted_at = self._now()
        proof.updated_at = proof.submitted_at
        payload = self._build_proof_payload(proof=proof)
        proof_hash = self._hash_payload(payload)
        try:
            signature = self._sign_hash(proof_hash)
        except AuditSigningError as exc:
            raise ServiceCompletionProofError("signing_failed") from exc
        proof.status = ServiceCompletionProofStatus.SUBMITTED
        proof.proof_hash = proof_hash
        proof.signature_json = self._signature_json(signature)
        self._emit_event(
            proof=proof,
            event_type=ServiceProofEventType.SUBMITTED,
            actor_type=ServiceProofActorType.PARTNER,
            actor_id=actor_id,
            payload={"proof_hash": proof.proof_hash, "signature": proof.signature_json},
        )
        return ProofSignaturePayload(proof_hash=proof_hash, signature_json=proof.signature_json)

    def confirm_proof(
        self,
        *,
        proof: ServiceCompletionProof,
        comment: str | None,
        actor_id: str | None,
        decision: ServiceProofDecision,
    ) -> ServiceProofConfirmation:
        if proof.status != ServiceCompletionProofStatus.SUBMITTED:
            existing = (
                self.db.query(ServiceProofConfirmation)
                .filter(ServiceProofConfirmation.proof_id == proof.id)
                .filter(ServiceProofConfirmation.decision == decision)
                .order_by(ServiceProofConfirmation.decision_at.desc())
                .first()
            )
            if existing and decision == ServiceProofDecision.CONFIRM:
                return existing
            if existing and decision == ServiceProofDecision.DISPUTE:
                return existing
            raise ServiceCompletionProofError("invalid_transition", detail={"from": proof.status.value})
        now = self._now()
        confirm_payload = f"{proof.proof_hash}:{decision.value}:{comment or ''}:{now.isoformat()}".encode("utf-8")
        confirm_hash = hashlib.sha256(confirm_payload).hexdigest()
        try:
            signature = self._sign_hash(confirm_hash)
        except AuditSigningError as exc:
            raise ServiceCompletionProofError("signing_failed") from exc
        confirmation = ServiceProofConfirmation(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            proof_id=proof.id,
            decision=decision,
            client_comment=comment,
            client_signature_json=self._signature_json(signature),
            decision_at=now,
        )
        self.db.add(confirmation)
        if decision == ServiceProofDecision.CONFIRM:
            proof.status = ServiceCompletionProofStatus.CONFIRMED
            proof.confirmed_at = now
            proof.updated_at = now
            self._emit_event(
                proof=proof,
                event_type=ServiceProofEventType.CONFIRMED,
                actor_type=ServiceProofActorType.CLIENT,
                actor_id=actor_id,
                payload={"confirmation_id": confirmation.id, "signature": confirmation.client_signature_json},
            )
            self._create_service_record(proof=proof)
            self._close_recommendation_if_linked(proof=proof)
        else:
            proof.status = ServiceCompletionProofStatus.DISPUTED
            proof.disputed_at = now
            proof.updated_at = now
            self._emit_event(
                proof=proof,
                event_type=ServiceProofEventType.DISPUTED,
                actor_type=ServiceProofActorType.CLIENT,
                actor_id=actor_id,
                payload={"confirmation_id": confirmation.id, "comment": comment},
            )
            self._create_dispute_case(proof=proof)
        return confirmation

    def resolve_dispute(
        self,
        *,
        proof: ServiceCompletionProof,
        approve: bool,
        actor_id: str | None,
        reason: str | None,
    ) -> ServiceCompletionProof:
        if proof.status != ServiceCompletionProofStatus.DISPUTED:
            raise ServiceCompletionProofError("invalid_transition", detail={"from": proof.status.value})
        if approve:
            proof.status = ServiceCompletionProofStatus.CONFIRMED
            proof.confirmed_at = self._now()
            proof.updated_at = proof.confirmed_at
            self._emit_event(
                proof=proof,
                event_type=ServiceProofEventType.RESOLVED,
                actor_type=ServiceProofActorType.ADMIN,
                actor_id=actor_id,
                payload={"decision": "CONFIRMED", "reason": reason},
            )
            self._create_service_record(proof=proof)
            self._close_recommendation_if_linked(proof=proof)
        else:
            proof.status = ServiceCompletionProofStatus.REJECTED
            proof.updated_at = self._now()
            self._emit_event(
                proof=proof,
                event_type=ServiceProofEventType.REJECTED,
                actor_type=ServiceProofActorType.ADMIN,
                actor_id=actor_id,
                payload={"decision": "REJECTED", "reason": reason},
            )
        return proof

    def _create_service_record(self, *, proof: ServiceCompletionProof) -> VehicleServiceRecord | None:
        if not proof.vehicle_id:
            return None
        record = VehicleServiceRecord(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            vehicle_id=proof.vehicle_id,
            proof_id=proof.id,
            work_summary=proof.work_summary,
            odometer_km=proof.odometer_km,
            performed_at=proof.performed_at,
            verified=True,
        )
        self.db.add(record)
        return record

    def _close_recommendation_if_linked(self, *, proof: ServiceCompletionProof) -> None:
        recommendation_id = self._resolve_recommendation_id(proof)
        if not recommendation_id:
            return
        recommendation = (
            self.db.query(VehicleRecommendation)
            .filter(VehicleRecommendation.id == recommendation_id)
            .one_or_none()
        )
        if not recommendation:
            return
        if recommendation.status == VehicleRecommendationStatus.DONE:
            return
        recommendation.status = VehicleRecommendationStatus.DONE

    def _create_dispute_case(self, *, proof: ServiceCompletionProof) -> Case:
        existing = (
            self.db.query(Case)
            .filter(Case.case_source_ref_type == "SERVICE_PROOF")
            .filter(Case.case_source_ref_id == proof.id)
            .one_or_none()
        )
        if existing:
            return existing
        case = Case(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            kind=CaseKind.ORDER,
            entity_id=str(proof.booking_id),
            title=f"Service proof dispute {proof.id}",
            priority=CasePriority.MEDIUM,
            created_by=self.request_ctx.actor_id if self.request_ctx else None,
            case_source_ref_type="SERVICE_PROOF",
            case_source_ref_id=proof.id,
        )
        self.db.add(case)
        return case
