from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import schemathesis
from fastapi.testclient import TestClient

from app.db import get_db as app_get_db
from app.deps.db import get_db as deps_get_db
from app.main import app
from app.models.crm import CRMBillingCycle, CRMBillingPeriod, CRMSubscriptionStatus, CRMTariffStatus
from app.models.fuel import FuelTransactionStatus, FuelType
from app.models.logistics import LogisticsETAMethod, LogisticsNavigatorExplainType
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationStatus, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.schemas.admin.unified_explain import UnifiedExplainIds, UnifiedExplainResponse, UnifiedExplainResult, UnifiedExplainSubject
from app.schemas.fuel import FuelAuthorizeResponse, FuelTransactionOut
from app.services.explain.actions.base import ActionItem
from app.services.explain.escalation.base import EscalationInfo
from app.services.explain.sla.base import SLAClock
from app.services.fuel.authorize import AuthorizationResult
from app.services.money_flow.replay import MoneyReplayMode, MoneyReplayResult, MoneyReplayScope

pytestmark = [pytest.mark.contracts, pytest.mark.contracts_api]

SCHEMA = schemathesis.from_dict(app.openapi())
CLIENT = TestClient(app)
NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


class DummyDB:
    class _Query:
        def __init__(self, result=None):
            self._result = result

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def one_or_none(self):
            return self._result

        def first(self):
            return self._result

    def get(self, *_args, **_kwargs):
        model = _args[0] if _args else None
        identifier = _args[1] if len(_args) > 1 else None
        if getattr(model, "__name__", "") == "SubscriptionPlan":
            return SimpleNamespace(id=str(identifier or "plan-contract"), code="PRO")
        return None

    def query(self, model):
        if getattr(model, "__name__", "") == "SubscriptionPlan":
            return self._Query(SimpleNamespace(id="plan-contract"))
        return self._Query()

    def add(self, _obj):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


@pytest.fixture(autouse=True)
def _override_db():
    dummy = DummyDB()

    def _get_db():
        yield dummy

    app.dependency_overrides[app_get_db] = _get_db
    app.dependency_overrides[deps_get_db] = _get_db
    yield
    app.dependency_overrides.pop(app_get_db, None)
    app.dependency_overrides.pop(deps_get_db, None)


def _call_case(path: str, method: str, *, body=None, query=None, path_parameters=None, headers=None):
    operation = SCHEMA[path][method.lower()]
    case = operation.make_case(body=body, query=query, path_parameters=path_parameters)
    response = case.call(session=CLIENT, headers=headers)
    case.validate_response(response)
    return response


def _fuel_transaction() -> FuelTransactionOut:
    return FuelTransactionOut(
        id="fuel-1",
        tenant_id=1,
        client_id="client-1",
        card_id="card-1",
        vehicle_id=None,
        driver_id=None,
        station_id="station-1",
        network_id="network-1",
        occurred_at=NOW,
        fuel_type=FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=100,
        amount_total_minor=1000,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
        decline_code=None,
        risk_decision_id=None,
        ledger_transaction_id=None,
        external_ref="ext-1",
    )


def _unified_explain_response() -> UnifiedExplainResponse:
    return UnifiedExplainResponse(
        primary_reason=PrimaryReason.LIMIT,
        secondary_reasons=[PrimaryReason.RISK],
        subject=UnifiedExplainSubject(type="fuel_tx", id="fuel-1", ts=NOW.isoformat()),
        result=UnifiedExplainResult(
            status="DECLINED",
            primary_reason=PrimaryReason.LIMIT,
            secondary_reasons=[PrimaryReason.RISK],
        ),
        sections={"summary": {"notes": []}},
        ids=UnifiedExplainIds(
            risk_decision_id="risk-1",
            ledger_transaction_id=None,
            invoice_id=None,
            document_ids=[],
            money_flow_event_ids=[],
            snapshot_id=None,
            snapshot_hash=None,
        ),
        recommendations=["review"],
        actions=[
            ActionItem(
                code="REVIEW_LIMIT",
                title="Review limit",
                description="Review the applied limit",
                target="CRM",
                severity="REQUIRED",
            )
        ],
        sla=SLAClock(
            started_at=NOW.isoformat().replace("+00:00", "Z"),
            expires_at=NOW.isoformat().replace("+00:00", "Z"),
            remaining_minutes=120,
        ),
        escalation=EscalationInfo(target="CRM", status="PENDING"),
        assistant=None,
    )


