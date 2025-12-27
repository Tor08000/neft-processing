from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetworkStatus,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.schemas.fuel import (
    DeclineCode,
    FuelAuthorizeRequest,
    FuelAuthorizeResponse,
    FuelDeclineExplain,
    RiskExplain,
)
from app.services.audit_service import RequestContext
from app.services.decision import DecisionEngine, DecisionOutcome
from app.services.fuel import events, limits, repository, risk_context
from app.services.legal_graph.registry import LegalGraphRegistry


@dataclass(frozen=True)
class AuthorizationResult:
    response: FuelAuthorizeResponse
    transaction: FuelTransaction | None = None


def _decline_response(
    *,
    decline_code: DeclineCode,
    message: str,
    limit_explain=None,
    risk_explain=None,
) -> FuelAuthorizeResponse:
    explain = FuelDeclineExplain(
        decline_code=decline_code,
        message=message,
        limit_explain=limit_explain,
        risk_explain=risk_explain,
    )
    return FuelAuthorizeResponse(status="DECLINE", decline_code=decline_code, explain=explain)


def _legal_graph(
    db: Session,
    *,
    tenant_id: int,
    transaction: FuelTransaction,
    card: FuelCard,
    vehicle: FleetVehicle | None,
    station_id: str,
    risk_decision_id: str | None,
    request_ctx: RequestContext | None,
) -> None:
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    tx_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.FUEL_TRANSACTION,
        ref_id=str(transaction.id),
        ref_table="fuel_transactions",
    ).node
    card_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.CARD,
        ref_id=str(card.id),
        ref_table="fuel_cards",
    ).node
    registry.link(
        tenant_id=tenant_id,
        src_node_id=tx_node.id,
        dst_node_id=card_node.id,
        edge_type=LegalEdgeType.RELATES_TO,
    )
    station_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.FUEL_STATION,
        ref_id=str(station_id),
        ref_table="fuel_stations",
    ).node
    registry.link(
        tenant_id=tenant_id,
        src_node_id=tx_node.id,
        dst_node_id=station_node.id,
        edge_type=LegalEdgeType.RELATES_TO,
    )
    if vehicle:
        vehicle_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.VEHICLE,
            ref_id=str(vehicle.id),
            ref_table="fleet_vehicles",
        ).node
        registry.link(
            tenant_id=tenant_id,
            src_node_id=tx_node.id,
            dst_node_id=vehicle_node.id,
            edge_type=LegalEdgeType.RELATES_TO,
        )
    if risk_decision_id:
        risk_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.RISK_DECISION,
            ref_id=str(risk_decision_id),
            ref_table="risk_decisions",
        ).node
        registry.link(
            tenant_id=tenant_id,
            src_node_id=tx_node.id,
            dst_node_id=risk_node.id,
            edge_type=LegalEdgeType.GATED_BY_RISK,
        )


def _resolve_vehicle_and_driver(
    *,
    db: Session,
    card: FuelCard,
    payload: FuelAuthorizeRequest,
) -> tuple[FleetVehicle | None, FleetDriver | None]:
    vehicle = None
    if payload.vehicle_plate:
        vehicle = repository.get_vehicle_by_plate(db, client_id=card.client_id, plate_number=payload.vehicle_plate)
    if vehicle is None and card.vehicle_id:
        vehicle = repository.get_vehicle_by_id(db, vehicle_id=str(card.vehicle_id))

    driver = None
    if payload.driver_id:
        driver = repository.get_driver_by_id(db, driver_id=payload.driver_id)
    if driver is None and card.driver_id:
        driver = repository.get_driver_by_id(db, driver_id=str(card.driver_id))

    return vehicle, driver


