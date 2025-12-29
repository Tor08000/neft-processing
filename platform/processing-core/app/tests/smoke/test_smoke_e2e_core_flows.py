from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.db import SessionLocal
from app.models.billing_period import BillingPeriod
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdScope, RiskThresholdAction
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.billing_run import BillingRunService
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import settle_fuel_tx
from app.services.money_flow.cfo_explain import build_cfo_explain
from app.services.money_flow.replay import MoneyReplayMode, MoneyReplayScope, run_money_flow_replay
from app.models.billing_period import BillingPeriodType


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_threshold_set(
    db,
    *,
    subject_type: RiskSubjectType,
    threshold_set_id: str,
    action: RiskThresholdAction,
) -> None:
    existing = db.get(RiskThresholdSet, threshold_set_id)
    if existing:
        return
    threshold_set = RiskThresholdSet(
        id=threshold_set_id,
        subject_type=subject_type,
        scope=RiskThresholdScope.GLOBAL,
        action=action,
        block_threshold=90,
        review_threshold=70,
        allow_threshold=0,
    )
    db.add(threshold_set)
    db.commit()


def _seed_fuel_refs(db, *, client_id: str, tenant_id: int):
    network = FuelNetwork(id=str(uuid4()), name="SmokeNet", provider_code="SMOKE", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        name="Smoke Station",
        country="RU",
        region="SPB",
        city="SPB",
        station_code="ST-1",
        status=FuelStationStatus.ACTIVE,
    )
    vehicle = FleetVehicle(
        id=str(uuid4()),
        tenant_id=tenant_id,
        client_id=client_id,
        plate_number="SMOKE-1",
        tank_capacity_liters=60,
        status=FleetVehicleStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=tenant_id,
        client_id=client_id,
        card_token="smoke-card-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
    )
    db.add_all([network, station, vehicle, card])
    db.commit()
    return network, station, vehicle, card


@pytest.mark.smoke
def test_fuel_authorize_settle_links(session):
    tenant_id = 1
    client_id = "smoke-client-fuel"
    _ensure_threshold_set(
        session,
        subject_type=RiskSubjectType.FUEL_TRANSACTION,
        threshold_set_id="smoke-fuel-thresholds",
        action=RiskThresholdAction.PAYMENT,
    )
    network, station, vehicle, card = _seed_fuel_refs(session, client_id=client_id, tenant_id=tenant_id)

    occurred_at = datetime(2025, 1, 5, tzinfo=timezone.utc)
    payload = FuelAuthorizeRequest(
        card_token=card.card_token,
        network_code=network.provider_code,
        station_code=station.station_code or "ST-1",
        occurred_at=occurred_at,
        fuel_type="DIESEL",
        volume_liters=10.0,
        unit_price=500,
        currency="RUB",
        external_ref="smoke-fuel-ref",
        vehicle_plate=vehicle.plate_number,
    )

    result = None
    settled = None
    try:
        result = authorize_fuel_tx(session, payload=payload)
        assert result.response.status == "ALLOW"
        tx_id = result.response.transaction_id
        assert tx_id

        settled = settle_fuel_tx(session, transaction_id=tx_id)
        assert settled.ledger_transaction_id

        entries = (
            session.query(InternalLedgerEntry)
            .filter(InternalLedgerEntry.ledger_transaction_id == settled.ledger_transaction_id)
            .all()
        )
        assert len(entries) == 2
        debit_total = sum(
            entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT
        )
        credit_total = sum(
            entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT
        )
        assert debit_total == credit_total

        links = (
            session.query(MoneyFlowLink)
            .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
            .filter(MoneyFlowLink.src_id == tx_id)
            .all()
        )
        assert any(link.link_type == MoneyFlowLinkType.POSTS for link in links)
        assert any(link.link_type == MoneyFlowLinkType.RELATES for link in links)
    finally:
        if result and result.response.transaction_id:
            session.query(MoneyFlowLink).filter(
                MoneyFlowLink.src_id == result.response.transaction_id
            ).delete(synchronize_session=False)
        session.query(InternalLedgerEntry).filter(
            InternalLedgerEntry.ledger_transaction_id == getattr(settled, "ledger_transaction_id", None)
        ).delete(synchronize_session=False)
        session.query(InternalLedgerTransaction).filter(
            InternalLedgerTransaction.id == getattr(settled, "ledger_transaction_id", None)
        ).delete(synchronize_session=False)
        session.query(FuelCard).filter(FuelCard.id == card.id).delete(synchronize_session=False)
        session.query(FleetVehicle).filter(FleetVehicle.id == vehicle.id).delete(synchronize_session=False)
        session.query(FuelStation).filter(FuelStation.id == station.id).delete(synchronize_session=False)
        session.query(FuelNetwork).filter(FuelNetwork.id == network.id).delete(synchronize_session=False)
        session.commit()