def test_fuel_authorize_contract(monkeypatch, admin_auth_headers):
    def _authorize(*_args, **_kwargs):
        return AuthorizationResult(response=FuelAuthorizeResponse(status="ALLOW", transaction_id="fuel-1"))

    monkeypatch.setattr("app.api.v1.endpoints.fuel_transactions.authorize_fuel_tx", _authorize)

    payload = {
        "card_token": "card-1",
        "network_code": "network-1",
        "station_code": "station-1",
        "occurred_at": NOW.isoformat().replace("+00:00", "Z"),
        "fuel_type": FuelType.DIESEL.value,
        "volume_liters": 10.0,
        "unit_price": 100,
        "currency": "RUB",
    }

    _call_case(
        "/api/v1/fuel/transactions/authorize",
        "post",
        body=payload,
        headers=admin_auth_headers,
    )


def test_fuel_settle_contract(monkeypatch, admin_auth_headers):
    def _settle(*_args, **_kwargs):
        return SimpleNamespace(transaction_id="fuel-1")

    monkeypatch.setattr("app.api.v1.endpoints.fuel_transactions.settle_fuel_tx", _settle)
    monkeypatch.setattr("app.api.v1.endpoints.fuel_transactions.get_fuel_transaction", lambda *_args, **_kwargs: _fuel_transaction())

    _call_case(
        "/api/v1/fuel/transactions/{transaction_id}/settle",
        "post",
        path_parameters={"transaction_id": "fuel-1"},
        headers=admin_auth_headers,
    )


def test_unified_explain_contract(monkeypatch, admin_auth_headers):
    def _build_unified_explain(*_args, **_kwargs):
        return _unified_explain_response()

    monkeypatch.setattr("app.routers.admin.explain.build_unified_explain", _build_unified_explain)

    _call_case(
        "/api/core/v1/admin/explain",
        "get",
        query={"fuel_tx_id": "fuel-1"},
        headers=admin_auth_headers,
    )


