from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from app.models.billing_period import BillingPeriod, BillingPeriodType
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
from app.models.documents import Document, DocumentType
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
from app.models.invoice import Invoice
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.models.subscriptions_v1 import SubscriptionPlan
from app.services.crm.subscription_billing import run_subscription_billing
from app.services.crm.subscription_pricing_engine import price_subscription
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.states import MoneyFlowType
from app.tests._crm_test_harness import (
    CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES,
    CRM_TEST_HEADERS,
    crm_admin_client_context,
    crm_session_context,
)


def _seed_invoice_thresholds(session) -> None:
    session.add(
        RiskThresholdSet(
            id="invoice-global",
            subject_type=RiskSubjectType.INVOICE,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.INVOICE,
            block_threshold=100,
            review_threshold=90,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    )
    session.commit()


def _seed_subscription_plan(session, *, code: str, title: str) -> None:
    session.add(
        SubscriptionPlan(
            code=code,
            title=title,
            description=f"{title} plan",
            billing_period_months=1,
            price_cents=0,
            discount_percent=0,
            currency="RUB",
        )
    )
    session.commit()


def test_crm_subscription_suspend_resume():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        _seed_subscription_plan(session, code="FUEL_BASIC", title="Fuel Basic")
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_BASIC",
                    "name": "Fuel Basic",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 10000,
                    "currency": "RUB",
                    "features": {"fuel": True},
                },
                headers=CRM_TEST_HEADERS,
            )
            created = client.post(
                "/api/core/v1/admin/crm/clients/client-1/subscriptions",
                json={
                    "tenant_id": 1,
                    "tariff_plan_id": "FUEL_BASIC",
                    "status": "ACTIVE",
                    "billing_cycle": "MONTHLY",
                    "billing_day": 1,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
                headers=CRM_TEST_HEADERS,
            )
            subscription_id = created.json()["id"]
            suspend = client.post(
                f"/api/core/v1/admin/crm/subscriptions/{subscription_id}/suspend",
                headers=CRM_TEST_HEADERS,
            )
            assert suspend.status_code == 200
            assert suspend.json()["status"] == "PAUSED"

            resume = client.post(
                f"/api/core/v1/admin/crm/subscriptions/{subscription_id}/resume",
                headers=CRM_TEST_HEADERS,
            )
            assert resume.status_code == 200
            assert resume.json()["status"] == "ACTIVE"


def test_subscription_billing_creates_invoice_and_documents():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        _seed_subscription_plan(session, code="FUEL_BASIC", title="Fuel Basic")
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/tariffs",
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
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/clients/client-1/subscriptions",
                json={
                    "tenant_id": 1,
                    "tariff_plan_id": "FUEL_BASIC",
                    "status": "ACTIVE",
                    "billing_cycle": "MONTHLY",
                    "billing_day": 1,
                    "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                },
                headers=CRM_TEST_HEADERS,
            )

        _seed_invoice_thresholds(session)
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


def test_subscription_billing_persists_merged_document_storage_fields():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        document_columns = {
            row["name"] for row in session.execute(text("PRAGMA table_info(documents)")).mappings()
        }
        assert {"direction", "title", "sender_type"}.issubset(document_columns)

        _seed_subscription_plan(session, code="FUEL_PRO", title="Fuel Pro")
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_PRO",
                    "name": "Fuel Pro",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 125000,
                    "currency": "RUB",
                    "definition": {
                        "base_fee": {"amount_minor": 125000, "currency": "RUB"},
                        "billing_cycle": "MONTHLY",
                        "included": {"cards": 0, "vehicles": 0, "drivers": 0, "fuel_tx": 0, "logistics_orders": 0},
                        "features": {"fuel": True},
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            created = client.post(
                "/api/core/v1/admin/crm/clients/client-1/subscriptions",
                json={
                    "tenant_id": 1,
                    "tariff_plan_id": "FUEL_PRO",
                    "status": "ACTIVE",
                    "billing_cycle": "MONTHLY",
                    "billing_day": 1,
                    "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                },
                headers=CRM_TEST_HEADERS,
            )
            subscription_id = created.json()["id"]

        _seed_invoice_thresholds(session)
        period = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
            tz="UTC",
        )
        session.add(period)
        session.commit()

        run_subscription_billing(session, billing_period_id=str(period.id))

        invoice = session.query(Invoice).filter(Invoice.client_id == "client-1").one()
        persisted_rows = session.execute(
            text(
                """
                SELECT
                    document_type,
                    direction,
                    title,
                    sender_type,
                    source_entity_type,
                    source_entity_id,
                    generated_at,
                    number
                FROM documents
                WHERE client_id = :client_id
                  AND period_from = :period_from
                  AND period_to = :period_to
                """
            ),
            {
                "client_id": "client-1",
                "period_from": datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
                "period_to": datetime(2025, 1, 31, tzinfo=timezone.utc).date(),
            },
        ).mappings()
        documents_by_type = {row["document_type"]: row for row in persisted_rows}

        assert set(documents_by_type) == {
            DocumentType.SUBSCRIPTION_INVOICE.value,
            DocumentType.SUBSCRIPTION_ACT.value,
        }

        invoice_row = documents_by_type[DocumentType.SUBSCRIPTION_INVOICE.value]
        assert invoice_row["direction"] == "OUTBOUND"
        assert invoice_row["title"] == "Subscription invoice"
        assert invoice_row["sender_type"] == "NEFT"
        assert invoice_row["source_entity_type"] == "invoice"
        assert invoice_row["source_entity_id"] == invoice.id
        assert invoice_row["number"] == invoice.number
        assert invoice_row["generated_at"] is not None

        act_row = documents_by_type[DocumentType.SUBSCRIPTION_ACT.value]
        assert act_row["direction"] == "OUTBOUND"
        assert act_row["title"] == "Subscription act"
        assert act_row["sender_type"] == "NEFT"
        assert act_row["source_entity_type"] == "subscription"
        assert act_row["source_entity_id"] == subscription_id
        assert act_row["number"] is None
        assert act_row["generated_at"] is not None


def test_subscription_billing_registers_legal_graph_and_money_flow_artifacts():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        _seed_subscription_plan(session, code="FUEL_ENTERPRISE", title="Fuel Enterprise")
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_ENTERPRISE",
                    "name": "Fuel Enterprise",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 225000,
                    "currency": "RUB",
                    "definition": {
                        "base_fee": {"amount_minor": 225000, "currency": "RUB"},
                        "billing_cycle": "MONTHLY",
                        "included": {"cards": 0, "vehicles": 0, "drivers": 0, "fuel_tx": 0, "logistics_orders": 0},
                        "features": {"fuel": True},
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            created = client.post(
                "/api/core/v1/admin/crm/clients/client-1/subscriptions",
                json={
                    "tenant_id": 1,
                    "tariff_plan_id": "FUEL_ENTERPRISE",
                    "status": "ACTIVE",
                    "billing_cycle": "MONTHLY",
                    "billing_day": 1,
                    "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                },
                headers=CRM_TEST_HEADERS,
            )
            subscription_id = created.json()["id"]

        _seed_invoice_thresholds(session)
        period = BillingPeriod(
            period_type=BillingPeriodType.MONTHLY,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
            tz="UTC",
        )
        session.add(period)
        session.commit()

        run_subscription_billing(session, billing_period_id=str(period.id))

        invoice = session.query(Invoice).filter(Invoice.client_id == "client-1").one()
        documents = {
            doc.document_type.value: doc
            for doc in session.query(Document).filter(Document.client_id == "client-1").all()
        }
        invoice_doc = documents[DocumentType.SUBSCRIPTION_INVOICE.value]
        act_doc = documents[DocumentType.SUBSCRIPTION_ACT.value]

        legal_nodes = {
            (node.node_type.value, node.ref_id): node
            for node in session.query(LegalNode).filter(LegalNode.tenant_id == 1).all()
        }
        subscription_node = legal_nodes[(LegalNodeType.SUBSCRIPTION.value, subscription_id)]
        invoice_node = legal_nodes[(LegalNodeType.INVOICE.value, invoice.id)]
        billing_node = legal_nodes[(LegalNodeType.BILLING_PERIOD.value, str(period.id))]
        invoice_doc_node = legal_nodes[(LegalNodeType.DOCUMENT.value, str(invoice_doc.id))]
        act_doc_node = legal_nodes[(LegalNodeType.DOCUMENT.value, str(act_doc.id))]

        assert subscription_node.ref_table == "crm_subscriptions"
        assert invoice_node.ref_table == "invoices"
        assert billing_node.ref_table == "billing_periods"
        assert invoice_doc_node.ref_table == "documents"
        assert act_doc_node.ref_table == "documents"

        legal_edges = {
            (edge.edge_type.value, edge.src_node_id, edge.dst_node_id)
            for edge in session.query(LegalEdge).filter(LegalEdge.tenant_id == 1).all()
        }
        assert (
            LegalEdgeType.GENERATED_FROM.value,
            subscription_node.id,
            invoice_node.id,
        ) in legal_edges
        assert (
            LegalEdgeType.INCLUDES.value,
            invoice_doc_node.id,
            billing_node.id,
        ) in legal_edges
        assert (
            LegalEdgeType.INCLUDES.value,
            act_doc_node.id,
            billing_node.id,
        ) in legal_edges

        money_event = (
            session.query(MoneyFlowEvent)
            .filter(MoneyFlowEvent.flow_ref_id == invoice.id)
            .filter(MoneyFlowEvent.flow_type == MoneyFlowType.SUBSCRIPTION_CHARGE)
            .one()
        )
        assert money_event.event_type == MoneyFlowEventType.AUTHORIZE

        money_links = {
            (link.src_type.value, link.src_id, link.link_type.value, link.dst_type.value, link.dst_id): link
            for link in session.query(MoneyFlowLink).filter(MoneyFlowLink.tenant_id == 1).all()
        }
        assert (
            MoneyFlowLinkNodeType.SUBSCRIPTION.value,
            subscription_id,
            MoneyFlowLinkType.RELATES.value,
            MoneyFlowLinkNodeType.BILLING_PERIOD.value,
            str(period.id),
        ) in money_links
        assert (
            MoneyFlowLinkNodeType.SUBSCRIPTION.value,
            subscription_id,
            MoneyFlowLinkType.GENERATES.value,
            MoneyFlowLinkNodeType.INVOICE.value,
            invoice.id,
        ) in money_links

        invoice_doc_link = money_links[
            (
                MoneyFlowLinkNodeType.INVOICE.value,
                invoice.id,
                MoneyFlowLinkType.GENERATES.value,
                MoneyFlowLinkNodeType.DOCUMENT.value,
                str(invoice_doc.id),
            )
        ]
        assert invoice_doc_link.meta["document_type"] == DocumentType.SUBSCRIPTION_INVOICE.value

        act_doc_link = money_links[
            (
                MoneyFlowLinkNodeType.INVOICE.value,
                invoice.id,
                MoneyFlowLinkType.GENERATES.value,
                MoneyFlowLinkNodeType.DOCUMENT.value,
                str(act_doc.id),
            )
        ]
        assert act_doc_link.meta["document_type"] == DocumentType.SUBSCRIPTION_ACT.value


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


def test_invoice_idempotent():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        _seed_subscription_plan(session, code="FUEL_START", title="Fuel Start")
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_START",
                    "name": "Fuel Start",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 990000,
                    "currency": "RUB",
                    "definition": {"base_fee": {"amount_minor": 990000, "currency": "RUB"}},
                },
                headers=CRM_TEST_HEADERS,
            )
            client.post(
                "/api/core/v1/admin/crm/clients/client-1/subscriptions",
                json={
                    "tenant_id": 1,
                    "tariff_plan_id": "FUEL_START",
                    "status": "ACTIVE",
                    "billing_cycle": "MONTHLY",
                    "billing_day": 1,
                    "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                },
                headers=CRM_TEST_HEADERS,
            )

        _seed_invoice_thresholds(session)
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


def test_subscription_fuel_usage_optional_feature_flag():
    with crm_session_context(tables=CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES) as session:
        _seed_invoice_thresholds(session)
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
        feb_invoice = session.query(Invoice).filter(Invoice.billing_period_id == str(period_feb.id)).one()
        assert int(feb_invoice.total_with_tax or 0) > 0


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