@pytest.mark.smoke
def test_billing_invoice_replay_cfo_explain(session):
    client_id = "smoke-client-billing"
    tenant_id = 1
    _ensure_threshold_set(
        session,
        subject_type=RiskSubjectType.INVOICE,
        threshold_set_id="smoke-invoice-thresholds",
        action=RiskThresholdAction.INVOICE,
    )

    start_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    operations = [
        Operation(
            ext_operation_id=str(uuid4()),
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED,
            created_at=start_at + timedelta(hours=1),
            updated_at=start_at + timedelta(hours=1),
            merchant_id="merchant-1",
            terminal_id="terminal-1",
            client_id=client_id,
            card_id="card-1",
            product_id="FUEL",
            product_type=ProductType.AI92,
            amount=2_000,
            amount_settled=2_000,
            currency="RUB",
            quantity=1,
            unit_price=2_000,
            captured_amount=2_000,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        ),
        Operation(
            ext_operation_id=str(uuid4()),
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED,
            created_at=start_at + timedelta(hours=2),
            updated_at=start_at + timedelta(hours=2),
            merchant_id="merchant-1",
            terminal_id="terminal-1",
            client_id=client_id,
            card_id="card-1",
            product_id="FUEL",
            product_type=ProductType.AI92,
            amount=3_000,
            amount_settled=3_000,
            currency="RUB",
            quantity=1,
            unit_price=3_000,
            captured_amount=3_000,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        ),
    ]

    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": tenant_id, "sub": "smoke-admin"}
    session.add_all(operations)
    session.commit()

    invoice = None
    billing_period = None
    try:
        service = BillingRunService(session)
        result = service.run(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            client_id=None,
            idempotency_key="smoke-billing-period",
            token=token,
        )
        billing_period = result.billing_period
        invoice = (
            session.query(Invoice)
            .filter(Invoice.billing_period_id == billing_period.id)
            .filter(Invoice.client_id == client_id)
            .one()
        )
        assert invoice.total_with_tax == 5_000

        snapshot = {
            "invoice": {
                "total_with_tax": int(invoice.total_with_tax or 0),
                "amount_paid": int(invoice.amount_paid or 0),
                "amount_due": int(invoice.amount_due or 0),
            },
            "links": {"invoice_id": invoice.id},
            "snapshots": {"status": "ok"},
        }
        replay = run_money_flow_replay(
            session,
            client_id=client_id,
            billing_period_id=str(billing_period.id),
            mode=MoneyReplayMode.COMPARE,
            scope=MoneyReplayScope.ALL,
            expected_snapshot=snapshot,
            actual_snapshot=snapshot,
        )
        assert replay.diff is not None
        assert replay.diff.mismatched_totals == []
        assert replay.diff.missing_links == []
        assert replay.diff.recommended_action == "NONE"

        explain = build_cfo_explain(session, invoice_id=invoice.id)
        assert explain.invoice_id == invoice.id
        assert explain.totals.total_with_tax == invoice.total_with_tax
        assert explain.breakdown is not None
        assert explain.snapshots is not None
    finally:
        if invoice:
            session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).delete(synchronize_session=False)
            session.query(Invoice).filter(Invoice.id == invoice.id).delete(synchronize_session=False)
        if billing_period:
            session.query(BillingPeriod).filter(BillingPeriod.id == billing_period.id).delete(synchronize_session=False)
        session.query(Operation).filter(Operation.client_id == client_id).delete(synchronize_session=False)
        session.commit()