def test_money_flow_contracts(monkeypatch, admin_auth_headers):
    def _money_explain(*_args, **_kwargs):
        return SimpleNamespace(
            flow_type="FUEL",
            flow_ref_id="fuel-1",
            state="AUTHORIZED",
            ledger={
                "ledger_transaction_id": "ledger-1",
                "balanced": True,
                "entries": [
                    {"account": "cash", "direction": "DEBIT", "amount": 1000, "currency": "RUB"}
                ],
            },
            invariants={"ok": True},
            risk=None,
            notes=["ok"],
            event_id="event-1",
            created_at=NOW,
        )

    def _money_health(*_args, **_kwargs):
        return SimpleNamespace(
            orphan_ledger_transactions=0,
            missing_ledger_postings=0,
            invariant_violations=0,
            stuck_authorized=0,
            stuck_pending_settlement=0,
            cross_period_anomalies=0,
            missing_money_flow_links=0,
            invoices_missing_subscription_links=0,
            charges_missing_invoice_links=0,
            charge_key_duplicates=0,
            segment_gaps_or_overlaps=0,
            missing_snapshots=0,
            missing_subscription_snapshots=0,
            disconnected_graph=0,
            cfo_explain_not_ready=0,
            fuel_missing_ledger_links=0,
            fuel_missing_billing_period_links=0,
            fuel_missing_invoice_links=0,
            top_offenders=[],
        )

    def _cfo_explain(*_args, **_kwargs):
        return SimpleNamespace(
            invoice_id="invoice-1",
            client_id="client-1",
            currency="RUB",
            totals={"total_with_tax": 1000, "amount_paid": 0, "amount_due": 1000},
            breakdown={"base_fee": 1000, "overage": 0, "fuel_usage": 0, "logistics_usage": 0},
            links={"charges": [], "usage": [], "ledger_postings": [], "payments": []},
            snapshots={"before_count": 0, "after_count": 0, "failed_count": 0, "passed": True},
            anomalies=[],
            fuel=None,
        )

    def _replay(*_args, **_kwargs):
        return MoneyReplayResult(
            mode=MoneyReplayMode.DRY_RUN,
            scope=MoneyReplayScope.FUEL,
            recompute_hash="hash-1",
            diff=None,
            links_rebuilt=None,
            summary={"fuel_total": 1000},
        )

    monkeypatch.setattr("app.routers.admin.money_flow.build_money_explain", _money_explain)
    monkeypatch.setattr("app.routers.admin.money_flow.build_money_health", _money_health)
    monkeypatch.setattr("app.routers.admin.money_flow.build_cfo_explain", _cfo_explain)
    monkeypatch.setattr("app.routers.admin.money_flow.run_money_flow_replay", _replay)

    _call_case(
        "/api/core/v1/admin/money/health",
        "get",
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/money/replay",
        "post",
        body={
            "client_id": "client-1",
            "billing_period_id": "period-1",
            "mode": MoneyReplayMode.DRY_RUN.value,
            "scope": MoneyReplayScope.FUEL.value,
        },
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/money/cfo-explain",
        "get",
        query={"invoice_id": "invoice-1"},
        headers=admin_auth_headers,
    )


