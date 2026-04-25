from __future__ import annotations

from csv import reader
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
import logging
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import reports_billing as reports_billing_endpoint
from app.db import Base, get_db
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.fuel import FuelNetwork, FuelStation, FuelStationNetwork
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.schemas.reports import (
    TurnoverGroupKey,
    TurnoverItem,
    TurnoverReportResponse,
    TurnoverTotals,
)
from app.services import reports_billing as reports_billing_service
from app.services.billing_periods import period_bounds_for_dates
from app.services.reports_route_metrics import metrics as reports_route_metrics


def _find_route(path: str, method: str) -> APIRoute | None:
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in (route.methods or set()):
            return route
    return None


@pytest.fixture(autouse=True)
def allow_mock_providers_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture(autouse=True)
def reset_reports_route_observability() -> None:
    reports_route_metrics.reset()
    yield
    reports_route_metrics.reset()

@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            FuelNetwork.__table__,
            FuelStationNetwork.__table__,
            FuelStation.__table__,
            Operation.__table__,
            BillingPeriod.__table__,
            BillingSummary.__table__,
        ],
    )

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield testing_session_local
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()



def _make_capture_operation(
    *,
    ext_operation_id: str,
    created_at: datetime,
    merchant_id: str,
    client_id: str,
    amount: int,
    terminal_id: str = "terminal-1",
    card_id: str = "card-1",
) -> Operation:
    return Operation(
        ext_operation_id=ext_operation_id,
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        created_at=created_at,
        updated_at=created_at,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        client_id=client_id,
        card_id=card_id,
        amount=amount,
        currency="RUB",
        captured_amount=amount,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )



def _turnover_report(*, merchant_id: str, start: datetime, end: datetime) -> TurnoverReportResponse:
    return TurnoverReportResponse(
        items=[
            TurnoverItem(
                group_key=TurnoverGroupKey(merchant_id=merchant_id),
                transaction_count=1,
                authorized_amount=1500,
                captured_amount=1500,
                refunded_amount=0,
                net_turnover=1500,
                currency="RUB",
            )
        ],
        totals=TurnoverTotals(
            transaction_count=1,
            authorized_amount=1500,
            captured_amount=1500,
            refunded_amount=0,
            net_turnover=1500,
            currency="RUB",
        ),
        group_by="merchant",
        from_created_at=start,
        to_created_at=end,
    )



def test_reports_billing_daily_public_read_compatibility_tail(
    db_session_factory: sessionmaker[Session],
) -> None:
    report_date = date(2026, 4, 20)
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)

    with db_session_factory() as db:
        db.add_all(
            [
                _make_capture_operation(
                    ext_operation_id="daily-op-1",
                    created_at=ts,
                    merchant_id="m-1",
                    client_id="c-1",
                    amount=1000,
                ),
                _make_capture_operation(
                    ext_operation_id="daily-op-2",
                    created_at=ts.replace(hour=11),
                    merchant_id="m-1",
                    client_id="c-2",
                    amount=500,
                ),
                _make_capture_operation(
                    ext_operation_id="daily-op-3",
                    created_at=ts,
                    merchant_id="m-2",
                    client_id="c-3",
                    amount=900,
                ),
            ]
        )
        db.commit()

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/reports/billing/daily",
            params={
                "date_from": report_date.isoformat(),
                "date_to": report_date.isoformat(),
                "merchant_id": "m-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == [
        {
            "date": report_date.isoformat(),
            "merchant_id": "m-1",
            "total_captured_amount": 1500,
            "total_operations": 2,
        }
    ]



