from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import bi as bi_dependencies
from app.db import Base, get_db
from app.main import app
from app.domains.documents.models import ClientDocument, DocumentEdoState
from app.models.bi import (
    BiDailyMetric,
    BiDeclineEvent,
    BiExportBatch,
    BiExportFormat,
    BiExportKind,
    BiExportStatus,
    BiMartVersion,
    BiOrderEvent,
    BiScopeType,
)


@pytest.fixture(autouse=True)
def enable_bi_clickhouse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi_dependencies.settings, "BI_CLICKHOUSE_ENABLED", True)
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_bi_schema(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("ATTACH DATABASE ':memory:' AS bi")
        cursor.close()

    Base.metadata.create_all(
        bind=engine,
        tables=[
            ClientDocument.__table__,
            DocumentEdoState.__table__,
            BiDailyMetric.__table__,
            BiDeclineEvent.__table__,
            BiOrderEvent.__table__,
            BiExportBatch.__table__,
            BiMartVersion.__table__,
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


def _client_headers(make_jwt, *, client_id: str, tenant_id: int) -> dict[str, str]:
    token = make_jwt(
        roles=("CLIENT_USER",),
        client_id=client_id,
        extra={"tenant_id": tenant_id, "aud": "neft-client"},
    )
    return {"Authorization": f"Bearer {token}"}


def test_client_daily_metrics_summary_route_returns_frontend_contract(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8101
    client_id = "wave1-analytics-client-metrics"
    period_from = date(2026, 1, 1)
    period_to = date(2026, 1, 2)
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add_all(
            [
                BiDailyMetric(
                    tenant_id=tenant_id,
                    date=period_from,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    spend_total=100,
                    orders_total=2,
                    orders_completed=1,
                    refunds_total=0,
                    payouts_total=0,
                    declines_total=1,
                ),
                BiDailyMetric(
                    tenant_id=tenant_id,
                    date=period_to,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    spend_total=150,
                    orders_total=3,
                    orders_completed=2,
                    refunds_total=1,
                    payouts_total=0,
                    declines_total=1,
                ),
                BiDeclineEvent(
                    operation_id="wave1-decline-metrics-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    occurred_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=300,
                    station_id="station-1",
                ),
                BiDeclineEvent(
                    operation_id="wave1-decline-metrics-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    occurred_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=200,
                    station_id="station-2",
                ),
                BiExportBatch(
                    id=export_id,
                    tenant_id=tenant_id,
                    kind=BiExportKind.DAILY_METRICS,
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    date_from=period_from,
                    date_to=period_to,
                    format=BiExportFormat.JSONL,
                    status=BiExportStatus.FAILED,
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/metrics/daily",
            params={
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "from": period_from.isoformat(),
                "to": period_to.isoformat(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["from"] == "2026-01-01"
    assert body["to"] == "2026-01-02"
    assert body["currency"] == "RUB"
    assert body["spend"] == {
        "total": 250,
        "series": [
            {"date": "2026-01-01", "value": 100},
            {"date": "2026-01-02", "value": 150},
        ],
    }
    assert body["orders"] == {
        "total": 5,
        "completed": 3,
        "refunds": 1,
        "series": [
            {"date": "2026-01-01", "value": 2},
            {"date": "2026-01-02", "value": 3},
        ],
    }
    assert body["declines"] == {
        "total": 2,
        "top_reason": "LIMIT",
        "series": [
            {"date": "2026-01-01", "value": 1},
            {"date": "2026-01-02", "value": 1},
        ],
    }
    assert body["documents"] == {"attention": 0}
    assert body["exports"] == {"attention": 1}
    assert body["attention"] == [
        {
            "id": export_id,
            "title": f"Export {export_id}",
            "description": "Status: FAILED",
            "href": "/analytics/exports",
            "severity": "warning",
        }
    ]


def test_client_declines_summary_route_aggregates_event_stream(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8102
    client_id = "wave1-analytics-client-declines"
    period_from = date(2026, 2, 1)
    period_to = date(2026, 2, 3)

    with db_session_factory() as db:
        db.add_all(
            [
                BiDeclineEvent(
                    operation_id="wave1-decline-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    occurred_at=datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=700,
                    station_id="station-1",
                ),
                BiDeclineEvent(
                    operation_id="wave1-decline-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    occurred_at=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=150,
                    station_id="station-1",
                ),
                BiDeclineEvent(
                    operation_id="wave1-decline-3",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    occurred_at=datetime(2026, 2, 2, 9, 30, tzinfo=timezone.utc),
                    primary_reason="FRAUD",
                    amount=50,
                    station_id="station-2",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/declines",
            params={"from": period_from.isoformat(), "to": period_to.isoformat()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["top_reasons"] == [
        {"reason": "LIMIT", "count": 2},
        {"reason": "FRAUD", "count": 1},
    ]
    assert body["trend"] == [
        {"date": "2026-02-01", "reason": "LIMIT", "count": 2},
        {"date": "2026-02-02", "reason": "FRAUD", "count": 1},
    ]
    assert body["heatmap"] == [
        {"station": "station-1", "reason": "LIMIT", "count": 2},
        {"station": "station-2", "reason": "FRAUD", "count": 1},
    ]
    assert body["expensive"] == [
        {"id": "wave1-decline-1", "reason": "LIMIT", "amount": 700, "station": "station-1"},
        {"id": "wave1-decline-2", "reason": "LIMIT", "amount": 150, "station": "station-1"},
        {"id": "wave1-decline-3", "reason": "FRAUD", "amount": 50, "station": "station-2"},
    ]


def test_client_orders_summary_route_aggregates_order_events(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 8103
    client_id = "wave1-analytics-client-orders"
    period_from = date(2026, 3, 1)
    period_to = date(2026, 3, 2)

    with db_session_factory() as db:
        db.add_all(
            [
                BiOrderEvent(
                    event_id="wave1-order-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    order_id="order-1",
                    event_type="ORDER_COMPLETED",
                    occurred_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
                    amount=1000,
                    currency="RUB",
                    service_id="fuel",
                    status_after="COMPLETED",
                ),
                BiOrderEvent(
                    event_id="wave1-order-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    order_id="order-2",
                    event_type="ORDER_CANCELLED",
                    occurred_at=datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc),
                    amount=0,
                    currency="RUB",
                    service_id="fuel",
                    status_after="CANCELLED",
                ),
                BiOrderEvent(
                    event_id="wave1-order-3",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    order_id="order-3",
                    event_type="ORDER_COMPLETED",
                    occurred_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
                    amount=500,
                    currency="RUB",
                    service_id="wash",
                    status_after="COMPLETED",
                ),
                BiOrderEvent(
                    event_id="wave1-order-4",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    order_id="order-4",
                    event_type="ORDER_REFUND",
                    occurred_at=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
                    amount=500,
                    currency="RUB",
                    service_id="wash",
                    status_after="REFUNDED",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/core/bi/orders/summary",
            params={"from": period_from.isoformat(), "to": period_to.isoformat()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["completed"] == 2
    assert body["cancelled"] == 1
    assert body["refunds_count"] == 1
    assert body["refunds_rate"] == 25
    assert body["avg_order_value"] == 750
    assert body["top_services"] == [
        {"name": "fuel", "orders": 2},
        {"name": "wash", "orders": 2},
    ]
    assert body["status_breakdown"] == [
        {"status": "COMPLETED", "count": 2},
        {"status": "CANCELLED", "count": 1},
        {"status": "REFUNDED", "count": 1},
    ]
