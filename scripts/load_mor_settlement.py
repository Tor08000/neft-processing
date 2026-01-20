from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import case, create_engine, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.db import Base
from app.models.audit_log import AuditLog
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
from app.models.marketplace_settlement import (
    MarketplaceSettlementItem,
    MarketplaceSettlementSnapshot,
    MarketplaceSettlementStatus,
)
from app.models.partner_finance import PartnerAccount, PartnerLedgerDirection, PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalProfile, PartnerLegalStatus, PartnerLegalType
from app.models.payout_batch import PayoutBatch
from app.models.platform_revenue import PlatformRevenueEntry
from app.services.marketplace_order_service import MarketplaceOrderService
from app.services.marketplace_settlement_service import MarketplaceSettlementService, PayoutBlockedError
from app.services.partner_finance_service import PartnerFinanceService


@dataclass
class PartnerResult:
    partner_id: str
    currency: str
    orders: int
    settlement_snapshot_total: Decimal
    ledger_total: Decimal
    revenue_total: Decimal
    payout_total: Decimal
    payout_blocked: bool
    payout_blocked_reasons: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "partner_id": self.partner_id,
            "currency": self.currency,
            "orders": self.orders,
            "settlement_snapshot_total": str(self.settlement_snapshot_total),
            "ledger_total": str(self.ledger_total),
            "revenue_total": str(self.revenue_total),
            "payout_total": str(self.payout_total),
            "payout_blocked": self.payout_blocked,
            "payout_blocked_reasons": self.payout_blocked_reasons,
            "errors": self.errors,
        }


@dataclass
class LoadResult:
    run_id: int
    orders: int
    partners: int
    payout_batches_target: int
    payout_batches_built: int
    duration_seconds: float
    payout_duration_seconds: float
    settlement_snapshot_total: Decimal
    ledger_total: Decimal
    revenue_total: Decimal
    payout_total: Decimal
    payout_blocked_total: int
    payout_blocked_reasons: dict[str, int]
    max_payout_batch_operations: int
    max_payout_batch_total_amount: Decimal
    partners_with_errors: int
    error_rate: float
    error_totals: dict[str, int]
    negative_balance_total: int
    payout_without_finalize_total: int
    settlement_immutable_violation_total: int
    partner_results: list[PartnerResult]

    def to_dict(self, *, include_partners: bool) -> dict[str, object]:
        payload = {
            "run_id": self.run_id,
            "orders": self.orders,
            "partners": self.partners,
            "payout_batches_target": self.payout_batches_target,
            "payout_batches_built": self.payout_batches_built,
            "duration_seconds": round(self.duration_seconds, 3),
            "payout_duration_seconds": round(self.payout_duration_seconds, 3),
            "settlement_snapshot_total": str(self.settlement_snapshot_total),
            "ledger_total": str(self.ledger_total),
            "revenue_total": str(self.revenue_total),
            "payout_total": str(self.payout_total),
            "payout_blocked_total": self.payout_blocked_total,
            "payout_blocked_reasons": self.payout_blocked_reasons,
            "max_payout_batch_operations": self.max_payout_batch_operations,
            "max_payout_batch_total_amount": str(self.max_payout_batch_total_amount),
            "partners_with_errors": self.partners_with_errors,
            "error_rate": round(self.error_rate, 4),
            "error_totals": self.error_totals,
            "negative_balance_total": self.negative_balance_total,
            "payout_without_finalize_total": self.payout_without_finalize_total,
            "settlement_immutable_violation_total": self.settlement_immutable_violation_total,
        }
        if include_partners:
            payload["partners"] = [partner.to_dict() for partner in self.partner_results]
        return payload


@dataclass
class PartnerSeed:
    partner_id: str
    client_id: str
    product_id: str
    currency: str


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


def _create_product_and_commission(db: Session, partner_id: str, currency: str) -> MarketplaceProduct:
    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=partner_id,
        type=MarketplaceProductType.SERVICE.value,
        title=f"MoR load test product ({currency})",
        description="Load test service",
        category="load-test",
        price_model="FIXED",
        price_config={"amount": "100", "currency": currency},
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


def _create_orders(db: Session, *, partner_id: str, client_id: str, product_id: str, count: int) -> list[str]:
    order_service = MarketplaceOrderService(db)
    batch_size = 250
    order_ids: list[str] = []
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
        order_ids.append(str(order.id))
        if index % batch_size == 0:
            db.commit()
    db.commit()
    return order_ids


