from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.types import new_uuid_str
from app.models.marketplace_contracts import (
    Contract,
    ContractEvent,
    ContractObligation,
    ContractStatus,
    ContractVersion,
    SLAResult,
)
from app.schemas.admin.marketplace_contracts import (
    ContractCreateRequest,
    ContractEventCreateRequest,
    ContractEventResponse,
    ContractListResponse,
    ContractObligationResponse,
    ContractResponse,
    ContractTerminateRequest,
    ContractVersionCreateRequest,
    ContractVersionResponse,
    SLAEvaluateRequest,
    SLAResultResponse,
    SLAResultsListResponse,
)
from app.services.audit_service import AuditService, request_context_from_request
from app.services.case_event_redaction import redact_deep
from app.services.decision_memory.records import record_decision_memory
from app.services.sla_service import create_contract_event, evaluate_sla

router = APIRouter(prefix="/contracts", tags=["admin"])


def _contract_response(
    contract: Contract,
    *,
    versions: list[ContractVersion] | None = None,
    obligations: list[ContractObligation] | None = None,
) -> ContractResponse:
    return ContractResponse(
        id=str(contract.id),
        contract_number=contract.contract_number,
        contract_type=contract.contract_type,
        party_a_type=contract.party_a_type,
        party_a_id=str(contract.party_a_id),
        party_b_type=contract.party_b_type,
        party_b_id=str(contract.party_b_id),
        currency=contract.currency,
        effective_from=contract.effective_from,
        effective_to=contract.effective_to,
        status=contract.status,
        created_at=contract.created_at,
        audit_event_id=str(contract.audit_event_id),
        versions=[
            ContractVersionResponse(
                id=str(version.id),
                contract_id=str(version.contract_id),
                version=version.version,
                terms=version.terms,
                created_at=version.created_at,
                audit_event_id=str(version.audit_event_id),
            )
            for version in (versions or [])
        ],
        obligations=[
            ContractObligationResponse(
                id=str(obligation.id),
                contract_id=str(obligation.contract_id),
                obligation_type=obligation.obligation_type,
                metric=obligation.metric,
                threshold=Decimal(str(obligation.threshold)),
                comparison=obligation.comparison,
                window=obligation.window,
                penalty_type=obligation.penalty_type,
                penalty_value=Decimal(str(obligation.penalty_value)),
                created_at=obligation.created_at,
            )
            for obligation in (obligations or [])
        ],
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract_endpoint(
    payload: ContractCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ContractResponse:
    existing = (
        db.query(Contract)
        .filter(Contract.contract_number == payload.contract_number)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=409, detail="contract_number_exists")

    request_ctx = request_context_from_request(request)
    contract_id = new_uuid_str()
    audit = AuditService(db).audit(
        event_type="CONTRACT_CREATED",
        entity_type="contract",
        entity_id=contract_id,
        action="CONTRACT_CREATED",
        after={
            "contract_number": payload.contract_number,
            "contract_type": payload.contract_type,
            "party_a_type": payload.party_a_type,
            "party_b_type": payload.party_b_type,
            "currency": payload.currency,
        },
        request_ctx=request_ctx,
    )

    contract = Contract(
        id=contract_id,
        contract_number=payload.contract_number,
        contract_type=payload.contract_type,
        party_a_type=payload.party_a_type,
        party_a_id=payload.party_a_id,
        party_b_type=payload.party_b_type,
        party_b_id=payload.party_b_id,
        currency=payload.currency,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status=ContractStatus.ACTIVE.value,
        audit_event_id=audit.id,
    )
    db.add(contract)

    version_audit = AuditService(db).audit(
        event_type="CONTRACT_VERSIONED",
        entity_type="contract_version",
        entity_id=contract_id,
        action="CONTRACT_VERSIONED",
        after={"version": 1, "terms": redact_deep(payload.terms, "terms", include_hash=True)},
        request_ctx=request_ctx,
    )
    version = ContractVersion(
        id=new_uuid_str(),
        contract_id=contract_id,
        version=1,
        terms=redact_deep(payload.terms, "terms", include_hash=True),
        audit_event_id=version_audit.id,
    )
    db.add(version)

    obligations: list[ContractObligation] = []
    for obligation in payload.obligations:
        record = ContractObligation(
            id=new_uuid_str(),
            contract_id=contract_id,
            obligation_type=obligation.obligation_type,
            metric=obligation.metric,
            threshold=obligation.threshold,
            comparison=obligation.comparison,
            window=obligation.window,
            penalty_type=obligation.penalty_type,
            penalty_value=obligation.penalty_value,
        )
        obligations.append(record)
        db.add(record)

    record_decision_memory(
        db,
        case_id=None,
        decision_type="contract_created",
        decision_ref_id=contract_id,
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=request_ctx.actor_id if request_ctx else None,
        context_snapshot={"contract_number": payload.contract_number},
        rationale="Contract created",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(audit.id),
    )

    db.commit()
    return _contract_response(contract, versions=[version], obligations=obligations)


@router.get("", response_model=ContractListResponse)
def list_contracts_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ContractListResponse:
    query = db.query(Contract)
    total = query.count()
    items = (
        query.order_by(Contract.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    responses = []
    for contract in items:
        responses.append(_contract_response(contract))
    return ContractListResponse(items=responses, total=total, limit=limit, offset=offset)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract_endpoint(contract_id: str, db: Session = Depends(get_db)) -> ContractResponse:
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")
    versions = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version.desc())
        .all()
    )
    obligations = (
        db.query(ContractObligation)
        .filter(ContractObligation.contract_id == contract_id)
        .order_by(ContractObligation.created_at.asc())
        .all()
    )
    return _contract_response(contract, versions=versions, obligations=obligations)


@router.post("/{contract_id}/terminate", response_model=ContractEventResponse)
def terminate_contract_endpoint(
    contract_id: str,
    payload: ContractTerminateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ContractEventResponse:
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")
    request_ctx = request_context_from_request(request)
    event = create_contract_event(
        db,
        contract_id=contract_id,
        event_type="CONTRACT_TERMINATED",
        occurred_at=datetime.now(timezone.utc),
        payload={"reason": payload.reason},
        request_ctx=request_ctx,
    )
    db.commit()
    return ContractEventResponse(
        id=str(event.id),
        contract_id=str(event.contract_id),
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        payload=event.payload,
        hash=event.hash,
        signature=event.signature,
        signature_alg=event.signature_alg,
        signing_key_id=event.signing_key_id,
        signed_at=event.signed_at,
        audit_event_id=str(event.audit_event_id),
    )


@router.post("/{contract_id}/versions", response_model=ContractVersionResponse, status_code=201)
def add_contract_version_endpoint(
    contract_id: str,
    payload: ContractVersionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ContractVersionResponse:
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")
    request_ctx = request_context_from_request(request)
    latest_version = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version.desc())
        .first()
    )
    version_number = (latest_version.version if latest_version else 0) + 1
    audit = AuditService(db).audit(
        event_type="CONTRACT_VERSIONED",
        entity_type="contract_version",
        entity_id=contract_id,
        action="CONTRACT_VERSIONED",
        after={"version": version_number, "terms": redact_deep(payload.terms, "terms", include_hash=True)},
        request_ctx=request_ctx,
    )
    version = ContractVersion(
        id=new_uuid_str(),
        contract_id=contract_id,
        version=version_number,
        terms=redact_deep(payload.terms, "terms", include_hash=True),
        audit_event_id=audit.id,
    )
    db.add(version)

    for obligation in payload.obligations:
        db.add(
            ContractObligation(
                id=new_uuid_str(),
                contract_id=contract_id,
                obligation_type=obligation.obligation_type,
                metric=obligation.metric,
                threshold=obligation.threshold,
                comparison=obligation.comparison,
                window=obligation.window,
                penalty_type=obligation.penalty_type,
                penalty_value=obligation.penalty_value,
            )
        )

    record_decision_memory(
        db,
        case_id=None,
        decision_type="contract_version",
        decision_ref_id=version.id,
        decision_at=datetime.now(timezone.utc),
        decided_by_user_id=request_ctx.actor_id if request_ctx else None,
        context_snapshot={"contract_id": contract_id, "version": version_number},
        rationale="Contract version added",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(audit.id),
    )

    db.commit()
    return ContractVersionResponse(
        id=str(version.id),
        contract_id=str(version.contract_id),
        version=version.version,
        terms=version.terms,
        created_at=version.created_at,
        audit_event_id=str(version.audit_event_id),
    )


@router.post("/{contract_id}/events", response_model=ContractEventResponse, status_code=201)
def record_contract_event_endpoint(
    contract_id: str,
    payload: ContractEventCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ContractEventResponse:
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")
    request_ctx = request_context_from_request(request)
    event = create_contract_event(
        db,
        contract_id=contract_id,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at,
        payload=payload.payload,
        request_ctx=request_ctx,
    )
    db.commit()
    return ContractEventResponse(
        id=str(event.id),
        contract_id=str(event.contract_id),
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        payload=event.payload,
        hash=event.hash,
        signature=event.signature,
        signature_alg=event.signature_alg,
        signing_key_id=event.signing_key_id,
        signed_at=event.signed_at,
        audit_event_id=str(event.audit_event_id),
    )


@router.get("/{contract_id}/events", response_model=list[ContractEventResponse])
def list_contract_events_endpoint(
    contract_id: str,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ContractEventResponse]:
    events = (
        db.query(ContractEvent)
        .filter(ContractEvent.contract_id == contract_id)
        .order_by(ContractEvent.occurred_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        ContractEventResponse(
            id=str(event.id),
            contract_id=str(event.contract_id),
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            payload=event.payload,
            hash=event.hash,
            signature=event.signature,
            signature_alg=event.signature_alg,
            signing_key_id=event.signing_key_id,
            signed_at=event.signed_at,
            audit_event_id=str(event.audit_event_id),
        )
        for event in events
    ]


@router.post("/{contract_id}/sla/evaluate", response_model=list[SLAResultResponse])
def evaluate_sla_endpoint(
    contract_id: str,
    payload: SLAEvaluateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> list[SLAResultResponse]:
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")
    request_ctx = request_context_from_request(request)
    summary = evaluate_sla(
        db,
        contract_id=contract_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        request_ctx=request_ctx,
    )
    db.commit()
    return [
        SLAResultResponse(
            id=str(result.id),
            contract_id=str(result.contract_id),
            obligation_id=str(result.obligation_id),
            period_start=result.period_start,
            period_end=result.period_end,
            measured_value=Decimal(str(result.measured_value)),
            status=result.status,
            created_at=result.created_at,
            audit_event_id=str(result.audit_event_id),
        )
        for result in summary.results
    ]


@router.get("/{contract_id}/sla/results", response_model=SLAResultsListResponse)
def list_sla_results_endpoint(
    contract_id: str,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SLAResultsListResponse:
    query = db.query(SLAResult).filter(SLAResult.contract_id == contract_id)
    total = query.count()
    items = (
        query.order_by(SLAResult.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SLAResultsListResponse(
        items=[
            SLAResultResponse(
                id=str(result.id),
                contract_id=str(result.contract_id),
                obligation_id=str(result.obligation_id),
                period_start=result.period_start,
                period_end=result.period_end,
                measured_value=Decimal(str(result.measured_value)),
                status=result.status,
                created_at=result.created_at,
                audit_event_id=str(result.audit_event_id),
            )
            for result in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )

