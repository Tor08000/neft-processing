from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import base64
import csv
import io
import json
from typing import Iterable
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.integrations.fuel.base import ProviderStatement, ProviderTransaction
from app.integrations.fuel.models import (
    FuelIngestMode,
    FuelProviderAuthType,
    FuelProviderCardMap,
    FuelProviderConnection,
    FuelProviderConnectionStatus,
    FuelProviderRawEvent,
)
from app.integrations.fuel.normalize import (
    CanonicalStatement,
    CanonicalTransaction,
    canonical_to_ingest_item,
    payload_hash,
    redact_payload,
)
from app.integrations.fuel.registry import get_connector, load_default_providers
from app.models.fuel import FuelCard, FuelIngestJob
from app.models.reconciliation import ExternalStatement
from app.schemas.fleet_ingestion import FleetIngestItemIn, FleetIngestRequestIn
from app.services import fleet_ingestion_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_card_alias(
    db: Session,
    *,
    provider_code: str,
    provider_card_id: str | None,
    fallback_alias: str | None,
) -> str | None:
    if fallback_alias:
        return fallback_alias
    if not provider_card_id:
        return None
    mapping = (
        db.query(FuelProviderCardMap)
        .filter(FuelProviderCardMap.provider_code == provider_code)
        .filter(FuelProviderCardMap.provider_card_id == provider_card_id)
        .one_or_none()
    )
    if not mapping:
        return None
    card = db.query(FuelCard).filter(FuelCard.id == mapping.card_id).one_or_none()
    return card.card_alias if card else None


def _store_raw_event(
    db: Session,
    *,
    connection: FuelProviderConnection,
    event_type: str,
    provider_event_id: str | None,
    occurred_at: datetime | None,
    payload: dict | None,
    ingest_job_id: str | None,
) -> FuelProviderRawEvent:
    if provider_event_id:
        existing = (
            db.query(FuelProviderRawEvent)
            .filter(FuelProviderRawEvent.provider_code == connection.provider_code)
            .filter(FuelProviderRawEvent.provider_event_id == provider_event_id)
            .one_or_none()
        )
        if existing:
            return existing
    redacted = redact_payload(payload)
    record = FuelProviderRawEvent(
        client_id=connection.client_id,
        provider_code=connection.provider_code,
        event_type=event_type,
        provider_event_id=provider_event_id,
        occurred_at=occurred_at,
        payload_redacted=redacted,
        payload_hash=payload_hash(redacted),
        ingest_job_id=ingest_job_id,
    )
    db.add(record)
    if provider_event_id:
        db.flush()
    return record


def _to_canonical(connector, item: ProviderTransaction) -> CanonicalTransaction:
    mapped = connector.map_transaction(item)
    return CanonicalTransaction(**mapped)


def _to_canonical_statement(connector, item: ProviderStatement) -> CanonicalStatement:
    mapped = connector.map_statement(item)
    return CanonicalStatement(**mapped)


def poll_provider(
    db: Session,
    *,
    connection: FuelProviderConnection,
    since: datetime,
    until: datetime,
    request_id: str | None = None,
    trace_id: str | None = None,
    include_statements: bool = False,
) -> FuelIngestJob | None:
    load_default_providers()
    connector = get_connector(connection.provider_code)
    page = connector.fetch_transactions(connection, since=since, until=until, cursor=connection.last_sync_cursor)
    if not page.items:
        connection.last_sync_at = until
        connection.last_sync_cursor = page.next_cursor or connection.last_sync_cursor
        return None

    canonical_items: list[CanonicalTransaction] = []
    for item in page.items:
        canonical = _to_canonical(connector, item)
        card_alias = _resolve_card_alias(
            db,
            provider_code=canonical.provider_code,
            provider_card_id=canonical.provider_card_id,
            fallback_alias=canonical.card_alias,
        )
        canonical_items.append(
            CanonicalTransaction(
                provider_code=canonical.provider_code,
                provider_tx_id=canonical.provider_tx_id,
                provider_card_id=canonical.provider_card_id,
                card_alias=card_alias,
                occurred_at=canonical.occurred_at,
                amount=canonical.amount,
                currency=canonical.currency,
                volume_liters=canonical.volume_liters,
                category=canonical.category,
                merchant_name=canonical.merchant_name,
                station_id=canonical.station_id,
                location=canonical.location,
                raw_payload=canonical.raw_payload,
            )
        )

    ingest_items = [
        canonical_to_ingest_item(item, client_ref=connection.client_id)
        for item in canonical_items
        if item.card_alias
    ]
    job = None
    if ingest_items:
        ingest_payload = FleetIngestRequestIn(
            provider_code=connection.provider_code,
            batch_ref=f"poll:{since.isoformat()}:{until.isoformat()}",
            idempotency_key=new_uuid_str(),
            items=ingest_items,
        )
        job = fleet_ingestion_service.ingest_transactions(
            db,
            payload=ingest_payload,
            principal=None,
            request_id=request_id,
            trace_id=trace_id,
        )
        job.mode = FuelIngestMode.POLL
        job.window_start = since
        job.window_end = until
        job.cursor = page.next_cursor

    for item in canonical_items:
        _store_raw_event(
            db,
            connection=connection,
            event_type="tx",
            provider_event_id=item.provider_tx_id,
            occurred_at=item.occurred_at,
            payload=item.raw_payload,
            ingest_job_id=str(job.id) if job else None,
        )

    connection.last_sync_at = until
    connection.last_sync_cursor = page.next_cursor or connection.last_sync_cursor

    if include_statements:
        statement = connector.fetch_statements(connection, period_start=since, period_end=until)
        store_statement(db, connection=connection, statement=statement, ingest_job_id=str(job.id) if job else None)

    return job