def _sum_decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _ledger_total(db: Session, partner_id: str) -> Decimal:
    amount_case = case(
        (PartnerLedgerEntry.direction == PartnerLedgerDirection.CREDIT, PartnerLedgerEntry.amount),
        else_=-PartnerLedgerEntry.amount,
    )
    return _sum_decimal(
        db.query(func.coalesce(func.sum(amount_case), 0))
        .filter(PartnerLedgerEntry.partner_org_id == partner_id)
        .filter(
            PartnerLedgerEntry.entry_type.in_(
                [PartnerLedgerEntryType.EARNED, PartnerLedgerEntryType.SLA_PENALTY, PartnerLedgerEntryType.ADJUSTMENT]
            )
        )
        .scalar()
    )


def _payout_total(db: Session, partner_id: str) -> Decimal:
    return _sum_decimal(
        db.query(func.coalesce(func.sum(PayoutBatch.total_amount), 0))
        .filter(PayoutBatch.partner_id == partner_id)
        .scalar()
    )


def run_load(
    *,
    run_id: int,
    orders_total: int,
    partners_total: int,
    payout_batches_target: int,
    penalty_rate: float,
    penalty_amount: Decimal,
    mixed_currencies: bool,
) -> LoadResult:
    SessionLocal = _make_engine()
    db = SessionLocal()
    partner_results: list[PartnerResult] = []
    payout_blocked_reasons: dict[str, int] = {}
    payout_blocked_by_partner: dict[str, list[str]] = {}
    partner_errors: dict[str, list[str]] = {}
    payout_batches_built = 0
    payout_duration = 0.0
    max_payout_batch_operations = 0
    max_payout_batch_total_amount = Decimal("0")
    try:
        currency_pool = ["RUB", "USD", "EUR"] if mixed_currencies else ["RUB"]
        partner_seeds: list[PartnerSeed] = []
        for index in range(partners_total):
            partner_id = str(uuid4())
            client_id = str(uuid4())
            currency = currency_pool[index % len(currency_pool)]
            _seed_partner_legal(db, partner_id)
            product = _create_product_and_commission(db, partner_id, currency)
            partner_seeds.append(
                PartnerSeed(partner_id=partner_id, client_id=client_id, product_id=str(product.id), currency=currency)
            )
            if index and index % 100 == 0:
                db.commit()
        db.commit()

        base_orders = orders_total // partners_total
        remainder = orders_total % partners_total
        order_records: list[tuple[str, str, str]] = []
        orders_per_partner: dict[str, int] = {}

        start = time.perf_counter()
        for index, seed in enumerate(partner_seeds):
            partner_orders = base_orders + (1 if index < remainder else 0)
            if partner_orders == 0:
                orders_per_partner[seed.partner_id] = 0
                continue
            order_ids = _create_orders(
                db,
                partner_id=seed.partner_id,
                client_id=seed.client_id,
                product_id=seed.product_id,
                count=partner_orders,
            )
            orders_per_partner[seed.partner_id] = partner_orders
            order_records.extend((order_id, seed.partner_id, seed.currency) for order_id in order_ids)
        duration = time.perf_counter() - start

        if penalty_rate > 0 and order_records:
            step = max(1, int(round(1 / penalty_rate)))
            settlement_service = MarketplaceSettlementService(db)
            finance_service = PartnerFinanceService(db)
            for index, (order_id, partner_id, currency) in enumerate(order_records, start=1):
                if index % step == 0:
                    settlement_service.update_penalty_for_order(order_id=order_id, penalty_amount=penalty_amount)
                    finance_service.record_sla_penalty(
                        partner_org_id=partner_id,
                        order_id=order_id,
                        amount=penalty_amount,
                        currency=currency,
                        reason="SLA_BREACH",
                    )
            db.commit()

        period = datetime.now(timezone.utc).strftime("%Y-%m")
        settlement_service = MarketplaceSettlementService(db)
        payout_partners = partner_seeds[: min(payout_batches_target, len(partner_seeds))]
        for seed in payout_partners:
            payout_start = time.perf_counter()
            try:
                result = settlement_service.build_payout_batch(
                    tenant_id=1,
                    partner_id=seed.partner_id,
                    period=period,
                )
                db.commit()
                payout_batches_built += 1
                payout_duration += time.perf_counter() - payout_start
                operations_count = int(result.batch.operations_count or 0)
                max_payout_batch_operations = max(max_payout_batch_operations, operations_count)
                batch_total = _sum_decimal(result.batch.total_amount)
                if batch_total > max_payout_batch_total_amount:
                    max_payout_batch_total_amount = batch_total

                payout_replay_error = False
                try:
                    settlement_service.build_payout_batch(tenant_id=1, partner_id=seed.partner_id, period=period)
                    payout_replay_error = True
                except ValueError as exc:
                    if str(exc) != "no_open_settlement_items":
                        payout_replay_error = True
                if payout_replay_error:
                    partner_errors.setdefault(seed.partner_id, []).append("double_payout_possible")
            except PayoutBlockedError as exc:
                payout_duration += time.perf_counter() - payout_start
                payout_blocked_by_partner[seed.partner_id] = exc.reasons
                for reason in exc.reasons:
                    payout_blocked_reasons[reason] = payout_blocked_reasons.get(reason, 0) + 1

        payout_total = Decimal("0")
        for seed in partner_seeds:
            snapshot_total = _sum_decimal(
                db.query(func.coalesce(func.sum(MarketplaceSettlementSnapshot.partner_net), 0))
                .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceSettlementSnapshot.order_id)
                .filter(MarketplaceOrder.partner_id == seed.partner_id)
                .scalar()
            )
            fee_total = _sum_decimal(
                db.query(func.coalesce(func.sum(MarketplaceSettlementSnapshot.platform_fee), 0))
                .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceSettlementSnapshot.order_id)
                .filter(MarketplaceOrder.partner_id == seed.partner_id)
                .scalar()
            )
            ledger_total = _ledger_total(db, seed.partner_id)
            revenue_total = _sum_decimal(
                db.query(func.coalesce(func.sum(PlatformRevenueEntry.amount), 0))
                .join(MarketplaceOrder, MarketplaceOrder.id == PlatformRevenueEntry.order_id)
                .filter(MarketplaceOrder.partner_id == seed.partner_id)
                .scalar()
            )
            payout_total_partner = _payout_total(db, seed.partner_id)
            payout_total += payout_total_partner

            account = (
                db.query(PartnerAccount)
                .filter_by(org_id=seed.partner_id, currency=seed.currency)
                .one_or_none()
            )
            account_balance = Decimal(str(account.balance_available or 0)) if account else Decimal("0")

            errors: list[str] = []
            if orders_per_partner.get(seed.partner_id, 0) == 0:
                errors.append("no_orders")
            if snapshot_total != ledger_total:
                errors.append("ledger_drift")
            if fee_total != revenue_total:
                errors.append("revenue_drift")
            if payout_total_partner and snapshot_total != payout_total_partner:
                errors.append("payout_mismatch")
            if account_balance < 0:
                errors.append("negative_balance")

            if errors:
                partner_errors.setdefault(seed.partner_id, []).extend(errors)

            partner_results.append(
                PartnerResult(
                    partner_id=seed.partner_id,
                    currency=seed.currency,
                    orders=orders_per_partner.get(seed.partner_id, 0),
                    settlement_snapshot_total=snapshot_total,
                    ledger_total=ledger_total,
                    revenue_total=revenue_total,
                    payout_total=payout_total_partner,
                    payout_blocked=seed.partner_id in payout_blocked_by_partner,
                    payout_blocked_reasons=payout_blocked_by_partner.get(seed.partner_id, []),
                    errors=partner_errors.get(seed.partner_id, []),
                )
            )

        error_totals: dict[str, int] = {}
        for errors in partner_errors.values():
            for error in errors:
                error_totals[error] = error_totals.get(error, 0) + 1
        partners_with_errors = len(partner_errors)

        settlement_snapshot_total = _sum_decimal(
            db.query(func.coalesce(func.sum(MarketplaceSettlementSnapshot.partner_net), 0)).scalar()
        )
        ledger_total = _sum_decimal(
            db.query(
                func.coalesce(
                    func.sum(
                        case(
                            (PartnerLedgerEntry.direction == PartnerLedgerDirection.CREDIT, PartnerLedgerEntry.amount),
                            else_=-PartnerLedgerEntry.amount,
                        )
                    ),
                    0,
                )
            )
            .filter(
                PartnerLedgerEntry.entry_type.in_(
                    [
                        PartnerLedgerEntryType.EARNED,
                        PartnerLedgerEntryType.SLA_PENALTY,
                        PartnerLedgerEntryType.ADJUSTMENT,
                    ]
                )
            )
            .scalar()
        )
        revenue_total = _sum_decimal(db.query(func.coalesce(func.sum(PlatformRevenueEntry.amount), 0)).scalar())

        negative_balance_total = (
            db.query(PartnerAccount)
            .filter(PartnerAccount.balance_available < 0)
            .count()
        )
        payout_without_finalize_total = (
            db.query(MarketplaceSettlementSnapshot)
            .join(
                MarketplaceSettlementItem,
                MarketplaceSettlementItem.settlement_snapshot_id == MarketplaceSettlementSnapshot.id,
            )
            .filter(MarketplaceSettlementItem.status == MarketplaceSettlementStatus.INCLUDED_IN_PAYOUT.value)
            .filter(MarketplaceSettlementSnapshot.finalized_at.is_(None))
            .count()
        )

        settlement_immutable_violation_total = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "SETTLEMENT_IMMUTABLE_VIOLATION")
            .count()
        )

        payout_blocked_total = sum(payout_blocked_reasons.values())

        return LoadResult(
            run_id=run_id,
            orders=orders_total,
            partners=partners_total,
            payout_batches_target=payout_batches_target,
            payout_batches_built=payout_batches_built,
            duration_seconds=duration,
            payout_duration_seconds=payout_duration,
            settlement_snapshot_total=settlement_snapshot_total,
            ledger_total=ledger_total,
            revenue_total=revenue_total,
            payout_total=payout_total,
            payout_blocked_total=payout_blocked_total,
            payout_blocked_reasons=payout_blocked_reasons,
            max_payout_batch_operations=max_payout_batch_operations,
            max_payout_batch_total_amount=max_payout_batch_total_amount,
            partners_with_errors=partners_with_errors,
            error_rate=partners_with_errors / partners_total if partners_total else 0,
            error_totals=error_totals,
            negative_balance_total=negative_balance_total,
            payout_without_finalize_total=payout_without_finalize_total,
            settlement_immutable_violation_total=settlement_immutable_violation_total,
            partner_results=partner_results,
        )
    finally:
        db.close()