def test_crm_control_plane_contracts(monkeypatch, admin_auth_headers):
    now = NOW

    def _create_tariff(*_args, **_kwargs):
        return _tariff_stub()

    def _get_tariff(*_args, **_kwargs):
        return _tariff_stub()

    def _update_tariff(*_args, **_kwargs):
        return _tariff_stub()

    def _create_subscription(*_args, **_kwargs):
        return _subscription_stub()

    def _tariff_stub():
        return SimpleNamespace(
            id="tariff-1",
            name="Standard",
            description=None,
            status=CRMTariffStatus.ACTIVE,
            billing_period=CRMBillingPeriod.MONTHLY,
            base_fee_minor=1000,
            currency="RUB",
            features=None,
            limits_defaults=None,
            created_at=now,
            definition=None,
        )

    def _subscription_stub():
        return SimpleNamespace(
            id="sub-1",
            tenant_id=1,
            client_id="client-1",
            tariff_plan_id="tariff-1",
            status=CRMSubscriptionStatus.ACTIVE,
            billing_cycle=CRMBillingCycle.MONTHLY,
            billing_day=1,
            started_at=now,
            paused_at=None,
            ended_at=None,
            meta=None,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr("app.routers.admin.crm.tariffs.create_tariff", _create_tariff)
    monkeypatch.setattr("app.routers.admin.crm.repository.get_tariff", _get_tariff)
    monkeypatch.setattr("app.routers.admin.crm.tariffs.update_tariff", _update_tariff)
    monkeypatch.setattr("app.routers.admin.crm.subscriptions.create_subscription", _create_subscription)
    monkeypatch.setattr("app.routers.admin.crm.events.audit_event", lambda *_args, **_kwargs: None)

    headers = {**admin_auth_headers, "X-CRM-Version": "1"}

    _call_case(
        "/api/core/v1/admin/crm/tariffs",
        "post",
        body={
            "name": "Standard",
            "description": "",
            "status": CRMTariffStatus.ACTIVE.value,
            "billing_period": CRMBillingPeriod.MONTHLY.value,
            "base_fee_minor": 1000,
            "currency": "RUB",
        },
        headers=headers,
    )

    _call_case(
        "/api/core/v1/admin/crm/tariffs/{tariff_id}",
        "patch",
        path_parameters={"tariff_id": "tariff-1"},
        body={"name": "Standard", "status": CRMTariffStatus.ACTIVE.value},
        headers=headers,
    )

    _call_case(
        "/api/core/v1/admin/crm/clients/{client_id}/subscriptions",
        "post",
        path_parameters={"client_id": "client-1"},
        body={
            "tenant_id": 1,
            "tariff_plan_id": "tariff-1",
            "status": CRMSubscriptionStatus.ACTIVE.value,
            "billing_cycle": CRMBillingCycle.MONTHLY.value,
            "billing_day": 1,
            "started_at": now.isoformat().replace("+00:00", "Z"),
        },
        headers=headers,
    )


def test_logistics_contracts(monkeypatch, admin_auth_headers):
    def _compute_eta_snapshot(*_args, **_kwargs):
        return SimpleNamespace(
            id="eta-1",
            order_id="order-1",
            computed_at=NOW,
            eta_end_at=NOW,
            eta_confidence=90,
            method=LogisticsETAMethod.HISTORICAL,
            inputs={"source": "contract"},
            created_at=NOW,
        )

    def _get_route(*_args, **_kwargs):
        return SimpleNamespace(id="route-1")

    def _get_latest_route_snapshot(*_args, **_kwargs):
        return SimpleNamespace(
            id="snapshot-1",
            order_id="order-1",
            route_id="route-1",
            provider="test",
            geometry=[{"lat": 0.0, "lon": 0.0}],
            distance_km=10.5,
            eta_minutes=15,
            created_at=NOW,
        )

    def _list_navigator_explains(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id="explain-1",
                route_snapshot_id="snapshot-1",
                type=LogisticsNavigatorExplainType.ETA,
                payload={"note": "ok"},
                created_at=NOW,
            )
        ]

    def _get_order(*_args, **_kwargs):
        return SimpleNamespace(
            id="order-1",
            tenant_id=1,
            client_id="client-1",
            order_type="TRIP",
            status="PLANNED",
            vehicle_id="vehicle-1",
            driver_id="driver-1",
            planned_start_at=NOW,
            planned_end_at=NOW,
            actual_start_at=None,
            actual_end_at=None,
            origin_text="Origin",
            destination_text="Destination",
            meta={},
            created_at=NOW,
            updated_at=NOW,
        )

    def _list_routes_for_order(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id="route-1",
                order_id="order-1",
                version=1,
                status="ACTIVE",
                distance_km=10.5,
                planned_duration_minutes=15,
                created_at=NOW,
            )
        ]

    def _get_active_route(*_args, **_kwargs):
        return _list_routes_for_order()[0]

    def _get_route_stops(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id="stop-1",
                route_id="route-1",
                sequence=0,
                stop_type="START",
                name="Start",
                address_text=None,
                lat=0.0,
                lon=0.0,
                planned_arrival_at=None,
                planned_departure_at=None,
                actual_arrival_at=None,
                actual_departure_at=None,
                status="PENDING",
                fuel_tx_id=None,
                meta=None,
            )
        ]

    def _get_last_tracking_event(*_args, **_kwargs):
        return SimpleNamespace(
            id="tracking-1",
            order_id="order-1",
            vehicle_id="vehicle-1",
            driver_id="driver-1",
            event_type="LOCATION",
            ts=NOW,
            lat=0.0,
            lon=0.0,
            speed_kmh=40.0,
            heading_deg=None,
            odometer_km=None,
            stop_id=None,
            status_from=None,
            status_to=None,
            meta=None,
        )

    def _count_tracking_events(*_args, **_kwargs):
        return 1

    monkeypatch.setattr(
        "app.routers.admin.logistics.eta.compute_eta_snapshot",
        _compute_eta_snapshot,
    )

    monkeypatch.setattr("app.routers.admin.logistics.repository.get_order", _get_order)
    monkeypatch.setattr("app.routers.admin.logistics.repository.get_active_route", _get_active_route)
    monkeypatch.setattr("app.routers.admin.logistics.repository.list_routes_for_order", _list_routes_for_order)
    monkeypatch.setattr("app.routers.admin.logistics.repository.get_route_stops", _get_route_stops)
    monkeypatch.setattr("app.routers.admin.logistics.repository.get_last_tracking_event", _get_last_tracking_event)
    monkeypatch.setattr("app.routers.admin.logistics.repository.count_tracking_events", _count_tracking_events)
    monkeypatch.setattr("app.routers.admin.logistics.repository.get_route", _get_route)
    monkeypatch.setattr(
        "app.routers.admin.logistics.repository.get_latest_route_snapshot",
        _get_latest_route_snapshot,
    )
    monkeypatch.setattr(
        "app.routers.admin.logistics.repository.list_navigator_explains",
        _list_navigator_explains,
    )

    _call_case(
        "/api/core/v1/admin/logistics/orders/{order_id}/eta/recompute",
        "post",
        path_parameters={"order_id": "order-1"},
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/logistics/orders/{order_id}/inspection",
        "get",
        path_parameters={"order_id": "order-1"},
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/logistics/routes/{route_id}/navigator",
        "get",
        path_parameters={"route_id": "route-1"},
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/logistics/routes/{route_id}/navigator/explain",
        "get",
        path_parameters={"route_id": "route-1"},
        headers=admin_auth_headers,
    )