def backfill_provider(
    db: Session,
    *,
    connection: FuelProviderConnection,
    period_start: datetime,
    period_end: datetime,
    batch_hours: int = 24,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> list[FuelIngestJob]:
    jobs: list[FuelIngestJob] = []
    window_start = period_start
    while window_start < period_end:
        window_end = min(window_start + timedelta(hours=batch_hours), period_end)
        job = poll_provider(
            db,
            connection=connection,
            since=window_start,
            until=window_end,
            request_id=request_id,
            trace_id=trace_id,
        )
        if job:
            job.mode = FuelIngestMode.BACKFILL
            job.window_start = window_start
            job.window_end = window_end
            jobs.append(job)
        window_start = window_end
    return jobs


def store_statement(
    db: Session,
    *,
    connection: FuelProviderConnection,
    statement: ProviderStatement,
    ingest_job_id: str | None,
) -> ExternalStatement:
    load_default_providers()
    connector = get_connector(connection.provider_code)
    canonical = _to_canonical_statement(connector, statement)
    source_hash = payload_hash(
        {
            "provider": canonical.provider_code,
            "period_start": canonical.period_start.isoformat(),
            "period_end": canonical.period_end.isoformat(),
            "currency": canonical.currency,
            "total_in": str(canonical.total_in) if canonical.total_in is not None else None,
            "total_out": str(canonical.total_out) if canonical.total_out is not None else None,
            "closing_balance": str(canonical.closing_balance) if canonical.closing_balance is not None else None,
            "lines": canonical.lines,
        }
    )
    existing = (
        db.query(ExternalStatement)
        .filter(ExternalStatement.provider == canonical.provider_code)
        .filter(ExternalStatement.source_hash == source_hash)
        .one_or_none()
    )
    if existing:
        return existing
    record = ExternalStatement(
        provider=canonical.provider_code,
        period_start=canonical.period_start,
        period_end=canonical.period_end,
        currency=canonical.currency,
        total_in=canonical.total_in,
        total_out=canonical.total_out,
        closing_balance=canonical.closing_balance,
        lines=canonical.lines,
        source_hash=source_hash,
    )
    db.add(record)
    _store_raw_event(
        db,
        connection=connection,
        event_type="statement",
        provider_event_id=canonical.provider_statement_id,
        occurred_at=canonical.period_end,
        payload=canonical.raw_payload,
        ingest_job_id=ingest_job_id,
    )
    return record


def replay_raw_event(
    db: Session,
    *,
    raw_event: FuelProviderRawEvent,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> FuelIngestJob | None:
    load_default_providers()
    connector = get_connector(raw_event.provider_code)
    canonical_payload = connector.map_raw_event(raw_event.payload_redacted or {})
    canonical = CanonicalTransaction(**canonical_payload)
    ingest_payload = FleetIngestRequestIn(
        provider_code=raw_event.provider_code,
        batch_ref=f"replay:{raw_event.id}",
        idempotency_key=new_uuid_str(),
        items=[canonical_to_ingest_item(canonical, client_ref=raw_event.client_id)],
    )
    job = fleet_ingestion_service.ingest_transactions(
        db,
        payload=ingest_payload,
        principal=None,
        request_id=request_id,
        trace_id=trace_id,
    )
    job.mode = FuelIngestMode.REPLAY
    job.window_start = raw_event.occurred_at or _now()
    job.window_end = raw_event.occurred_at or _now()
    raw_event.ingest_job_id = job.id
    return job


def list_raw_events(
    db: Session,
    *,
    client_id: str | None,
    provider_code: str | None,
    start: datetime | None,
    end: datetime | None,
) -> Iterable[FuelProviderRawEvent]:
    query = db.query(FuelProviderRawEvent)
    if client_id:
        query = query.filter(FuelProviderRawEvent.client_id == client_id)
    if provider_code:
        query = query.filter(FuelProviderRawEvent.provider_code == provider_code)
    if start:
        query = query.filter(FuelProviderRawEvent.created_at >= start)
    if end:
        query = query.filter(FuelProviderRawEvent.created_at <= end)
    return query.order_by(FuelProviderRawEvent.created_at.desc()).all()


def list_ingest_jobs(
    db: Session,
    *,
    provider_code: str | None = None,
) -> Iterable[FuelIngestJob]:
    query = db.query(FuelIngestJob)
    if provider_code:
        query = query.filter(FuelIngestJob.provider_code == provider_code)
    return query.order_by(FuelIngestJob.received_at.desc()).all()


def ingest_edi_payload(
    db: Session,
    *,
    provider_code: str,
    client_ref: str,
    file_type: str,
    payload_base64: str | None,
    payload_url: str | None,
    idempotency_key: str,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> FuelIngestJob:
    raw_payload = _load_payload(payload_base64=payload_base64, payload_url=payload_url)
    items = _parse_edi_payload(file_type=file_type, raw_payload=raw_payload, client_ref=client_ref)
    if not items:
        raise ValueError("empty_payload")
    ingest_payload = FleetIngestRequestIn(
        provider_code=provider_code,
        batch_ref=f"edi:{file_type}",
        idempotency_key=idempotency_key,
        items=items,
    )
    job = fleet_ingestion_service.ingest_transactions(
        db,
        payload=ingest_payload,
        principal=None,
        request_id=request_id,
        trace_id=trace_id,
    )
    job.mode = FuelIngestMode.EDI
    for item in items:
        _store_raw_event(
            db,
            connection=FuelProviderConnection(
                client_id=client_ref,
                provider_code=provider_code,
                status=FuelProviderConnectionStatus.ACTIVE,
                auth_type=FuelProviderAuthType.EDI,
            ),
            event_type="edi",
            provider_event_id=item.provider_tx_id,
            occurred_at=item.occurred_at,
            payload=item.raw_payload,
            ingest_job_id=str(job.id),
        )
    return job


def _load_payload(*, payload_base64: str | None, payload_url: str | None) -> str:
    if payload_base64:
        return base64.b64decode(payload_base64).decode("utf-8")
    if payload_url:
        import requests

        response = requests.get(payload_url, timeout=30)
        response.raise_for_status()
        return response.text
    raise ValueError("payload_required")


def _parse_edi_payload(*, file_type: str, raw_payload: str, client_ref: str) -> list[FleetIngestItemIn]:
    normalized_type = file_type.strip().lower()
    if normalized_type == "jsonl":
        return [_parse_edi_row(json.loads(line), client_ref=client_ref) for line in raw_payload.splitlines() if line.strip()]
    if normalized_type == "csv":
        reader = csv.DictReader(io.StringIO(raw_payload))
        return [_parse_edi_row(row, client_ref=client_ref) for row in reader]
    if normalized_type == "xml":
        root = ElementTree.fromstring(raw_payload)
        rows = []
        for item in root.findall(".//transaction"):
            row = {child.tag: child.text for child in item}
            rows.append(_parse_edi_row(row, client_ref=client_ref))
        return rows
    raise ValueError("unsupported_file_type")


def _parse_edi_row(row: dict, *, client_ref: str) -> FleetIngestItemIn:
    occurred_at = datetime.fromisoformat(row.get("occurred_at")) if row.get("occurred_at") else _now()
    return canonical_to_ingest_item(
        CanonicalTransaction(
            provider_code=str(row.get("provider_code") or "edi"),
            provider_tx_id=row.get("provider_tx_id"),
            provider_card_id=row.get("provider_card_id"),
            card_alias=row.get("card_alias"),
            occurred_at=occurred_at,
            amount=Decimal(str(row.get("amount", "0"))),
            currency=row.get("currency") or "RUB",
            volume_liters=Decimal(str(row.get("volume_liters"))) if row.get("volume_liters") else None,
            category=row.get("category"),
            merchant_name=row.get("merchant_name"),
            station_id=row.get("station_id"),
            location=row.get("location"),
            raw_payload=row,
        ),
        client_ref=client_ref,
    )