def _write_report(path: Path, csv_path: Path, results: list[LoadResult], *, include_partners: bool) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [result.to_dict(include_partners=include_partners) for result in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "orders",
                "partners",
                "payout_batches_target",
                "payout_batches_built",
                "duration_seconds",
                "payout_duration_seconds",
                "settlement_snapshot_total",
                "ledger_total",
                "revenue_total",
                "payout_total",
                "payout_blocked_total",
                "max_payout_batch_operations",
                "max_payout_batch_total_amount",
                "partners_with_errors",
                "error_rate",
                "negative_balance_total",
                "payout_without_finalize_total",
                "settlement_immutable_violation_total",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "run_id": result.run_id,
                    "orders": result.orders,
                    "partners": result.partners,
                    "payout_batches_target": result.payout_batches_target,
                    "payout_batches_built": result.payout_batches_built,
                    "duration_seconds": round(result.duration_seconds, 3),
                    "payout_duration_seconds": round(result.payout_duration_seconds, 3),
                    "settlement_snapshot_total": str(result.settlement_snapshot_total),
                    "ledger_total": str(result.ledger_total),
                    "revenue_total": str(result.revenue_total),
                    "payout_total": str(result.payout_total),
                    "payout_blocked_total": result.payout_blocked_total,
                    "max_payout_batch_operations": result.max_payout_batch_operations,
                    "max_payout_batch_total_amount": str(result.max_payout_batch_total_amount),
                    "partners_with_errors": result.partners_with_errors,
                    "error_rate": round(result.error_rate, 4),
                    "negative_balance_total": result.negative_balance_total,
                    "payout_without_finalize_total": result.payout_without_finalize_total,
                    "settlement_immutable_violation_total": result.settlement_immutable_violation_total,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="MoR settlement load test runner")
    parser.add_argument("--orders", type=int, default=10_000, help="Total orders per run")
    parser.add_argument("--partners", type=int, default=1_000, help="Partners to seed per run")
    parser.add_argument("--payout-batches", type=int, default=100, help="Payout batches to build per run")
    parser.add_argument("--runs", type=int, default=3, help="How many full runs to execute")
    parser.add_argument("--penalty-rate", type=float, default=0.1, help="Fraction of orders with SLA penalties")
    parser.add_argument("--penalty-amount", type=str, default="5", help="Penalty amount per order")
    parser.add_argument("--mixed-currencies", action="store_true", help="Enable multi-currency orders")
    parser.add_argument("--include-partners", action="store_true", help="Include per-partner details in JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/load_mor_settlement.json"),
        help="Where to write the JSON report",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path("reports/load_mor_settlement.csv"),
        help="Where to write the CSV report",
    )
    args = parser.parse_args()

    results = [
        run_load(
            run_id=run_id,
            orders_total=args.orders,
            partners_total=args.partners,
            payout_batches_target=args.payout_batches,
            penalty_rate=args.penalty_rate,
            penalty_amount=Decimal(args.penalty_amount),
            mixed_currencies=args.mixed_currencies,
        )
        for run_id in range(1, args.runs + 1)
    ]
    _write_report(args.output, args.csv_output, results, include_partners=args.include_partners)

    print("MoR settlement load test report")
    for result in results:
        print(
            " ".join(
                [
                    f"run={result.run_id}",
                    f"orders={result.orders}",
                    f"partners={result.partners}",
                    f"duration={result.duration_seconds:.2f}s",
                    f"payout={result.payout_duration_seconds:.2f}s",
                    f"errors={result.partners_with_errors}",
                    f"blocked={result.payout_blocked_total}",
                ]
            )
        )
    print(f"Report saved to {args.output} and {args.csv_output}")


if __name__ == "__main__":
    main()