def authorize_fuel_tx(
    db: Session,
    *,
    payload: FuelAuthorizeRequest,
    request_ctx: RequestContext | None = None,
) -> AuthorizationResult:
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)
    card = repository.get_card_by_token(db, tenant_id=None, card_token=payload.card_token)
    if not card:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.CARD_NOT_FOUND,
                message="Card token not found",
            )
        )
    if card.status == FuelCardStatus.BLOCKED:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.CARD_BLOCKED,
                message="Card is blocked",
            )
        )
    if card.status == FuelCardStatus.EXPIRED:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.CARD_EXPIRED,
                message="Card expired",
            )
        )

    network = repository.get_network_by_code(db, network_code=payload.network_code)
    if not network or network.status != FuelNetworkStatus.ACTIVE:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.NETWORK_NOT_SUPPORTED,
                message="Fuel network not supported",
            )
        )
    station = repository.get_station_by_code(
        db, network_id=str(network.id), station_code=payload.station_code or ""
    )
    if not station:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.STATION_NOT_FOUND,
                message="Station not found",
            )
        )
    if station.status != FuelStationStatus.ACTIVE:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.STATION_INACTIVE,
                message="Station is inactive",
            )
        )

    existing = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.external_ref == payload.external_ref)
        .one_or_none()
        if payload.external_ref
        else None
    )
    if existing:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.DUPLICATE_EXTERNAL_REF,
                message="Duplicate external reference",
            )
        )

    vehicle, driver = _resolve_vehicle_and_driver(db=db, card=card, payload=payload)
    if payload.vehicle_plate and vehicle is None:
        return AuthorizationResult(
            response=_decline_response(
                decline_code=DeclineCode.CARD_NOT_ASSIGNED,
                message="Vehicle not assigned",
            )
        )

    volume_ml = int(payload.volume_liters * 1000)
    amount_minor = int(payload.unit_price * volume_ml / 1000)
    base_meta = payload.meta or {}

    limit_decision = limits.check_limits(
        db=db,
        tenant_id=card.tenant_id,
        client_id=card.client_id,
        card_id=str(card.id),
        card_group_id=str(card.card_group_id) if card.card_group_id else None,
        vehicle_id=str(vehicle.id) if vehicle else None,
        driver_id=str(driver.id) if driver else None,
        at=occurred_at,
        amount_minor=amount_minor,
        volume_ml=volume_ml,
        currency=payload.currency,
    )
    if not limit_decision.allowed:
        transaction = FuelTransaction(
            tenant_id=card.tenant_id,
            client_id=card.client_id,
            card_id=card.id,
            vehicle_id=vehicle.id if vehicle else None,
            driver_id=driver.id if driver else None,
            station_id=station.id,
            network_id=network.id,
            occurred_at=occurred_at,
            fuel_type=payload.fuel_type,
            volume_ml=volume_ml,
            unit_price_minor=payload.unit_price,
            amount_total_minor=amount_minor,
            currency=payload.currency,
            status=FuelTransactionStatus.DECLINED,
            decline_code=limit_decision.decline_code.value if limit_decision.decline_code else None,
            external_ref=payload.external_ref,
            meta={**base_meta, "limit_explain": limit_decision.explain.model_dump() if limit_decision.explain else None},
        )
        transaction = repository.add_fuel_transaction(db, transaction)
        events.audit_event(
            db,
            event_type=events.FUEL_EVENT_DECLINED,
            entity_id=str(transaction.id),
            payload={
                "status": transaction.status.value,
                "decline_code": transaction.decline_code,
                "limit_explain": limit_decision.explain.model_dump() if limit_decision.explain else None,
            },
            request_ctx=request_ctx,
        )
        response = _decline_response(
            decline_code=limit_decision.decline_code or DeclineCode.LIMIT_EXCEEDED_AMOUNT,
            message="Limit exceeded",
            limit_explain=limit_decision.explain,
        )
        response.transaction_id = str(transaction.id)
        return AuthorizationResult(response=response, transaction=transaction)

    risk_result = risk_context.build_risk_context_for_fuel_tx(
        tenant_id=card.tenant_id,
        client_id=card.client_id,
        card=card,
        station=station,
        vehicle=vehicle,
        driver=driver,
        fuel_type=payload.fuel_type,
        amount_minor=amount_minor,
        volume_ml=volume_ml,
        occurred_at=occurred_at,
        currency=payload.currency,
        subject_id=payload.external_ref or str(card.id),
        db=db,
    )
    decision = DecisionEngine(db).evaluate(risk_result.decision_context)
    risk_explain = RiskExplain(
        decision=decision.outcome.value,
        score=decision.risk_score,
        thresholds=decision.explain.get("thresholds") if isinstance(decision.explain, dict) else None,
        policy=decision.explain.get("policy") if isinstance(decision.explain, dict) else None,
        factors=decision.explain.get("factors") if isinstance(decision.explain, dict) else None,
        decision_hash=decision.explain.get("decision_hash") if isinstance(decision.explain, dict) else None,
        payload=decision.to_payload(),
    )
    risk_decision_id = repository.get_risk_decision_id(db, decision_id=decision.decision_id)

    status = FuelTransactionStatus.AUTHORIZED
    decline_code: DeclineCode | None = None
    if decision.outcome == DecisionOutcome.ALLOW and risk_result.decline_code:
        status = FuelTransactionStatus.DECLINED
        decline_code = risk_result.decline_code
    if decision.outcome == DecisionOutcome.MANUAL_REVIEW:
        status = FuelTransactionStatus.REVIEW_REQUIRED
        decline_code = DeclineCode.RISK_REVIEW_REQUIRED
    elif decision.outcome == DecisionOutcome.DECLINE:
        status = FuelTransactionStatus.DECLINED
        decline_code = DeclineCode.RISK_BLOCK
        if risk_result.decline_code == DeclineCode.VELOCITY_SPIKE:
            decline_code = DeclineCode.VELOCITY_SPIKE
        elif risk_result.decline_code == DeclineCode.TANK_SANITY_EXCEEDED:
            decline_code = DeclineCode.TANK_SANITY_EXCEEDED

    transaction = FuelTransaction(
        tenant_id=card.tenant_id,
        client_id=card.client_id,
        card_id=card.id,
        vehicle_id=vehicle.id if vehicle else None,
        driver_id=driver.id if driver else None,
        station_id=station.id,
        network_id=network.id,
        occurred_at=occurred_at,
        fuel_type=payload.fuel_type,
        volume_ml=volume_ml,
        unit_price_minor=payload.unit_price,
        amount_total_minor=amount_minor,
        currency=payload.currency,
        status=status,
        decline_code=decline_code.value if decline_code else None,
        risk_decision_id=risk_decision_id,
        external_ref=payload.external_ref,
        meta={**base_meta, "risk_explain": risk_explain.model_dump()},
    )
    transaction = repository.add_fuel_transaction(db, transaction)

    event_type = events.FUEL_EVENT_AUTHORIZED
    if status == FuelTransactionStatus.REVIEW_REQUIRED:
        event_type = events.FUEL_EVENT_REVIEW
    elif status == FuelTransactionStatus.DECLINED:
        event_type = events.FUEL_EVENT_DECLINED

    events.audit_event(
        db,
        event_type=event_type,
        entity_id=str(transaction.id),
        payload={
            "status": transaction.status.value,
            "decline_code": transaction.decline_code,
            "risk_explain": risk_explain.model_dump(),
        },
        request_ctx=request_ctx,
    )
    _legal_graph(
        db,
        tenant_id=card.tenant_id,
        transaction=transaction,
        card=card,
        vehicle=vehicle,
        station_id=str(station.id),
        risk_decision_id=risk_decision_id,
        request_ctx=request_ctx,
    )

    response_status = "ALLOW"
    if status == FuelTransactionStatus.REVIEW_REQUIRED:
        response_status = "REVIEW"
    elif status == FuelTransactionStatus.DECLINED:
        response_status = "DECLINE"

    response = FuelAuthorizeResponse(
        status=response_status,
        transaction_id=str(transaction.id),
        decline_code=decline_code,
        explain=FuelDeclineExplain(
            decline_code=decline_code or DeclineCode.RISK_BLOCK,
            message="Risk decision",
            risk_explain=risk_explain,
        )
        if status != FuelTransactionStatus.AUTHORIZED
        else None,
    )
    return AuthorizationResult(response=response, transaction=transaction)


__all__ = ["AuthorizationResult", "authorize_fuel_tx"]
