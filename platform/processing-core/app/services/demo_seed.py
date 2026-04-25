from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobType
from app.models.billing_period import BillingPeriodStatus, BillingPeriodType
from app.models.contract_limits import TariffPlan, TariffPrice
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.models.card import Card
from app.models.client import Client
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.services.billing_job_runs import BillingJobRunService
from app.services.billing_periods import BillingPeriodService
from app.services.billing_run import BillingRunService
from app.services.job_locks import make_stable_key

DEMO_CLIENT_ID = "00000000-0000-0000-0000-00000000b111"
DEMO_MERCHANT_ID = "demo-merchant"
DEMO_TERMINAL_ID = "demo-terminal"
DEMO_CARD_ID = "demo-card"
DEMO_TARIFF_ID = "demo-tariff"


class DemoSeeder:
    """Create deterministic demo data for billing/clearing smoke."""

    def __init__(self, db: Session):
        self.db = db
        self.job_service = BillingJobRunService(db)

    def _ensure_client(self) -> Client:
        client = self.db.query(Client).filter(Client.id == DEMO_CLIENT_ID).first()
        if client:
            return client
        client = Client(
            id=DEMO_CLIENT_ID,
            name="Demo Client",
            external_id="DEMO",
            email="demo@example.com",
            full_name="Demo Client",
            status="ACTIVE",
        )
        self.db.add(client)
        self.db.flush()
        return client

    def _ensure_merchant(self) -> Merchant:
        merchant = self.db.query(Merchant).filter(Merchant.id == DEMO_MERCHANT_ID).first()
        if merchant:
            merchant.status = "ACTIVE"
            return merchant
        merchant = Merchant(id=DEMO_MERCHANT_ID, name="Demo Merchant", status="ACTIVE")
        self.db.add(merchant)
        self.db.flush()
        return merchant

    def _ensure_terminal(self) -> Terminal:
        terminal = self.db.query(Terminal).filter(Terminal.id == DEMO_TERMINAL_ID).first()
        if terminal:
            terminal.status = "ACTIVE"
            terminal.merchant_id = DEMO_MERCHANT_ID
            return terminal
        terminal = Terminal(id=DEMO_TERMINAL_ID, merchant_id=DEMO_MERCHANT_ID, status="ACTIVE", location="Demo")
        self.db.add(terminal)
        self.db.flush()
        return terminal

    def _ensure_card(self) -> Card:
        card = self.db.query(Card).filter(Card.id == DEMO_CARD_ID).first()
        if card:
            card.status = "ACTIVE"
            card.client_id = DEMO_CLIENT_ID
            return card
        card = Card(
            id=DEMO_CARD_ID,
            client_id=DEMO_CLIENT_ID,
            status="ACTIVE",
            pan_masked="************4242",
        )
        self.db.add(card)
        self.db.flush()
        return card

    def _ensure_tariff(self) -> TariffPlan:
        tariff = self.db.query(TariffPlan).filter(TariffPlan.id == DEMO_TARIFF_ID).first()
        if not tariff:
            tariff = TariffPlan(id=DEMO_TARIFF_ID, name="Demo Tariff", params=None)
            self.db.add(tariff)
            self.db.flush()

        price = (
            self.db.query(TariffPrice)
            .filter(TariffPrice.tariff_id == DEMO_TARIFF_ID)
            .filter(TariffPrice.product_id == "FUEL")
            .first()
        )
        if not price:
            price = TariffPrice(
                tariff_id=DEMO_TARIFF_ID,
                product_id="FUEL",
                partner_id=None,
                azs_id=None,
                price_per_liter=1,
                cost_price_per_liter=1,
                currency="RUB",
                priority=100,
            )
            self.db.add(price)
            self.db.flush()
        return tariff

    def _make_operation(
        self,
        *,
        created_at: datetime,
        amount: int,
        product_type: ProductType,
        status: OperationStatus,
        idx: int,
    ) -> Operation:
        ext_id = f"demo-op-{idx}"
        existing = self.db.query(Operation).filter(Operation.ext_operation_id == ext_id).one_or_none()
        if existing:
            return existing
        op = Operation(
            ext_operation_id=ext_id,
            operation_type=OperationType.COMMIT,
            status=status,
            created_at=created_at,
            updated_at=created_at,
            merchant_id=DEMO_MERCHANT_ID,
            terminal_id=DEMO_TERMINAL_ID,
            client_id=DEMO_CLIENT_ID,
            card_id=DEMO_CARD_ID,
            product_id="FUEL",
            product_type=product_type,
            amount=amount,
            amount_settled=amount,
            currency="RUB",
            quantity=1,
            unit_price=amount,
            captured_amount=amount if status in (OperationStatus.CAPTURED, OperationStatus.COMPLETED) else 0,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        )
        self.db.add(op)
        return op

    def _seed_operations(self, billing_date: date) -> list[Operation]:
        base_dt = datetime.combine(billing_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        operations: list[Operation] = []
        amounts = [500, 700, 900, 1100, 1300, 1500]
        statuses = [OperationStatus.CAPTURED, OperationStatus.COMPLETED] * 3
        for idx, (amount, status) in enumerate(zip(amounts, statuses, strict=False), start=1):
            operations.append(
                self._make_operation(
                    created_at=base_dt + timedelta(hours=idx),
                    amount=amount,
                    product_type=ProductType.AI92,
                    status=status,
                    idx=idx,
                )
            )
        self.db.flush()
        return operations

    def _ensure_billing_summaries(
        self,
        billing_date: date,
        operations: Iterable[Operation],
        *,
        billing_period_id: str,
    ) -> list[BillingSummary]:
        summaries: list[BillingSummary] = []
        totals_by_merchant: dict[tuple[str, str], int] = {}
        counts_by_merchant: dict[tuple[str, str], int] = {}
        for op in operations:
            key = (op.merchant_id, op.currency or "RUB")
            totals_by_merchant[key] = totals_by_merchant.get(key, 0) + int(op.amount_settled or op.amount or 0)
            counts_by_merchant[key] = counts_by_merchant.get(key, 0) + 1

        for (merchant_id, currency), total_amount in totals_by_merchant.items():
            existing = (
                self.db.query(BillingSummary)
                .filter(BillingSummary.billing_date == billing_date)
                .filter(BillingSummary.merchant_id == merchant_id)
                .filter(BillingSummary.currency == currency)
                .one_or_none()
            )
            if existing:
                if not existing.billing_period_id:
                    existing.billing_period_id = billing_period_id
                summaries.append(existing)
                continue
            summary = BillingSummary(
                billing_date=billing_date,
                billing_period_id=billing_period_id,
                merchant_id=merchant_id,
                client_id=DEMO_CLIENT_ID,
                product_type=ProductType.AI92,
                currency=currency,
                total_amount=total_amount,
                total_quantity=len(operations),
                operations_count=counts_by_merchant[(merchant_id, currency)],
                commission_amount=0,
                status=BillingSummaryStatus.FINALIZED,
            )
            self.db.add(summary)
            summaries.append(summary)
        self.db.flush()
        return summaries

    def seed(self, billing_date: date | None = None) -> dict[str, Any]:
        target_date = billing_date or date.today() - timedelta(days=1)
        self._ensure_client()
        self._ensure_merchant()
        self._ensure_terminal()
        self._ensure_card()
        self._ensure_tariff()

        operations = self._seed_operations(target_date)
        period_service = BillingPeriodService(self.db)
        start_at = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_at = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        period = period_service.get_or_create(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
        )
        self._ensure_billing_summaries(target_date, operations, billing_period_id=str(period.id))
        self.db.commit()

        scope_key = make_stable_key(
            "billing_seed_run",
            {"date": target_date.isoformat(), "ops": len(operations)},
        )

        # Trigger a billing run to ensure invoices exist for smoke flows.
        billing_service = BillingRunService(self.db)
        seed_token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "demo_seed"}
        result = billing_service.run(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            end_at=datetime.combine(target_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
            tz="UTC",
            client_id=None,
            idempotency_key=scope_key,
            token=seed_token,
        )

        result.billing_period.status = BillingPeriodStatus.FINALIZED
        result.billing_period.finalized_at = datetime.now(timezone.utc)
        self.db.add(result.billing_period)
        self.db.commit()
        return {
            "client_id": DEMO_CLIENT_ID,
            "merchant_id": DEMO_MERCHANT_ID,
            "terminal_id": DEMO_TERMINAL_ID,
            "card_id": DEMO_CARD_ID,
            "billing_period_id": str(result.billing_period.id),
            "period_from": str(result.period_from),
            "period_to": str(result.period_to),
        }
