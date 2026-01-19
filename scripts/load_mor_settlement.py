from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import models  # noqa: F401
from app.db import Base
from app.models.marketplace_catalog import (
    MarketplaceProduct,
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
    MarketplaceProductType,
)
from app.models.marketplace_commissions import (
    MarketplaceCommissionRule,
    MarketplaceCommissionScope,
    MarketplaceCommissionStatus,
    MarketplaceCommissionType,
)
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderActorType
from app.models.marketplace_settlement import MarketplaceSettlementSnapshot
from app.models.partner_finance import PartnerAccount, PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalProfile, PartnerLegalStatus, PartnerLegalType
from app.models.platform_revenue import PlatformRevenueEntry
from app.services.marketplace_order_service import MarketplaceOrderService
from app.services.marketplace_settlement_service import MarketplaceSettlementService, PayoutBlockedError


@dataclass
class LoadResult:
    orders: int
    duration_seconds: float
    payout_duration_seconds: float
    settlement_snapshot_total: Decimal
    ledger_total: Decimal
    revenue_total: Decimal
    payout_amount: Decimal
    payout_blocked: bool
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "orders": self.orders,
            "duration_seconds": round(self.duration_seconds, 3),
            "payout_duration_seconds": round(self.payout_duration_seconds, 3),
            "settlement_snapshot_total": str(self.settlement_snapshot_total),
            "ledger_total": str(self.ledger_total),
            "revenue_total": str(self.revenue_total),
            "payout_amount": str(self.payout_amount),
            "payout_blocked": self.payout_blocked,
            "errors": self.errors,
        }


def _make_engine() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _seed_partner_legal(db: Session, partner_id: str) -> None:
    profile = PartnerLegalProfile(
        partner_id=partner_id,
        legal_status=PartnerLegalStatus.VERIFIED,
        legal_type=PartnerLegalType.LEGAL_ENTITY,
    )
    details = PartnerLegalDetails(
        partner_id=partner_id,
        legal_name="Load Test LLC",
        inn="7700000000",
        kpp="770001001",
        ogrn="1027700000000",
        bank_account="40702810900000000001",
        bank_bic="044525225",
        bank_name="Load Test Bank",
    )
    db.add_all([profile, details])


def _create_product_and_commission(db: Session, partner_id: str) -> MarketplaceProduct:
    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=partner_id,
        type=MarketplaceProductType.SERVICE.value,
        title="MoR load test product",
        description="Load test service",
        category="load-test",
        price_model="FIXED",
        price_config={"amount": "100", "currency": "RUB"},
        status=MarketplaceProductStatus.PUBLISHED.value,
        moderation_status=MarketplaceProductModerationStatus.APPROVED.value,
    )
    db.add(product)
    db.flush()

    commission_rule = MarketplaceCommissionRule(
        id=str(uuid4()),
        scope=MarketplaceCommissionScope.MARKETPLACE.value,
        partner_id=partner_id,
        product_category="load-test",
        commission_type=MarketplaceCommissionType.FIXED.value,
        amount=Decimal("15"),
        priority=100,
        status=MarketplaceCommissionStatus.ACTIVE.value,
    )
    db.add(commission_rule)
    return product


def _create_orders(db: Session, *, partner_id: str, client_id: str, product_id: str, count: int) -> None:
    order_service = MarketplaceOrderService(db)
    batch_size = 250
    for index in range(1, count + 1):
        order = order_service.create_order(
            client_id=client_id,
            product_id=product_id,
            quantity=Decimal("1"),
            actor=MarketplaceOrderActorType.SYSTEM,
        )
        order_service.accept_order(
            partner_id=partner_id,
            order_id=str(order.id),
            note=None,
            actor=MarketplaceOrderActorType.SYSTEM,
        )
        order_service.start_order(
            partner_id=partner_id,
            order_id=str(order.id),
            note=None,
            actor=MarketplaceOrderActorType.SYSTEM,
        )
        order_service.complete_order(
            partner_id=partner_id,
            order_id=str(order.id),
            summary="load test",
            actor=MarketplaceOrderActorType.SYSTEM,
        )
        if index % batch_size == 0:
            db.commit()
    db.commit()


def _sum_decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))


