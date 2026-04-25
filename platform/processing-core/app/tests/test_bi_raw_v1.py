from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import bi as bi_dependencies
from app.api.v1.endpoints import bi as raw_bi
from app.db import Base, get_db
from app.main import app
from app.models.bi import (
    BiDailyMetric,
    BiDeclineEvent,
    BiExportBatch,
    BiExportFormat,
    BiExportKind,
    BiExportStatus,
    BiOrderEvent,
    BiPayoutEvent,
    BiScopeType,
)


@pytest.fixture(autouse=True)
def enable_bi_clickhouse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi_dependencies.settings, "BI_CLICKHOUSE_ENABLED", True)
    monkeypatch.setattr(raw_bi.bi_exports.settings, "BI_CLICKHOUSE_ENABLED", True)
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture(autouse=True)
def allow_raw_bi_abac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raw_bi, "get_abac_principal", lambda request, db: {"sub": "raw-bi-test"})
    monkeypatch.setattr(
        raw_bi.AbacEngine,
        "evaluate",
        lambda self, **kwargs: SimpleNamespace(allowed=True, reason_code=None, matched_policies=[], explain=[]),
    )


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
            BiDailyMetric.__table__,
            BiDeclineEvent.__table__,
            BiOrderEvent.__table__,
            BiPayoutEvent.__table__,
            BiExportBatch.__table__,
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


