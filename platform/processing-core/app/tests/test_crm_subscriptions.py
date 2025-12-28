from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.documents import Document, DocumentType
from app.models.invoice import Invoice
from app.models.crm import (
    CRMBillingCycle,
    CRMBillingPeriod,
    CRMClient,
    CRMClientStatus,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMSubscription,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
    CRMUsageCounter,
    CRMUsageMetric,
)
from app.services.crm.subscription_billing import run_subscription_billing
from app.services.crm.subscription_pricing_engine import price_subscription
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
)


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_crm_subscription_suspend_resume(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    client.post(
        "/api/v1/admin/crm/tariffs",
        json={
            "id": "FUEL_BASIC",
            "name": "Fuel Basic",
            "status": "ACTIVE",
            "billing_period": "MONTHLY",
            "base_fee_minor": 10000,
            "currency": "RUB",
            "features": {"fuel": True},
        },
        headers=admin_auth_headers,
    )
    created = client.post(
        "/api/v1/admin/crm/clients/client-1/subscriptions",
        json={
            "tenant_id": 1,
            "tariff_plan_id": "FUEL_BASIC",
            "status": "ACTIVE",
            "billing_cycle": "MONTHLY",
            "billing_day": 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=admin_auth_headers,
    )
    subscription_id = created.json()["id"]
    suspend = client.post(
        f"/api/v1/admin/crm/subscriptions/{subscription_id}/suspend",
        headers=admin_auth_headers,
    )
    assert suspend.status_code == 200
    assert suspend.json()["status"] == "PAUSED"

    resume = client.post(
        f"/api/v1/admin/crm/subscriptions/{subscription_id}/resume",
        headers=admin_auth_headers,
    )
    assert resume.status_code == 200
    assert resume.json()["status"] == "ACTIVE"


def test_subscription_billing_creates_invoice_and_documents(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    client.post(
        "/api/v1/admin/crm/tariffs",
        json={
            "id": "FUEL_BASIC",
            "name": "Fuel Basic",
            "status": "ACTIVE",
            "billing_period": "MONTHLY",
            "base_fee_minor": 500000,
            "currency": "RUB",
            "definition": {
                "base_fee": {"amount_minor": 500000, "currency": "RUB"},
                "billing_cycle": "MONTHLY",
                "included": {"cards": 0, "vehicles": 0, "drivers": 0, "fuel_tx": 0, "logistics_orders": 0},
                "overage": {"fuel_tx": {"unit_price_minor": 50}},
                "features": {"fuel": True},
            },
        },
        headers=admin_auth_headers,
    )
    client.post(
        "/api/v1/admin/crm/clients/client-1/subscriptions",
        json={
            "tenant_id": 1,
            "tariff_plan_id": "FUEL_BASIC",
            "status": "ACTIVE",
            "billing_cycle": "MONTHLY",
            "billing_day": 1,
            "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        },
        headers=admin_auth_headers,
    )

    session = SessionLocal()
    try:
        period = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
            tz="UTC",
        )
        session.add(period)
        session.commit()
        run_subscription_billing(session, billing_period_id=str(period.id))
        invoice = session.query(Invoice).filter(Invoice.client_id == "client-1").one_or_none()
        assert invoice is not None
        docs = session.query(Document).filter(Document.client_id == "client-1").all()
        assert any(doc.document_type == DocumentType.SUBSCRIPTION_INVOICE for doc in docs)
        assert any(doc.document_type == DocumentType.SUBSCRIPTION_ACT for doc in docs)
    finally:
        session.close()


def test_pricing_engine_overage_and_base_fee():
    subscription = CRMSubscription(
        id="sub-1",
        tenant_id=1,
        client_id="client-1",
        tariff_plan_id="FUEL_START",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    counters = [
        CRMUsageCounter(
            subscription_id="sub-1",
            billing_period_id="period-1",
            metric=CRMUsageMetric.CARDS_COUNT,
            value=15,
            limit_value=None,
        ),
        CRMUsageCounter(
            subscription_id="sub-1",
            billing_period_id="period-1",
            metric=CRMUsageMetric.FUEL_TX_COUNT,
            value=350,
            limit_value=None,
        ),
    ]
    tariff_definition = {
        "base_fee": {"amount_minor": 990000, "currency": "RUB"},
        "included": {"cards": 10, "fuel_tx": 300},
        "overage": {"cards": {"unit_price_minor": 15000}, "fuel_tx": {"unit_price_minor": 120}},
    }
    result = price_subscription(
        subscription=subscription,
        billing_period_id="period-1",
        counters=counters,
        tariff_definition=tariff_definition,
    )
    amounts = {charge.code: charge.amount for charge in result.charges}
    assert amounts["BASE_FEE"] == 990000
    assert amounts["OVERAGE_CARDS_COUNT"] == 5 * 15000
    assert amounts["OVERAGE_FUEL_TX_COUNT"] == 50 * 120
    assert counters[0].overage == 5
    assert counters[1].overage == 50


def test_invoice_idempotent(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    client.post(
        "/api/v1/admin/crm/tariffs",
        json={
            "id": "FUEL_START",
            "name": "Fuel Start",
            "status": "ACTIVE",
            "billing_period": "MONTHLY",
            "base_fee_minor": 990000,
            "currency": "RUB",
            "definition": {"base_fee": {"amount_minor": 990000, "currency": "RUB"}},
        },
        headers=admin_auth_headers,
    )
    client.post(
        "/api/v1/admin/crm/clients/client-1/subscriptions",
        json={
            "tenant_id": 1,
            "tariff_plan_id": "FUEL_START",
            "status": "ACTIVE",
            "billing_cycle": "MONTHLY",
            "billing_day": 1,
            "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        },
        headers=admin_auth_headers,
    )

    session = SessionLocal()
    try:
        period = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
            tz="UTC",
        )
        session.add(period)
        session.commit()
        run_subscription_billing(session, billing_period_id=str(period.id))
        run_subscription_billing(session, billing_period_id=str(period.id))
        invoices = session.query(Invoice).filter(Invoice.client_id == "client-1").all()
        assert len(invoices) == 1
    finally:
        session.close()


def test_subscription_fuel_usage_optional_feature_flag():
    session = SessionLocal()
    try:
        session.add(
            CRMClient(
                id="client-1",
                tenant_id=1,
                legal_name="Client",
                country="RU",
                status=CRMClientStatus.ACTIVE,
            )
        )
        session.add(
            CRMTariffPlan(
                id="FUEL_TARIFF",
                name="Fuel Tariff",
                status=CRMTariffStatus.ACTIVE,
                billing_period=CRMBillingPeriod.MONTHLY,
                base_fee_minor=0,
                currency="RUB",
                definition={
                    "base_fee": {"amount_minor": 0, "currency": "RUB"},
                    "included": {"fuel_tx": 0},
                    "overage": {"fuel_tx": {"unit_price_minor": 100}},
                },
            )
        )
        subscription = CRMSubscription(
            tenant_id=1,
            client_id="client-1",
            tariff_plan_id="FUEL_TARIFF",
            status=CRMSubscriptionStatus.ACTIVE,
            billing_cycle=CRMBillingCycle.MONTHLY,
            billing_day=1,
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        session.add(subscription)

        network = FuelNetwork(id=str(uuid4()), name="Net", provider_code="NET", status=FuelNetworkStatus.ACTIVE)
        station = FuelStation(
            network_id=network.id,
            station_network_id=None,
            station_code="ST-1",
            name="Station",
            country="RU",
            region="RU",
            city="SPB",
            lat="0",
            lon="0",
            status=FuelStationStatus.ACTIVE,
        )
        card = FuelCard(
            id=str(uuid4()),
            tenant_id=1,
            client_id="client-1",
            card_token="card-1",
            status=FuelCardStatus.ACTIVE,
        )
        session.add_all([network, station, card])
        session.commit()

        period_jan = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
            tz="UTC",
        )
        period_feb = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 2, 28, tzinfo=timezone.utc),
            tz="UTC",
        )
        session.add_all([period_jan, period_feb])
        session.commit()

        session.add_all(
            [
                FuelTransaction(
                    tenant_id=1,
                    client_id="client-1",
                    card_id=card.id,
                    station_id=station.id,
                    network_id=network.id,
                    occurred_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
                    fuel_type="DIESEL",
                    volume_ml=10000,
                    unit_price_minor=500,
                    amount_total_minor=5000,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                ),
                FuelTransaction(
                    tenant_id=1,
                    client_id="client-1",
                    card_id=card.id,
                    station_id=station.id,
                    network_id=network.id,
                    occurred_at=datetime(2025, 2, 15, tzinfo=timezone.utc),
                    fuel_type="DIESEL",
                    volume_ml=10000,
                    unit_price_minor=500,
                    amount_total_minor=5000,
                    currency="RUB",
                    status=FuelTransactionStatus.SETTLED,
                ),
            ]
        )
        session.add(
            CRMFeatureFlag(
                tenant_id=1,
                client_id="client-1",
                feature=CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED,
                enabled=False,
            )
        )
        session.commit()

        run_subscription_billing(session, billing_period_id=str(period_jan.id))
        jan_counters = (
            session.query(CRMUsageCounter)
            .filter(CRMUsageCounter.subscription_id == subscription.id)
            .filter(CRMUsageCounter.billing_period_id == str(period_jan.id))
            .all()
        )
        assert all(counter.metric != CRMUsageMetric.FUEL_TX_COUNT for counter in jan_counters)

        flag = (
            session.query(CRMFeatureFlag)
            .filter(CRMFeatureFlag.client_id == "client-1")
            .filter(CRMFeatureFlag.feature == CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED)
            .one()
        )
        flag.enabled = True
        session.add(flag)
        session.commit()

        run_subscription_billing(session, billing_period_id=str(period_feb.id))
        feb_counters = (
            session.query(CRMUsageCounter)
            .filter(CRMUsageCounter.subscription_id == subscription.id)
            .filter(CRMUsageCounter.billing_period_id == str(period_feb.id))
            .all()
        )
        assert any(counter.metric == CRMUsageMetric.FUEL_TX_COUNT for counter in feb_counters)
        feb_invoice = (
            session.query(Invoice)
            .filter(Invoice.billing_period_id == str(period_feb.id))
            .one()
        )
        assert int(feb_invoice.total_with_tax or 0) > 0
    finally:
        session.close()


def test_pricing_engine_proration_segments():
    subscription = CRMSubscription(
        id="sub-2",
        tenant_id=1,
        client_id="client-2",
        tariff_plan_id="FUEL_BASIC",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    period_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2025, 1, 30, 23, 59, 59, tzinfo=timezone.utc)
    segments = [
        CRMSubscriptionPeriodSegment(
            subscription_id="sub-2",
            billing_period_id="period-2",
            tariff_plan_id="FUEL_BASIC",
            segment_start=period_start,
            segment_end=datetime(2025, 1, 10, 23, 59, 59, tzinfo=timezone.utc),
            status=CRMSubscriptionSegmentStatus.ACTIVE,
            days_count=10,
        )
    ]
    tariff_definition = {"base_fee": {"amount_minor": 3000, "currency": "RUB"}}
    result = price_subscription(
        subscription=subscription,
        billing_period_id="period-2",
        counters=[],
        tariff_definition=tariff_definition,
        segments=segments,
        period_start=period_start,
        period_end=period_end,
    )
    assert result.charges[0].amount == 1000


def test_pricing_engine_metric_rules():
    subscription = CRMSubscription(
        id="sub-3",
        tenant_id=1,
        client_id="client-3",
        tariff_plan_id="FUEL_VOLUME",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    counters = [
        CRMUsageCounter(
            subscription_id="sub-3",
            billing_period_id="period-3",
            metric=CRMUsageMetric.FUEL_VOLUME,
            value=1550,
            limit_value=None,
        )
    ]
    tariff_definition = {
        "included": {"fuel_volume": 1},
        "overage": {"fuel_volume": {"unit_price_minor": 10}},
        "metric_rules": {"FUEL_VOLUME": {"divisor": 1000, "rounding": "ceil"}},
    }
    result = price_subscription(
        subscription=subscription,
        billing_period_id="period-3",
        counters=counters,
        tariff_definition=tariff_definition,
    )
    assert result.charges[0].amount == 10
    assert counters[0].overage == 1