def run_load(count: int) -> LoadResult:
    SessionLocal = _make_engine()
    db = SessionLocal()
    errors: list[str] = []
    payout_blocked = False
    payout_duration = 0.0
    try:
        partner_id = str(uuid4())
        client_id = str(uuid4())
        _seed_partner_legal(db, partner_id)
        product = _create_product_and_commission(db, partner_id)
        db.commit()

        start = time.perf_counter()
        _create_orders(db, partner_id=partner_id, client_id=client_id, product_id=str(product.id), count=count)
        duration = time.perf_counter() - start

        period = datetime.now(timezone.utc).strftime("%Y-%m")
        settlement_service = MarketplaceSettlementService(db)
        payout_start = time.perf_counter()
        payout_amount = Decimal("0")
        try:
            result = settlement_service.build_payout_batch(tenant_id=1, partner_id=partner_id, period=period)
            db.commit()
            payout_amount = Decimal(str(result.batch.total_amount or 0))
        except PayoutBlockedError:
            payout_blocked = True
        payout_duration = time.perf_counter() - payout_start

        snapshot_total = _sum_decimal(
            db.query(func.coalesce(func.sum(MarketplaceSettlementSnapshot.partner_net), 0))
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceSettlementSnapshot.order_id)
            .filter(MarketplaceOrder.partner_id == partner_id)
            .scalar()
        )
        fee_total = _sum_decimal(
            db.query(func.coalesce(func.sum(MarketplaceSettlementSnapshot.platform_fee), 0))
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceSettlementSnapshot.order_id)
            .filter(MarketplaceOrder.partner_id == partner_id)
            .scalar()
        )
        ledger_total = _sum_decimal(
            db.query(func.coalesce(func.sum(PartnerLedgerEntry.amount), 0))
            .filter(PartnerLedgerEntry.partner_org_id == partner_id)
            .filter(PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.EARNED)
            .scalar()
        )
        revenue_total = _sum_decimal(
            db.query(func.coalesce(func.sum(PlatformRevenueEntry.amount), 0))
            .join(MarketplaceOrder, MarketplaceOrder.id == PlatformRevenueEntry.order_id)
            .filter(MarketplaceOrder.partner_id == partner_id)
            .scalar()
        )

        account = db.query(PartnerAccount).filter_by(org_id=partner_id).one_or_none()
        account_balance = Decimal(str(account.balance_available or 0)) if account else Decimal("0")

        if snapshot_total != ledger_total:
            errors.append("ledger_drift")
        if fee_total != revenue_total:
            errors.append("revenue_drift")
        if payout_amount and snapshot_total != payout_amount:
            errors.append("payout_mismatch")
        if payout_blocked:
            errors.append("payout_blocked")
        if account_balance < 0:
            errors.append("negative_balance")

        payout_replay_error = False
        try:
            settlement_service.build_payout_batch(tenant_id=1, partner_id=partner_id, period=period)
            payout_replay_error = True
        except ValueError as exc:
            if str(exc) != "no_open_settlement_items":
                payout_replay_error = True
        if payout_replay_error:
            errors.append("double_payout_possible")

        return LoadResult(
            orders=count,
            duration_seconds=duration,
            payout_duration_seconds=payout_duration,
            settlement_snapshot_total=snapshot_total,
            ledger_total=ledger_total,
            revenue_total=revenue_total,
            payout_amount=payout_amount,
            payout_blocked=payout_blocked,
            errors=errors,
        )
    finally:
        db.close()


def _write_report(path: Path, results: list[LoadResult]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [result.to_dict() for result in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="MoR settlement load test runner")
    parser.add_argument("--orders", type=int, help="Number of orders to create per run")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/load_mor_settlement.json"),
        help="Where to write the JSON report",
    )
    args = parser.parse_args()

    order_counts = [args.orders] if args.orders else [1_000, 5_000, 10_000]
    results = [run_load(count) for count in order_counts]
    _write_report(args.output, results)

    print("MoR settlement load test report")
    for result in results:
        print(
            f"orders={result.orders} duration={result.duration_seconds:.2f}s "
            f"payout={result.payout_duration_seconds:.2f}s errors={','.join(result.errors) or 'none'}"
        )
    print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
