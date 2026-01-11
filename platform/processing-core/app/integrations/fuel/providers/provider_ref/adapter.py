from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.integrations.fuel.models import (
    FuelProviderAuthorizationDecision,
    FuelProviderBatch,
    FuelProviderBatchStatus,
    FuelProviderRecord,
    FuelProviderRecordStatus,
)
from app.integrations.fuel.providers.protocols import (
    AuthorizeRequest,
    AuthorizeResult,
    IngestBatchRequest,
    IngestResult,
    NotSupportedError,
    ReconciliationResult,
    SettlementExportRequest,
    SettlementResult,
)
from app.models.client import Client
from app.models.fuel import (
    FleetOfflineProfile,
    FleetOfflineProfileStatus,
    FuelCard,
    FuelCardStatus,
    FuelTransaction,
    FuelTransactionAuthType,
    FuelTransactionStatus,
    FuelType,
    FuelUnmatchedRecord,
)
from app.services import fleet_ingestion_service
from app.services.fleet_limit_check import apply_limit_checks
from app.services.fleet_service import _resolve_tenant_id

PRODUCT_FUEL_TYPE = {
    "DIESEL": FuelType.DIESEL,
    "AI-92": FuelType.AI92,
    "AI-95": FuelType.AI95,
    "AI-98": FuelType.AI98,
    "GAS": FuelType.GAS,
}


@dataclass(frozen=True)
class ProviderRefRecord:
    provider_tx_id: str
    occurred_at: datetime
    card_token: str | None
    card_pan_masked: str | None
    station_id: str | None
    product_code: str | None
    quantity: Decimal
    amount: Decimal
    currency: str
    auth_flag: str | None
    status: str | None
    rrn: str | None
    client_ref: str | None
    raw_payload: dict