def test_reports_billing_summary_public_read_compatibility_tail(
    db_session_factory: sessionmaker[Session],
) -> None:
    billing_date = date(2026, 4, 21)
    start_at, end_at = period_bounds_for_dates(
        date_from=billing_date,
        date_to=billing_date,
        tz=reports_billing_service.settings.NEFT_BILLING_TZ,
    )

    with db_session_factory() as db:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz=reports_billing_service.settings.NEFT_BILLING_TZ,
            status=BillingPeriodStatus.OPEN,
        )
        db.add(period)
        db.flush()
        db.add(
            BillingSummary(
                billing_date=billing_date,
                billing_period_id=period.id,
                merchant_id="m-1",
                total_amount=2300,
                operations_count=2,
                status=BillingSummaryStatus.PENDING,
                generated_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
                hash="summary-hash",
            )
        )
        db.commit()

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/reports/billing/summary",
            params={
                "date_from": billing_date.isoformat(),
                "date_to": billing_date.isoformat(),
                "merchant_id": "m-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["date"] == billing_date.isoformat()
    assert body[0]["merchant_id"] == "m-1"
    assert body[0]["total_captured_amount"] == 2300
    assert body[0]["operations_count"] == 2
    assert body[0]["status"] == "PENDING"
    assert body[0]["hash"] == "summary-hash"



def test_billing_summary_shared_row_has_compatibility_public_and_admin_projections(
    db_session_factory: sessionmaker[Session],
    admin_auth_headers: dict[str, str],
) -> None:
    billing_date = date(2026, 4, 26)
    generated_at = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    finalized_at = datetime(2026, 4, 26, 13, 30, tzinfo=timezone.utc)
    start_at, end_at = period_bounds_for_dates(
        date_from=billing_date,
        date_to=billing_date,
        tz=reports_billing_service.settings.NEFT_BILLING_TZ,
    )

    with db_session_factory() as db:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz=reports_billing_service.settings.NEFT_BILLING_TZ,
            status=BillingPeriodStatus.OPEN,
        )
        db.add(period)
        db.flush()

        summary = BillingSummary(
            billing_date=billing_date,
            billing_period_id=period.id,
            client_id='c-shared',
            merchant_id='m-shared',
            product_type=ProductType.DIESEL,
            currency='RUB',
            total_amount=2300,
            total_quantity=Decimal('10.500'),
            operations_count=2,
            commission_amount=23,
            status=BillingSummaryStatus.FINALIZED,
            generated_at=generated_at,
            finalized_at=finalized_at,
            hash='shared-summary-hash',
        )
        db.add(summary)
        db.commit()
        db.refresh(summary)
        summary_id = summary.id

    with TestClient(app) as api_client:
        public_response = api_client.get(
            '/api/v1/reports/billing/summary',
            params={
                'date_from': billing_date.isoformat(),
                'date_to': billing_date.isoformat(),
                'merchant_id': 'm-shared',
            },
        )
        admin_single_response = api_client.get(
            f'/api/v1/admin/billing/summary/{summary_id}',
            headers=admin_auth_headers,
        )
        admin_list_response = api_client.get(
            '/api/v1/admin/billing/summary',
            params={
                'date_from': billing_date.isoformat(),
                'date_to': billing_date.isoformat(),
                'client_id': 'c-shared',
                'merchant_id': 'm-shared',
                'product_type': ProductType.DIESEL.value,
                'currency': 'RUB',
                'limit': 10,
                'offset': 0,
            },
            headers=admin_auth_headers,
        )

    assert public_response.status_code == 200
    public_body = public_response.json()
    assert public_body == [
        {
            'date': billing_date.isoformat(),
            'merchant_id': 'm-shared',
            'total_captured_amount': 2300,
            'operations_count': 2,
            'status': 'FINALIZED',
            'generated_at': generated_at.replace(tzinfo=None).isoformat(),
            'finalized_at': finalized_at.replace(tzinfo=None).isoformat(),
            'id': summary_id,
            'hash': 'shared-summary-hash',
        }
    ]

    assert admin_single_response.status_code == 200
    admin_single_body = admin_single_response.json()
    assert admin_single_body == public_body[0]

    assert admin_list_response.status_code == 200
    admin_list_body = admin_list_response.json()
    assert admin_list_body['total'] == 1
    assert admin_list_body['limit'] == 10
    assert admin_list_body['offset'] == 0
    assert admin_list_body['items'] == [
        {
            'billing_date': billing_date.isoformat(),
            'client_id': 'c-shared',
            'merchant_id': 'm-shared',
            'product_type': ProductType.DIESEL.value,
            'currency': 'RUB',
            'total_amount': 2300,
            'total_quantity': '10.500',
            'operations_count': 2,
            'commission_amount': 23,
        }
    ]
    assert admin_list_body['items'][0]['billing_date'] == public_body[0]['date']
    assert admin_list_body['items'][0]['total_amount'] == public_body[0]['total_captured_amount']