def test_raw_bi_metrics_daily_returns_raw_rows(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9101
    client_id = "raw-bi-client-metrics"
    other_client_id = "raw-bi-client-other"

    with db_session_factory() as db:
        db.add_all(
            [
                BiDailyMetric(
                    tenant_id=tenant_id,
                    date=date(2026, 4, 1),
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    spend_total=100,
                    orders_total=2,
                    orders_completed=1,
                    refunds_total=0,
                    payouts_total=0,
                    declines_total=1,
                    top_primary_reason="LIMIT",
                ),
                BiDailyMetric(
                    tenant_id=tenant_id,
                    date=date(2026, 4, 2),
                    scope_type=BiScopeType.CLIENT,
                    scope_id=client_id,
                    spend_total=200,
                    orders_total=3,
                    orders_completed=2,
                    refunds_total=1,
                    payouts_total=0,
                    declines_total=0,
                    top_primary_reason="FRAUD",
                ),
                BiDailyMetric(
                    tenant_id=tenant_id,
                    date=date(2026, 4, 2),
                    scope_type=BiScopeType.CLIENT,
                    scope_id=other_client_id,
                    spend_total=999,
                    orders_total=9,
                    orders_completed=9,
                    refunds_total=0,
                    payouts_total=0,
                    declines_total=0,
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/metrics/daily",
            params={
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "from": "2026-04-01",
                "to": "2026-04-02",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [row["date"] for row in body] == ["2026-04-01", "2026-04-02"]
    assert [row["scope_id"] for row in body] == [client_id, client_id]
    assert body[0]["spend_total"] == 100
    assert body[1]["orders_total"] == 3


def test_raw_bi_orders_returns_filtered_event_rows(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9102
    client_id = "raw-bi-client-orders"

    with db_session_factory() as db:
        db.add_all(
            [
                BiOrderEvent(
                    event_id="raw-order-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    order_id="order-1",
                    event_type="ORDER_COMPLETED",
                    occurred_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
                    amount=1500,
                    currency="RUB",
                    service_id="fuel",
                    offer_id="offer-1",
                    status_after="COMPLETED",
                ),
                BiOrderEvent(
                    event_id="raw-order-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    order_id="order-2",
                    event_type="ORDER_CANCELLED",
                    occurred_at=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
                    amount=0,
                    currency="RUB",
                    service_id="wash",
                    offer_id="offer-2",
                    status_after="CANCELLED",
                ),
                BiOrderEvent(
                    event_id="raw-order-3",
                    tenant_id=tenant_id,
                    client_id="other-client",
                    partner_id="partner-2",
                    order_id="order-3",
                    event_type="ORDER_COMPLETED",
                    occurred_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
                    amount=900,
                    currency="RUB",
                    service_id="fuel",
                    offer_id="offer-3",
                    status_after="COMPLETED",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/orders",
            params={
                "from": "2026-04-03T00:00:00Z",
                "to": "2026-04-03T23:59:59Z",
                "client_id": client_id,
                "status": "COMPLETED",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [row["event_id"] for row in body] == ["raw-order-1"]
    assert body[0]["order_id"] == "order-1"
    assert body[0]["status_after"] == "COMPLETED"
    assert body[0]["amount"] == 1500


def test_raw_bi_declines_returns_filtered_rows(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9104
    client_id = "raw-bi-client-declines"

    with db_session_factory() as db:
        db.add_all(
            [
                BiDeclineEvent(
                    operation_id="decline-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=700,
                    product_type="fuel",
                    station_id="station-1",
                ),
                BiDeclineEvent(
                    operation_id="decline-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
                    primary_reason="FRAUD",
                    amount=500,
                    product_type="wash",
                    station_id="station-2",
                ),
                BiDeclineEvent(
                    operation_id="decline-3",
                    tenant_id=tenant_id,
                    client_id="other-client",
                    partner_id="partner-2",
                    occurred_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                    amount=999,
                    product_type="fuel",
                    station_id="station-1",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/declines",
            params={
                "from": "2026-04-04T00:00:00Z",
                "to": "2026-04-04T23:59:59Z",
                "client_id": client_id,
                "reason": "LIMIT",
                "station_id": "station-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [row["operation_id"] for row in body] == ["decline-1"]
    assert body[0]["primary_reason"] == "LIMIT"
    assert body[0]["station_id"] == "station-1"
    assert body[0]["amount"] == 700


def test_raw_bi_payouts_returns_filtered_rows(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9105
    client_id = "raw-bi-client-payouts"

    with db_session_factory() as db:
        db.add_all(
            [
                BiPayoutEvent(
                    event_id="payout-1",
                    tenant_id=tenant_id,
                    partner_id="partner-1",
                    settlement_id="settlement-1",
                    payout_batch_id="batch-1",
                    event_type="PAYOUT_CONFIRMED",
                    occurred_at=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
                    amount_gross=3000,
                    amount_net=2700,
                    amount_commission=300,
                    currency="RUB",
                ),
                BiPayoutEvent(
                    event_id="payout-2",
                    tenant_id=tenant_id,
                    partner_id="partner-2",
                    settlement_id="settlement-2",
                    payout_batch_id="batch-2",
                    event_type="PAYOUT_CONFIRMED",
                    occurred_at=datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc),
                    amount_gross=5000,
                    amount_net=4500,
                    amount_commission=500,
                    currency="RUB",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/payouts",
            params={
                "from": "2026-04-05T00:00:00Z",
                "to": "2026-04-05T23:59:59Z",
                "partner_id": "partner-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["partner_id"] == "partner-1"
    assert body[0]["settlement_id"] == "settlement-1"
    assert body[0]["amount_net"] == 2700


def test_raw_bi_top_reasons_returns_ranked_counts(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9106
    client_id = "raw-bi-client-top-reasons"

    with db_session_factory() as db:
        db.add_all(
            [
                BiDeclineEvent(
                    operation_id="top-reason-1",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                ),
                BiDeclineEvent(
                    operation_id="top-reason-2",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                ),
                BiDeclineEvent(
                    operation_id="top-reason-3",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 6, 11, 0, tzinfo=timezone.utc),
                    primary_reason="LIMIT",
                ),
                BiDeclineEvent(
                    operation_id="top-reason-4",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    partner_id="partner-1",
                    occurred_at=datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc),
                    primary_reason="FRAUD",
                ),
                BiDeclineEvent(
                    operation_id="top-reason-5",
                    tenant_id=tenant_id,
                    client_id="other-client",
                    partner_id="partner-2",
                    occurred_at=datetime(2026, 4, 6, 13, 0, tzinfo=timezone.utc),
                    primary_reason="FRAUD",
                ),
            ]
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/top-reasons",
            params={
                "from": "2026-04-06T00:00:00Z",
                "to": "2026-04-06T23:59:59Z",
                "scope_type": "CLIENT",
                "scope_id": client_id,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"primary_reason": "LIMIT", "count": 3},
        {"primary_reason": "FRAUD", "count": 1},
    ]


def test_raw_bi_export_get_and_confirm_flow(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9103
    client_id = "raw-bi-client-exports"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDERS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 3),
                format=BiExportFormat.CSV,
                status=BiExportStatus.DELIVERED,
                object_key="bi/test/orders.csv",
                bucket="test-bucket",
                sha256="abc123",
                row_count=5,
                created_by="user-1",
            )
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        get_response = api_client.get(f"/api/v1/bi/exports/{export_id}")
        confirm_response = api_client.post(f"/api/v1/bi/exports/{export_id}/confirm")

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "DELIVERED"
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "CONFIRMED"


def test_raw_bi_export_download_returns_presigned_url(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9107
    client_id = "raw-bi-client-download"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDERS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 7),
                format=BiExportFormat.CSV,
                status=BiExportStatus.DELIVERED,
                object_key="bi/test/orders.csv",
                bucket="test-bucket",
                sha256="download-hash",
                row_count=3,
                created_by="user-1",
            )
        )
        db.commit()

    monkeypatch.setattr(raw_bi.S3Storage, "presign", lambda self, key: f"https://signed.example/{key}")

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/download")

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://signed.example/bi/test/orders.csv",
        "sha256": "download-hash",
        "status": "DELIVERED",
    }


def test_raw_bi_export_manifest_returns_embedded_manifest_when_presign_missing(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9108
    client_id = "raw-bi-client-manifest"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDER_EVENTS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 8),
                format=BiExportFormat.JSONL,
                status=BiExportStatus.DELIVERED,
                manifest_key="bi/test/orders.manifest.json",
                bucket="test-bucket",
                created_by="user-1",
            )
        )
        db.commit()

    monkeypatch.setattr(raw_bi.S3Storage, "presign", lambda self, key: None)
    monkeypatch.setattr(
        raw_bi.S3Storage,
        "get_bytes",
        lambda self, key: b'{"rows": 5, "dataset": "order_events"}',
    )

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/manifest")

    assert response.status_code == 200
    assert response.json() == {
        "manifest": {"rows": 5, "dataset": "order_events"},
        "status": "DELIVERED",
    }


def test_raw_bi_metrics_daily_rejects_abac_denial(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9109
    client_id = "raw-bi-client-denied"

    with db_session_factory() as db:
        db.add(
            BiDailyMetric(
                tenant_id=tenant_id,
                date=date(2026, 4, 9),
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                spend_total=50,
                orders_total=1,
                orders_completed=1,
                refunds_total=0,
                payouts_total=0,
                declines_total=0,
            )
        )
        db.commit()

    monkeypatch.setattr(
        raw_bi.AbacEngine,
        "evaluate",
        lambda self, **kwargs: SimpleNamespace(
            allowed=False,
            reason_code="bi_scope_denied",
            matched_policies=["bi.scope.read"],
            explain=["denied for test"],
        ),
    )

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(
            "/api/v1/bi/metrics/daily",
            params={
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "from": "2026-04-09",
                "to": "2026-04-09",
            },
        )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "abac_deny"
    assert body["reason_code"] == "bi_scope_denied"
    assert body["matched_policies"] == ["bi.scope.read"]
    assert body["explain"] == ["denied for test"]



def test_raw_bi_export_get_returns_not_found(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9110
    client_id = "raw-bi-client-missing-export"

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "export_not_found"



def test_raw_bi_export_download_rejects_foreign_tenant_access(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9111
    foreign_tenant_id = 9112
    client_id = "raw-bi-client-foreign-export"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=foreign_tenant_id,
                kind=BiExportKind.ORDERS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 10),
                format=BiExportFormat.CSV,
                status=BiExportStatus.DELIVERED,
                object_key="bi/foreign/orders.csv",
                bucket="test-bucket",
                created_by="user-1",
            )
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/download")

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "forbidden"



def test_raw_bi_export_download_returns_not_ready_when_object_missing(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9113
    client_id = "raw-bi-client-download-not-ready"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDERS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 11),
                format=BiExportFormat.CSV,
                status=BiExportStatus.GENERATED,
                object_key=None,
                bucket="test-bucket",
                created_by="user-1",
            )
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/download")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "export_not_ready"



def test_raw_bi_export_manifest_returns_not_ready_when_manifest_missing(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9114
    client_id = "raw-bi-client-manifest-not-ready"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDER_EVENTS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 12),
                format=BiExportFormat.JSONL,
                status=BiExportStatus.GENERATED,
                manifest_key=None,
                bucket="test-bucket",
                created_by="user-1",
            )
        )
        db.commit()

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/manifest")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "manifest_not_ready"



def test_raw_bi_export_manifest_returns_unavailable_when_storage_has_no_payload(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9115
    client_id = "raw-bi-client-manifest-unavailable"
    export_id = str(uuid4())

    with db_session_factory() as db:
        db.add(
            BiExportBatch(
                id=export_id,
                tenant_id=tenant_id,
                kind=BiExportKind.ORDER_EVENTS,
                scope_type=BiScopeType.CLIENT,
                scope_id=client_id,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 13),
                format=BiExportFormat.JSONL,
                status=BiExportStatus.DELIVERED,
                manifest_key="bi/test/unavailable.manifest.json",
                bucket="test-bucket",
                created_by="user-1",
            )
        )
        db.commit()

    monkeypatch.setattr(raw_bi.S3Storage, "presign", lambda self, key: None)
    monkeypatch.setattr(raw_bi.S3Storage, "get_bytes", lambda self, key: None)

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.get(f"/api/v1/bi/exports/{export_id}/manifest")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "manifest_unavailable"

def test_raw_bi_create_export_returns_created_batch_and_queues_task(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9116
    client_id = "raw-bi-client-create"
    queued: list[str] = []
    monkeypatch.setenv("DISABLE_CELERY", "0")
    monkeypatch.setattr(raw_bi, "generate_export_task", SimpleNamespace(delay=lambda export_id: queued.append(export_id)))

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.post(
            "/api/v1/bi/exports",
            json={
                "kind": "ORDERS",
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "date_from": "2026-04-01",
                "date_to": "2026-04-14",
                "format": "CSV",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == tenant_id
    assert body["kind"] == "ORDERS"
    assert body["scope_type"] == "CLIENT"
    assert body["scope_id"] == client_id
    assert body["date_from"] == "2026-04-01"
    assert body["date_to"] == "2026-04-14"
    assert body["format"] == "CSV"
    assert body["status"] == "CREATED"
    assert body["object_key"] is None
    assert body["manifest_key"] is None
    assert body["bucket"] is None
    assert body["sha256"] is None
    assert body["row_count"] is None
    assert body["created_by"] is not None
    assert body["created_at"] is not None
    assert queued == [body["id"]]

    with db_session_factory() as db:
        export = db.query(BiExportBatch).filter(BiExportBatch.id == body["id"]).one()
        assert export.tenant_id == tenant_id
        assert export.kind == BiExportKind.ORDERS
        assert export.scope_type == BiScopeType.CLIENT
        assert export.scope_id == client_id
        assert export.status == BiExportStatus.CREATED



def test_raw_bi_create_export_rejects_abac_denial(
    db_session_factory: sessionmaker[Session],
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = 9117
    client_id = "raw-bi-client-create-denied"

    monkeypatch.setattr(
        raw_bi.AbacEngine,
        "evaluate",
        lambda self, **kwargs: SimpleNamespace(
            allowed=False,
            reason_code="bi_scope_denied",
            matched_policies=["bi.scope.create"],
            explain=["create denied for test"],
        ),
    )

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.post(
            "/api/v1/bi/exports",
            json={
                "kind": "ORDERS",
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "date_from": "2026-04-01",
                "date_to": "2026-04-15",
                "format": "CSV",
            },
        )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "abac_deny"
    assert body["reason_code"] == "bi_scope_denied"
    assert body["matched_policies"] == ["bi.scope.create"]
    assert body["explain"] == ["create denied for test"]



def test_raw_bi_create_export_rejects_unsupported_export_format(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9118
    client_id = "raw-bi-client-create-format"

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.post(
            "/api/v1/bi/exports",
            json={
                "kind": "ORDERS",
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "date_from": "2026-04-01",
                "date_to": "2026-04-16",
                "format": "PARQUET",
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "unsupported_export_format"



def test_raw_bi_create_export_rejects_invalid_kind_payload(
    db_session_factory: sessionmaker[Session],
    make_jwt,
) -> None:
    tenant_id = 9119
    client_id = "raw-bi-client-create-invalid-kind"

    with TestClient(app, headers=_client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id)) as api_client:
        response = api_client.post(
            "/api/v1/bi/exports",
            json={
                "kind": "NOT_A_KIND",
                "scope_type": "CLIENT",
                "scope_id": client_id,
                "date_from": "2026-04-01",
                "date_to": "2026-04-17",
                "format": "CSV",
            },
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["message"] == "Validation failed"
    assert any(err["loc"][-1] == "kind" for err in body["error"]["details"])