def test_ops_workflow_contracts(monkeypatch, admin_auth_headers):
    def _list_escalations(*_args, **_kwargs):
        return (
            [
                SimpleNamespace(
                    id="esc-1",
                    tenant_id=1,
                    client_id="client-1",
                    target=OpsEscalationTarget.CRM,
                    status=OpsEscalationStatus.OPEN,
                    priority=OpsEscalationPriority.MEDIUM,
                    primary_reason=PrimaryReason.LIMIT,
                    reason_code="LIMIT",
                    subject_type="fuel_tx",
                    subject_id="fuel-1",
                    source=OpsEscalationSource.SYSTEM,
                    sla_started_at=NOW,
                    sla_expires_at=NOW,
                    created_at=NOW,
                    acked_at=None,
                    acked_by=None,
                    ack_reason_code=None,
                    ack_reason_text=None,
                    closed_at=None,
                    closed_by=None,
                    close_reason_code=None,
                    close_reason_text=None,
                    created_by_actor_type=None,
                    created_by_actor_id=None,
                    created_by_actor_email=None,
                    unified_explain_snapshot_hash=None,
                    unified_explain_snapshot=None,
                    meta=None,
                )
            ],
            1,
        )

    def _build_sla_report(*_args, **_kwargs):
        return {
            "period": NOW.date().isoformat(),
            "total": 1,
            "closed_within_sla": 1,
            "overdue": 0,
            "sla_breaches": 0,
            "avg_time_to_ack": 10.0,
            "avg_time_to_close": 20.0,
            "by_primary_reason": {PrimaryReason.LIMIT: {"total": 1, "overdue": 0, "sla_breaches": 0}},
            "by_team": {"CRM": {"total": 1, "overdue": 0, "sla_breaches": 0}},
            "by_client": {"client-1": {"total": 1, "overdue": 0, "sla_breaches": 0}},
        }

    monkeypatch.setattr(
        "app.routers.admin.ops.list_escalations",
        _list_escalations,
    )

    monkeypatch.setattr(
        "app.routers.admin.ops.build_sla_report",
        _build_sla_report,
    )

    _call_case(
        "/api/core/v1/admin/ops/escalations",
        "get",
        headers=admin_auth_headers,
    )

    _call_case(
        "/api/core/v1/admin/ops/reports/sla",
        "get",
        headers=admin_auth_headers,
    )
