from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.cases import CaseEventType
from app.models.fuel import (
    FuelCard,
    FuelIngestJob,
    FuelIngestJobStatus,
    FuelMerchant,
    FuelNetwork,
    FuelNetworkStatus,
    FuelProvider,
    FuelProviderStatus,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.schemas.fleet_ingestion import FleetIngestRequestIn
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.fleet_limit_check import apply_limit_checks
from app.services.fleet_metrics import metrics as fleet_metrics

CATEGORY_MAP = {
    "FUEL": "FUEL",
    "GAS": "FUEL",
    "DIESEL": "FUEL",
}

MERCHANT_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


class FleetIngestionError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_category(raw: str | None) -> str | None:
    if not raw:
        return None
    mapped = CATEGORY_MAP.get(raw.upper())
    return mapped or raw.strip().upper()


def _normalize_merchant_key(name: str | None, station_id: str | None) -> str | None:
    value = name or station_id
    if not value:
        return None
    lowered = value.strip().lower()
    normalized = MERCHANT_KEY_PATTERN.sub("", lowered)
    return normalized or lowered


def _ensure_provider(db: Session, *, provider_code: str) -> FuelProvider:
    provider = db.query(FuelProvider).filter(FuelProvider.code == provider_code).one_or_none()
    if provider:
        return provider
    provider = FuelProvider(code=provider_code, name=provider_code, status=FuelProviderStatus.ACTIVE)
    db.add(provider)
    db.flush()
    return provider


def _ensure_network(db: Session, *, provider_code: str) -> FuelNetwork:
    network = db.query(FuelNetwork).filter(FuelNetwork.provider_code == provider_code).one_or_none()
    if network:
        return network
    network = FuelNetwork(name=provider_code, provider_code=provider_code, status=FuelNetworkStatus.ACTIVE)
    db.add(network)
    db.flush()
    return network


def _ensure_station(db: Session, *, network_id: str, station_external_id: str | None, name: str | None) -> FuelStation:
    station = None
    if station_external_id:
        station = (
            db.query(FuelStation)
            .filter(FuelStation.network_id == network_id)
            .filter(FuelStation.station_code == station_external_id)
            .one_or_none()
        )
    if station:
        return station
    station = FuelStation(
        network_id=network_id,
        name=name or station_external_id or "Fleet station",
        station_code=station_external_id,
        status="ACTIVE",
    )
    db.add(station)
    db.flush()
    return station


def _resolve_card(
    db: Session,
    *,
    card_alias: str | None,
    masked_pan: str | None,
    client_ref: str | None,
) -> FuelCard | None:
    query = db.query(FuelCard)
    if card_alias:
        query = query.filter(FuelCard.card_alias == card_alias)
    if masked_pan:
        query = query.filter(FuelCard.masked_pan == masked_pan)
    if client_ref:
        query = query.filter(FuelCard.client_id == client_ref)
    results = query.all()
    if not results:
        return None
    if len(results) > 1:
        raise FleetIngestionError("ambiguous_card")
    return results[0]


def _ensure_merchant(
    db: Session,
    *,
    provider_code: str,
    merchant_key: str | None,
    display_name: str | None,
    category: str | None,
) -> None:
    if not merchant_key or not display_name:
        return
    existing = (
        db.query(FuelMerchant)
        .filter(FuelMerchant.provider_code == provider_code)
        .filter(FuelMerchant.merchant_key == merchant_key)
        .one_or_none()
    )
    if existing:
        return
    merchant = FuelMerchant(
        provider_code=provider_code,
        merchant_key=merchant_key,
        display_name=display_name,
        category_default=category,
    )
    db.add(merchant)


def _find_duplicate(
    db: Session,
    *,
    provider_code: str,
    provider_tx_id: str | None,
    external_ref: str | None,
    client_id: str,
    card_id: str,
    occurred_at: datetime,
    amount: Decimal,
    volume_liters: Decimal | None,
    merchant_key: str | None,
) -> FuelTransaction | None:
    if provider_tx_id:
        return (
            db.query(FuelTransaction)
            .filter(FuelTransaction.provider_code == provider_code)
            .filter(FuelTransaction.provider_tx_id == provider_tx_id)
            .one_or_none()
        )
    if external_ref:
        return (
            db.query(FuelTransaction)
            .filter(FuelTransaction.provider_code == provider_code)
            .filter(FuelTransaction.external_ref == external_ref)
            .one_or_none()
        )
    return (
        db.query(FuelTransaction)
        .filter(FuelTransaction.client_id == client_id)
        .filter(FuelTransaction.card_id == card_id)
        .filter(FuelTransaction.occurred_at == occurred_at)
        .filter(FuelTransaction.amount == amount)
        .filter(FuelTransaction.volume_liters == volume_liters)
        .filter(FuelTransaction.merchant_key == merchant_key)
        .one_or_none()
    )


def ingest_transactions(
    db: Session,
    *,
    payload: FleetIngestRequestIn,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FuelIngestJob:
    existing = db.query(FuelIngestJob).filter(FuelIngestJob.idempotency_key == payload.idempotency_key).one_or_none()
    if existing:
        return existing

    _ensure_provider(db, provider_code=payload.provider_code)
    job = FuelIngestJob(
        provider_code=payload.provider_code,
        client_id=None,
        batch_ref=payload.batch_ref,
        idempotency_key=payload.idempotency_key,
        status=FuelIngestJobStatus.RECEIVED,
        total_count=len(payload.items),
        inserted_count=0,
        deduped_count=0,
    )
    db.add(job)
    db.flush()

    try:
        network = _ensure_network(db, provider_code=payload.provider_code)
        inserted_count = 0
        deduped_count = 0
        for item in payload.items:
            card = _resolve_card(
                db,
                card_alias=item.card_alias,
                masked_pan=item.masked_pan,
                client_ref=item.client_ref,
            )
            if not card:
                raise FleetIngestionError("card_not_found")
            if job.client_id and job.client_id != card.client_id:
                raise FleetIngestionError("multi_client_batch")
            if not job.client_id:
                job.client_id = card.client_id
            category = _normalize_category(item.category)
            merchant_key = _normalize_merchant_key(item.merchant_name, item.station_id)
            external_ref = item.external_ref or item.provider_tx_id
            duplicate = _find_duplicate(
                db,
                provider_code=payload.provider_code,
                provider_tx_id=item.provider_tx_id,
                external_ref=external_ref,
                client_id=card.client_id,
                card_id=str(card.id),
                occurred_at=item.occurred_at,
                amount=item.amount,
                volume_liters=item.volume_liters,
                merchant_key=merchant_key,
            )
            if duplicate:
                deduped_count += 1
                fleet_metrics.mark_ingest_item("deduped")
                continue
            station = _ensure_station(
                db,
                network_id=str(network.id),
                station_external_id=item.station_id,
                name=item.merchant_name,
            )
            amount_minor = int((item.amount * Decimal("100")).quantize(Decimal("1")))
            volume_ml = (
                int((item.volume_liters * Decimal("1000")).quantize(Decimal("1")))
                if item.volume_liters is not None
                else 0
            )
            tx = FuelTransaction(
                tenant_id=fleet_service._resolve_tenant_id(principal),
                client_id=card.client_id,
                card_id=str(card.id),
                vehicle_id=card.vehicle_id,
                driver_id=card.driver_id,
                station_id=station.id,
                network_id=network.id,
                occurred_at=item.occurred_at,
                fuel_type=FuelType.OTHER,
                volume_ml=volume_ml,
                unit_price_minor=0,
                amount_total_minor=amount_minor,
                currency=item.currency or "RUB",
                status=FuelTransactionStatus.SETTLED,
                provider_code=payload.provider_code,
                provider_tx_id=item.provider_tx_id,
                merchant_key=merchant_key,
                external_ref=external_ref,
                amount=item.amount,
                volume_liters=item.volume_liters,
                category=category,
                merchant_name=item.merchant_name,
                station_external_id=item.station_id,
                location=item.location,
                raw_payload_redacted=redact_deep(item.raw_payload, "", include_hash=True)
                if item.raw_payload
                else None,
            )
            db.add(tx)
            db.flush()
            apply_limit_checks(
                db,
                transaction=tx,
                principal=principal,
                request_id=request_id,
                trace_id=trace_id,
            )
            _ensure_merchant(
                db,
                provider_code=payload.provider_code,
                merchant_key=merchant_key,
                display_name=item.merchant_name,
                category=category,
            )
            inserted_count += 1
            fleet_metrics.mark_ingest_item("inserted")
            fleet_metrics.mark_transaction()
        job.status = FuelIngestJobStatus.PROCESSED
        job.inserted_count = inserted_count
        job.deduped_count = deduped_count
        job.audit_event_id = fleet_service._emit_event(
            db,
            client_id=job.client_id or payload.items[0].client_ref or "unknown",
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
            event_type=CaseEventType.FLEET_TRANSACTIONS_INGESTED,
            payload={
                "provider_code": payload.provider_code,
                "batch_ref": payload.batch_ref,
                "idempotency_key": payload.idempotency_key,
                "total_count": len(payload.items),
                "inserted_count": inserted_count,
                "deduped_count": deduped_count,
            },
        )
        fleet_metrics.mark_ingest_job("PROCESSED", payload.provider_code)
        return job
    except Exception as exc:
        job.status = FuelIngestJobStatus.FAILED
        job.error = str(exc)[:500]
        job.audit_event_id = fleet_service._emit_event(
            db,
            client_id=job.client_id or payload.items[0].client_ref or "unknown",
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
            event_type=CaseEventType.FLEET_INGEST_FAILED,
            payload={
                "provider_code": payload.provider_code,
                "batch_ref": payload.batch_ref,
                "idempotency_key": payload.idempotency_key,
                "error": job.error,
            },
        )
        fleet_metrics.mark_ingest_job("FAILED", payload.provider_code)
        raise


__all__ = ["ingest_transactions", "FleetIngestionError"]