def test_reports_turnover_public_read_compatibility_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 22, 23, 59, tzinfo=timezone.utc)
    calls: list[dict[str, object]] = []

    def _fake_turnover_report(db, **kwargs):
        calls.append(kwargs)
        return _turnover_report(merchant_id="m-1", start=start, end=end)

    monkeypatch.setattr(reports_billing_endpoint, "get_turnover_report", _fake_turnover_report)

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/reports/turnover",
            params={
                "group_by": "merchant",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "merchant_id": "m-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "merchant"
    assert body["totals"]["captured_amount"] == 1500
    assert body["items"][0]["group_key"]["merchant_id"] == "m-1"
    assert calls == [
        {
            "group_by": "merchant",
            "from_created_at": start,
            "to_created_at": end,
            "client_id": None,
            "card_id": None,
            "merchant_id": "m-1",
            "terminal_id": None,
        }
    ]



def test_reports_turnover_export_public_read_compatibility_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 23, 23, 59, tzinfo=timezone.utc)

    monkeypatch.setattr(
        reports_billing_endpoint,
        "get_turnover_report",
        lambda db, **kwargs: _turnover_report(merchant_id="m-1", start=start, end=end),
    )

    with TestClient(app) as api_client:
        response = api_client.get(
            "/api/v1/reports/turnover/export",
            params={
                "group_by": "merchant",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "merchant_id": "m-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="turnover_report.csv"'
    rows = list(reader(StringIO(response.text), delimiter=";"))
    assert rows[0] == [
        "group_by",
        "client_id",
        "card_id",
        "merchant_id",
        "terminal_id",
        "transaction_count",
        "authorized_amount",
        "captured_amount",
        "refunded_amount",
        "net_turnover",
        "currency",
        "from",
        "to",
    ]
    assert rows[1] == [
        "merchant",
        "",
        "",
        "m-1",
        "",
        "1",
        "1500",
        "1500",
        "0",
        "1500",
        "RUB",
        start.isoformat(),
        end.isoformat(),
    ]



def test_reports_billing_rebuild_requires_admin_billing_permission() -> None:
    billing_date = date(2026, 4, 24)

    with TestClient(app) as api_client:
        response = api_client.post(
            "/api/v1/reports/billing/summary/rebuild",
            params={
                "date_from": billing_date.isoformat(),
                "date_to": billing_date.isoformat(),
                "merchant_id": "m-1",
            },
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "Missing bearer token"



def test_reports_billing_rebuild_allows_authorized_admin_path(
    db_session_factory: sessionmaker[Session],
    admin_auth_headers: dict[str, str],
) -> None:
    billing_date = date(2026, 4, 24)
    ts = datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)

    with db_session_factory() as db:
        db.add_all(
            [
                _make_capture_operation(
                    ext_operation_id="rebuild-op-1",
                    created_at=ts,
                    merchant_id="m-1",
                    client_id="c-1",
                    amount=1200,
                ),
                _make_capture_operation(
                    ext_operation_id="rebuild-op-2",
                    created_at=ts.replace(hour=11),
                    merchant_id="m-1",
                    client_id="c-2",
                    amount=800,
                ),
            ]
        )
        db.commit()

    with TestClient(app) as api_client:
        response = api_client.post(
            "/api/v1/reports/billing/summary/rebuild",
            params={
                "date_from": billing_date.isoformat(),
                "date_to": billing_date.isoformat(),
                "merchant_id": "m-1",
            },
            headers=admin_auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["date"] == billing_date.isoformat()
    assert body[0]["merchant_id"] == "m-1"
    assert body[0]["total_captured_amount"] == 2000
    assert body[0]["operations_count"] == 2
    assert body[0]["status"] == "PENDING"

    with db_session_factory() as db:
        summaries = db.query(BillingSummary).all()
        assert len(summaries) == 1
        assert summaries[0].total_amount == 2000
        assert summaries[0].operations_count == 2



def test_reports_billing_rebuild_conflict_path_for_authorized_admin(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    admin_auth_headers: dict[str, str],
) -> None:
    billing_date = date(2026, 4, 25)
    start_at, end_at = period_bounds_for_dates(
        date_from=billing_date,
        date_to=billing_date,
        tz=reports_billing_service.settings.NEFT_BILLING_TZ,
    )

    with db_session_factory() as db:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz=reports_billing_service.settings.NEFT_BILLING_TZ,
            status=BillingPeriodStatus.LOCKED,
        )
        db.add(period)
        db.commit()
        period_id = str(period.id)

    monkeypatch.setattr(reports_billing_endpoint.AuditService, "audit", lambda self, **kwargs: None)

    with TestClient(app) as api_client:
        response = api_client.post(
            "/api/v1/reports/billing/summary/rebuild",
            params={
                "date_from": billing_date.isoformat(),
                "date_to": billing_date.isoformat(),
                "merchant_id": "m-1",
            },
            headers=admin_auth_headers,
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == f"Billing period {period_id} is LOCKED"


def test_reports_routes_stay_frozen_compatibility_tails_pending_consumer_diagnosis() -> None:
    frozen_compatibility_routes = {
        ("GET", "/api/v1/reports/billing/daily"),
        ("GET", "/api/v1/reports/billing/summary"),
        ("GET", "/api/v1/reports/turnover"),
        ("GET", "/api/v1/reports/turnover/export"),
        ("POST", "/api/v1/reports/billing/summary/rebuild"),
    }

    for method, path in frozen_compatibility_routes:
        route = _find_route(path, method)
        assert route is not None, f"compatibility route missing: {method} {path}"
        assert route.include_in_schema is True

    assert _find_route("/api/v1/admin/billing/summary", "GET") is not None
    assert _find_route("/api/v1/admin/billing/summary/{summary_id}", "GET") is not None


def test_reports_routes_emit_structured_logs_and_metrics(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    admin_auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    daily_date = date(2026, 4, 27)
    billing_date = date(2026, 4, 28)
    rebuild_date = date(2026, 4, 29)
    start = datetime(2026, 4, 30, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc)
    billing_start_at, billing_end_at = period_bounds_for_dates(
        date_from=billing_date,
        date_to=billing_date,
        tz=reports_billing_service.settings.NEFT_BILLING_TZ,
    )

    with db_session_factory() as db:
        db.add(
            BillingPeriod(
                period_type=BillingPeriodType.ADHOC,
                start_at=billing_start_at,
                end_at=billing_end_at,
                tz=reports_billing_service.settings.NEFT_BILLING_TZ,
                status=BillingPeriodStatus.OPEN,
            )
        )
        db.flush()
        db.add(
            BillingSummary(
                billing_date=billing_date,
                billing_period_id=db.query(BillingPeriod).first().id,
                merchant_id="m-observe",
                total_amount=1800,
                operations_count=1,
                status=BillingSummaryStatus.PENDING,
                generated_at=datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc),
                hash="observe-hash",
            )
        )
        db.add(
            _make_capture_operation(
                ext_operation_id="daily-observe-op",
                created_at=datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc),
                merchant_id="m-observe",
                client_id="c-observe-1",
                amount=900,
            )
        )
        db.add(
            _make_capture_operation(
                ext_operation_id="rebuild-observe-op",
                created_at=datetime(2026, 4, 29, 11, 0, tzinfo=timezone.utc),
                merchant_id="m-observe",
                client_id="c-observe-2",
                amount=1100,
            )
        )
        db.commit()

    monkeypatch.setattr(
        reports_billing_endpoint,
        "get_turnover_report",
        lambda db, **kwargs: _turnover_report(merchant_id="m-observe", start=start, end=end),
    )

    caplog.set_level(logging.INFO, logger=reports_billing_endpoint.__name__)

    with TestClient(app) as api_client:
        assert api_client.get(
            "/api/v1/reports/billing/daily",
            params={
                "date_from": daily_date.isoformat(),
                "date_to": daily_date.isoformat(),
                "merchant_id": "m-observe",
            },
        ).status_code == 200

        assert api_client.get(
            "/api/v1/reports/billing/summary",
            params={
                "date_from": billing_date.isoformat(),
                "date_to": billing_date.isoformat(),
                "merchant_id": "m-observe",
            },
        ).status_code == 200

        assert api_client.get(
            "/api/v1/reports/turnover",
            params={
                "group_by": "merchant",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "merchant_id": "m-observe",
            },
        ).status_code == 200

        assert api_client.get(
            "/api/v1/reports/turnover/export",
            params={
                "group_by": "merchant",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "merchant_id": "m-observe",
            },
        ).status_code == 200

        assert api_client.post(
            "/api/v1/reports/billing/summary/rebuild",
            params={
                "date_from": rebuild_date.isoformat(),
                "date_to": rebuild_date.isoformat(),
                "merchant_id": "m-observe",
            },
            headers=admin_auth_headers,
        ).status_code == 200

        metrics_response = api_client.get("/metrics")

    assert metrics_response.status_code == 200
    metrics_body = metrics_response.text
    assert (
        'core_api_reports_compat_requests_total{route="/api/v1/reports/billing/daily",method="GET",outcome="success"} 1'
        in metrics_body
    )
    assert (
        'core_api_reports_compat_requests_total{route="/api/v1/reports/billing/summary",method="GET",outcome="success"} 1'
        in metrics_body
    )
    assert (
        'core_api_reports_compat_requests_total{route="/api/v1/reports/turnover",method="GET",outcome="success"} 1'
        in metrics_body
    )
    assert (
        'core_api_reports_compat_requests_total{route="/api/v1/reports/turnover/export",method="GET",outcome="success"} 1'
        in metrics_body
    )
    assert (
        'core_api_reports_compat_requests_total{route="/api/v1/reports/billing/summary/rebuild",method="POST",outcome="success"} 1'
        in metrics_body
    )
    assert 'core_api_reports_compat_duration_seconds_bucket{route="/api/v1/reports/billing/daily",method="GET",le="+Inf"} 1' in metrics_body

    request_totals = reports_route_metrics.requests_total
    assert request_totals[("/api/v1/reports/billing/daily", "GET", "success")] == 1
    assert request_totals[("/api/v1/reports/billing/summary", "GET", "success")] == 1
    assert request_totals[("/api/v1/reports/turnover", "GET", "success")] == 1
    assert request_totals[("/api/v1/reports/turnover/export", "GET", "success")] == 1
    assert request_totals[("/api/v1/reports/billing/summary/rebuild", "POST", "success")] == 1

    records = [record for record in caplog.records if record.name == reports_billing_endpoint.__name__]
    event_names = {record.msg for record in records}
    assert {
        "reports_billing_daily_read",
        "reports_billing_summary_read",
        "reports_turnover_read",
        "reports_turnover_export",
        "reports_billing_summary_rebuild",
    }.issubset(event_names)
    for record in records:
        if record.msg not in event_names:
            continue
        assert getattr(record, "surface_status", None) == "compatibility_tail"
        assert getattr(record, "outcome", None) == "success"
        assert getattr(record, "route", None)
        assert getattr(record, "method", None)
        assert getattr(record, "duration_ms", None) is not None