class ProviderRefAdapter:
    code = "provider_ref"

    def ingest_batch(self, db: Session, request: IngestBatchRequest) -> IngestResult:
        batch = (
            db.query(FuelProviderBatch)
            .filter(FuelProviderBatch.provider_code == self.code)
            .filter(FuelProviderBatch.batch_key == request.batch_key)
            .one_or_none()
        )
        if not batch:
            batch = FuelProviderBatch(
                provider_code=self.code,
                batch_key=request.batch_key,
                source=request.source,
                status=FuelProviderBatchStatus.RECEIVED,
                payload_ref=str(request.payload_ref) if isinstance(request.payload_ref, str) else None,
            )
            db.add(batch)
            db.flush()

        records = list(self._parse_payload(request.payload_ref))
        batch.status = FuelProviderBatchStatus.PARSED
        batch.records_total = len(records)

        applied = 0
        duplicates = 0
        failed = 0
        offline_dates: list[datetime] = []
        offline_snapshot: dict | None = None

        for record in records:
            existing = (
                db.query(FuelTransaction)
                .filter(FuelTransaction.provider_code == self.code)
                .filter(FuelTransaction.provider_tx_id == record.provider_tx_id)
                .one_or_none()
            )
            content_hash = _content_hash(record.raw_payload)
            if existing:
                if existing.content_hash and existing.content_hash != content_hash:
                    failed += 1
                    batch.error = "provider_mutation_detected"
                    self._record_batch_item(
                        db,
                        batch=batch,
                        record=record,
                        status=FuelProviderRecordStatus.FAILED,
                        error="PROVIDER_MUTATION_DETECTED",
                    )
                else:
                    duplicates += 1
                continue

            card = _resolve_card(db, record=record)
            if not card:
                failed += 1
                self._record_unmatched(db, batch=batch, record=record, reason="card_not_found")
                self._record_batch_item(
                    db,
                    batch=batch,
                    record=record,
                    status=FuelProviderRecordStatus.FAILED,
                    error="CARD_NOT_FOUND",
                )
                continue

            network = fleet_ingestion_service._ensure_network(db, provider_code=self.code)
            station = fleet_ingestion_service._ensure_station(
                db,
                network_id=str(network.id),
                station_external_id=record.station_id,
                name=record.station_id,
            )
            volume_ml = int((record.quantity * Decimal("1000")).quantize(Decimal("1")))
            amount_minor = int((record.amount * Decimal("100")).quantize(Decimal("1")))
            unit_price_minor = 0
            if record.quantity > 0:
                unit_price_minor = int((record.amount / record.quantity * Decimal("100")).quantize(Decimal("1")))
            auth_type = _auth_type(record.auth_flag)
            if auth_type == FuelTransactionAuthType.OFFLINE:
                offline_dates.append(record.occurred_at)
                if not offline_snapshot:
                    offline_snapshot = _offline_profile_snapshot(db, card=card, client_id=card.client_id)
            tx = FuelTransaction(
                tenant_id=_resolve_tenant_id(None),
                client_id=card.client_id,
                card_id=str(card.id),
                vehicle_id=card.vehicle_id,
                driver_id=card.driver_id,
                station_id=station.id,
                network_id=network.id,
                occurred_at=record.occurred_at,
                fuel_type=PRODUCT_FUEL_TYPE.get((record.product_code or "").upper(), FuelType.OTHER),
                volume_ml=volume_ml,
                unit_price_minor=unit_price_minor,
                amount_total_minor=amount_minor,
                currency=record.currency,
                status=_status(record.status),
                auth_type=auth_type,
                provider_code=self.code,
                provider_tx_id=record.provider_tx_id,
                provider_batch_key=request.batch_key,
                merchant_key=record.station_id,
                external_ref=record.rrn,
                amount=record.amount,
                volume_liters=record.quantity,
                category=record.product_code,
                merchant_name=None,
                station_external_id=record.station_id,
                location=None,
                raw_payload=record.raw_payload,
                content_hash=content_hash,
            )
            db.add(tx)
            db.flush()
            apply_limit_checks(db, transaction=tx, principal=None, request_id=None, trace_id=None)

            applied += 1
            self._record_batch_item(db, batch=batch, record=record, status=FuelProviderRecordStatus.APPLIED)

        batch.records_applied = applied
        batch.records_duplicate = duplicates
        batch.records_failed = failed
        batch.is_offline_batch = bool(offline_dates)
        if offline_dates:
            window_start = min(offline_dates).date().isoformat()
            window_end = max(offline_dates).date().isoformat()
            batch.offline_window = f"{window_start}/{window_end}"
            batch.offline_profile_snapshot = offline_snapshot

        if failed:
            batch.status = FuelProviderBatchStatus.FAILED
        else:
            batch.status = FuelProviderBatchStatus.APPLIED

        db.flush()
        return IngestResult(
            batch_id=str(batch.id),
            records_total=batch.records_total,
            records_applied=applied,
            records_duplicate=duplicates,
            records_failed=failed,
            status=batch.status.value,
            error=batch.error,
        )

    def authorize(self, db: Session, request: AuthorizeRequest) -> AuthorizeResult:
        card = _resolve_card_by_token(db, card_token=request.card_token, client_id=request.client_id)
        decision = "DECLINED"
        reason = "RULE_DECLINE"
        auth_code = None
        offline_profile_name = None
        offline_profile_id = None

        if card and card.status == FuelCardStatus.ACTIVE:
            decision = "APPROVED"
            reason = "OK"
            auth_code = _generate_auth_code(request.provider_tx_id)
            tx = _build_authorization_tx(db, card=card, request=request, auth_code=auth_code)
            db.add(tx)
            db.flush()
            breaches = apply_limit_checks(db, transaction=tx, principal=None, request_id=None, trace_id=None)
            if breaches:
                decision = "DECLINED"
                reason = "LIMIT_EXCEEDED"
                tx.status = FuelTransactionStatus.DECLINED
                tx.decline_code = reason
            if decision == "APPROVED" and request.offline_mode_allowed:
                profile = _resolve_offline_profile(db, card=card, client_id=card.client_id)
                if profile:
                    offline_profile_name = profile.name
                    offline_profile_id = str(profile.id)
        else:
            reason = "LEGAL_REQUIRED"

        decision_record = FuelProviderAuthorizationDecision(
            provider_code=self.code,
            provider_tx_id=request.provider_tx_id,
            client_id=request.client_id,
            card_id=str(card.id) if card else None,
            decision=decision,
            reason_code=reason,
            auth_code=auth_code,
            offline_profile_id=offline_profile_id,
            context=request.context,
        )
        db.add(decision_record)
        db.flush()

        return AuthorizeResult(
            decision=decision,
            reason_code=reason,
            auth_code=auth_code,
            offline_profile=offline_profile_name,
        )

    def settlement_export(self, db: Session, request: SettlementExportRequest) -> SettlementResult:
        period_start = datetime.strptime(request.period + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if period_start.month == 12:
            period_end = datetime(period_start.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(period_start.year, period_start.month + 1, 1, tzinfo=timezone.utc)

        query = (
            db.query(FuelTransaction)
            .filter(FuelTransaction.provider_code == self.code)
            .filter(FuelTransaction.occurred_at >= period_start)
            .filter(FuelTransaction.occurred_at < period_end)
        )
        if request.client_id:
            query = query.filter(FuelTransaction.client_id == request.client_id)
        rows = query.all()

        output_dir = Path("data/settlement_exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"provider_ref_settlement_{request.period}.csv"

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["client_id", "total_amount", "total_qty", "currency"])
            totals: dict[str, dict[str, Decimal]] = {}
            for tx in rows:
                totals.setdefault(tx.client_id, {"amount": Decimal("0"), "qty": Decimal("0"), "currency": tx.currency})
                totals[tx.client_id]["amount"] += Decimal(str(tx.amount or 0))
                totals[tx.client_id]["qty"] += Decimal(str(tx.volume_liters or 0))
            for client_id, total in totals.items():
                writer.writerow([client_id, str(total["amount"]), str(total["qty"]), total["currency"]])

            if request.include_details:
                writer.writerow([])
                writer.writerow(
                    [
                        "tx_id",
                        "provider_tx_id",
                        "client_id",
                        "card_id",
                        "occurred_at",
                        "amount",
                        "currency",
                        "qty",
                        "product_code",
                        "status",
                    ]
                )
                for tx in rows:
                    writer.writerow(
                        [
                            tx.id,
                            tx.provider_tx_id,
                            tx.client_id,
                            tx.card_id,
                            tx.occurred_at.isoformat(),
                            str(tx.amount),
                            tx.currency,
                            str(tx.volume_liters or "0"),
                            tx.category,
                            tx.status.value if tx.status else None,
                        ]
                    )

        return SettlementResult(
            payload_ref=str(output_path),
            format=request.format,
            records_total=len(rows),
        )

    def reconciliation_import(self, db: Session, payload_ref: str) -> ReconciliationResult:
        raise NotSupportedError("provider_ref does not support reconciliation import")

    @staticmethod
    def _parse_payload(payload_ref: bytes | str) -> Iterable[ProviderRefRecord]:
        if isinstance(payload_ref, bytes):
            text = payload_ref.decode("utf-8")
        else:
            payload_path = Path(payload_ref)
            text = payload_path.read_text(encoding="utf-8")

        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            occurred_at = _parse_datetime(row.get("occurred_at"))
            amount = _parse_decimal(row.get("amount"))
            quantity = _parse_decimal(row.get("qty"))
            yield ProviderRefRecord(
                provider_tx_id=str(row.get("tx_id") or "").strip(),
                occurred_at=occurred_at,
                card_token=_normalize_str(row.get("card_token") or row.get("card_pan_masked")),
                card_pan_masked=_normalize_str(row.get("card_pan_masked")),
                station_id=_normalize_str(row.get("station_id")),
                product_code=_normalize_str(row.get("product_code")),
                quantity=quantity,
                amount=amount,
                currency=_normalize_str(row.get("currency") or "RUB") or "RUB",
                auth_flag=_normalize_str(row.get("auth_flag")),
                status=_normalize_str(row.get("status")),
                rrn=_normalize_str(row.get("rrn") or row.get("auth_code")),
                client_ref=_normalize_str(row.get("client_ref")),
                raw_payload=row,
            )

    @staticmethod
    def _record_batch_item(
        db: Session,
        *,
        batch: FuelProviderBatch,
        record: ProviderRefRecord,
        status: FuelProviderRecordStatus,
        error: str | None = None,
    ) -> None:
        existing = (
            db.query(FuelProviderRecord)
            .filter(FuelProviderRecord.provider_code == batch.provider_code)
            .filter(FuelProviderRecord.provider_tx_id == record.provider_tx_id)
            .one_or_none()
        )
        if existing:
            return
        entry = FuelProviderRecord(
            batch_id=batch.id,
            provider_code=batch.provider_code,
            provider_tx_id=record.provider_tx_id,
            status=status,
            error=error,
            raw_payload=record.raw_payload,
        )
        db.add(entry)

    @staticmethod
    def _record_unmatched(db: Session, *, batch: FuelProviderBatch, record: ProviderRefRecord, reason: str) -> None:
        record_row = FuelUnmatchedRecord(
            provider_code=batch.provider_code,
            provider_tx_id=record.provider_tx_id,
            batch_id=batch.id,
            reason=reason,
            raw_payload=record.raw_payload,
        )
        db.add(record_row)


def _normalize_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = value.strip()
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _parse_decimal(value: str | None) -> Decimal:
    if not value:
        return Decimal("0")
    return Decimal(str(value))


def _content_hash(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return sha256(normalized.encode("utf-8")).hexdigest()


def _auth_type(flag: str | None) -> FuelTransactionAuthType:
    if not flag:
        return FuelTransactionAuthType.UNKNOWN
    if flag.upper() == "OFFLINE":
        return FuelTransactionAuthType.OFFLINE
    if flag.upper() == "ONLINE":
        return FuelTransactionAuthType.ONLINE
    return FuelTransactionAuthType.UNKNOWN


def _status(raw_status: str | None) -> FuelTransactionStatus:
    if not raw_status:
        return FuelTransactionStatus.SETTLED
    normalized = raw_status.upper()
    if normalized == "DECLINED":
        return FuelTransactionStatus.DECLINED
    if normalized == "REVERSED":
        return FuelTransactionStatus.REVERSED
    return FuelTransactionStatus.SETTLED


def _resolve_card(db: Session, *, record: ProviderRefRecord) -> FuelCard | None:
    query = db.query(FuelCard)
    if record.card_token:
        query = query.filter(FuelCard.card_token == record.card_token)
    if record.card_pan_masked:
        query = query.filter(FuelCard.masked_pan == record.card_pan_masked)
    if record.client_ref:
        query = query.filter(FuelCard.client_id == record.client_ref)
    return query.one_or_none()


def _resolve_card_by_token(db: Session, *, card_token: str | None, client_id: str | None) -> FuelCard | None:
    if not card_token:
        return None
    query = db.query(FuelCard).filter(FuelCard.card_token == card_token)
    if client_id:
        query = query.filter(FuelCard.client_id == client_id)
    return query.one_or_none()


def _offline_profile_snapshot(db: Session, *, card: FuelCard | None, client_id: str | None) -> dict | None:
    profile = _resolve_offline_profile(db, card=card, client_id=client_id)
    if not profile:
        return None
    return {
        "id": str(profile.id),
        "name": profile.name,
        "daily_amount_limit": str(profile.daily_amount_limit) if profile.daily_amount_limit is not None else None,
        "daily_txn_limit": profile.daily_txn_limit,
        "allowed_products": profile.allowed_products,
        "allowed_stations": profile.allowed_stations,
        "effective_from": profile.effective_from.isoformat() if profile.effective_from else None,
        "effective_to": profile.effective_to.isoformat() if profile.effective_to else None,
    }


def _resolve_offline_profile(
    db: Session,
    *,
    card: FuelCard | None,
    client_id: str | None,
) -> FleetOfflineProfile | None:
    if card and card.card_offline_profile_id:
        profile = db.query(FleetOfflineProfile).filter(FleetOfflineProfile.id == card.card_offline_profile_id).one_or_none()
        if profile:
            return profile
    if client_id:
        client = db.query(Client).filter(Client.id == client_id).one_or_none()
        if client and client.client_offline_profile_id:
            return (
                db.query(FleetOfflineProfile)
                .filter(FleetOfflineProfile.id == client.client_offline_profile_id)
                .one_or_none()
            )
        return (
            db.query(FleetOfflineProfile)
            .filter(FleetOfflineProfile.client_id == client_id)
            .filter(FleetOfflineProfile.status == FleetOfflineProfileStatus.ACTIVE)
            .order_by(FleetOfflineProfile.created_at.desc())
            .first()
        )
    return None


def _build_authorization_tx(
    db: Session,
    *,
    card: FuelCard,
    request: AuthorizeRequest,
    auth_code: str,
) -> FuelTransaction:
    network = fleet_ingestion_service._ensure_network(db, provider_code="provider_ref")
    station = fleet_ingestion_service._ensure_station(
        db,
        network_id=str(network.id),
        station_external_id=request.station_id,
        name=request.station_id,
    )
    amount = Decimal(request.amount)
    amount_minor = int((amount * Decimal("100")).quantize(Decimal("1")))
    volume_ml = 0
    tx = FuelTransaction(
        tenant_id=_resolve_tenant_id(None),
        client_id=card.client_id,
        card_id=str(card.id),
        vehicle_id=card.vehicle_id,
        driver_id=card.driver_id,
        station_id=station.id,
        network_id=network.id,
        occurred_at=request.timestamp,
        fuel_type=PRODUCT_FUEL_TYPE.get((request.product_code or "").upper(), FuelType.OTHER),
        volume_ml=volume_ml,
        unit_price_minor=0,
        amount_total_minor=amount_minor,
        currency=request.currency,
        status=FuelTransactionStatus.AUTHORIZED,
        auth_type=FuelTransactionAuthType.ONLINE,
        provider_code="provider_ref",
        provider_tx_id=request.provider_tx_id,
        provider_batch_key=None,
        merchant_key=request.station_id,
        external_ref=auth_code,
        amount=amount,
        volume_liters=None,
        category=request.product_code,
        merchant_name=None,
        station_external_id=request.station_id,
        location=None,
        raw_payload={
            "tx_id": request.provider_tx_id,
            "station_id": request.station_id,
            "product_code": request.product_code,
            "amount": str(amount),
            "currency": request.currency,
            "ts": request.timestamp.isoformat(),
        },
    )
    return tx


def _generate_auth_code(seed: str | None) -> str:
    digest = sha256((seed or "provider_ref").encode("utf-8")).hexdigest()
    return digest[:6].upper()
