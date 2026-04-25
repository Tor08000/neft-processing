from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.operation import ProductType
from ._money_router_harness import (
    ADMIN_BILLING_SUMMARY_TEST_TABLES,
    admin_billing_client_context,
    money_session_context,
)

@pytest.fixture
def session() -> Session:
    with money_session_context(tables=ADMIN_BILLING_SUMMARY_TEST_TABLES) as db:
        yield db


@pytest.fixture
def admin_client(session: Session) -> TestClient:
    with admin_billing_client_context(db_session=session) as api_client:
        yield api_client


def _make_period(billing_date: date) -> BillingPeriod:
    return BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(billing_date, time.min),
        end_at=datetime.combine(billing_date, time.max),
        tz='UTC',
        status=BillingPeriodStatus.OPEN,
    )


def _make_summary(
    *,
    period_id: str,
    billing_date: date,
    client_id: str,
    merchant_id: str,
    product_type: ProductType,
    amount: int,
    quantity: Decimal | None,
    currency: str = 'RUB',
    commission_amount: int = 0,
    operations_count: int = 1,
) -> BillingSummary:
    return BillingSummary(
        billing_date=billing_date,
        billing_period_id=period_id,
        client_id=client_id,
        merchant_id=merchant_id,
        product_type=product_type,
        currency=currency,
        total_amount=amount,
        total_quantity=quantity,
        operations_count=operations_count,
        commission_amount=commission_amount,
        status=BillingSummaryStatus.PENDING,
    )


def test_admin_billing_summary_filters(admin_client: TestClient, session: Session):
    billing_date = date(2024, 5, 20)

    period = _make_period(billing_date)
    session.add(period)
    session.flush()

    summaries = [
        _make_summary(
            period_id=period.id,
            billing_date=billing_date,
            client_id='c-1',
            merchant_id='m-1',
            product_type=ProductType.DIESEL,
            amount=2_000,
            quantity=Decimal('10.000'),
            currency='RUB',
            commission_amount=20,
        ),
        _make_summary(
            period_id=period.id,
            billing_date=billing_date,
            client_id='c-2',
            merchant_id='m-2',
            product_type=ProductType.AI92,
            amount=1_000,
            quantity=None,
            currency='USD',
            commission_amount=10,
        ),
    ]

    session.add_all(summaries)
    session.commit()

    response = admin_client.get(
        '/api/v1/admin/billing/summary',
        params={
            'date_from': billing_date.isoformat(),
            'date_to': billing_date.isoformat(),
            'merchant_id': 'm-1',
            'currency': 'RUB',
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload['total'] == 1
    assert payload['limit'] == 50
    assert payload['offset'] == 0
    assert len(payload['items']) == 1

    item = payload['items'][0]
    assert item['billing_date'] == billing_date.isoformat()
    assert item['merchant_id'] == 'm-1'
    assert item['client_id'] == 'c-1'
    assert item['product_type'] == ProductType.DIESEL.value
    assert item['total_amount'] == 2000
    assert item['total_quantity'] == '10.000'
    assert item['operations_count'] == 1
    assert item['commission_amount'] == 20


def test_admin_billing_summary_pagination(admin_client: TestClient, session: Session):
    billing_date = date(2024, 6, 1)

    period = _make_period(billing_date)
    session.add(period)
    session.flush()

    summaries = []
    for idx in range(3):
        summaries.append(
            _make_summary(
                period_id=period.id,
                billing_date=billing_date + timedelta(days=0),
                client_id=f'client-{idx}',
                merchant_id='merchant-1',
                product_type=ProductType.AI95,
                amount=1_000 + idx * 100,
                quantity=Decimal('1.000'),
                commission_amount=10 + idx,
            )
        )

    session.add_all(summaries)
    session.commit()

    first_page = admin_client.get(
        '/api/v1/admin/billing/summary',
        params={
            'date_from': billing_date.isoformat(),
            'date_to': billing_date.isoformat(),
            'limit': 2,
            'offset': 0,
        },
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload['total'] == 3
    assert len(first_payload['items']) == 2

    second_page = admin_client.get(
        '/api/v1/admin/billing/summary',
        params={
            'date_from': billing_date.isoformat(),
            'date_to': billing_date.isoformat(),
            'limit': 2,
            'offset': 2,
        },
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload['total'] == 3
    assert len(second_payload['items']) == 1
