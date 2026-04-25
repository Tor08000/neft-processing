from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.decision_memory import DecisionMemoryRecord
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
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderActorType, MarketplaceOrderEvent, MarketplacePaymentFlow
from app.models.marketplace_settlement import MarketplaceSettlementItem, MarketplaceSettlementSnapshot
from app.models.notifications import NotificationMessage
from app.models.partner_finance import PartnerAccount, PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.platform_revenue import PlatformRevenueEntry
from app.services.marketplace_order_service import MarketplaceOrderService
from app.services.marketplace_settlement_service import MarketplaceSettlementService
from app.services.partner_finance_service import PartnerFinanceService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        AuditLog.__table__,
        DecisionMemoryRecord.__table__,
        Case.__table__,
        CaseSnapshot.__table__,
        CaseComment.__table__,
        CaseEvent.__table__,
        MarketplaceProduct.__table__,
        MarketplaceOrder.__table__,
        MarketplaceCommissionRule.__table__,
        MarketplaceOrderEvent.__table__,
        MarketplaceSettlementItem.__table__,
        MarketplaceSettlementSnapshot.__table__,
        PartnerAccount.__table__,
        PartnerLedgerEntry.__table__,
        NotificationMessage.__table__,
        PlatformRevenueEntry.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(tables):
            table.drop(bind=engine)
        engine.dispose()


def test_mor_settlement_breakdown_and_ledgers(db_session: Session) -> None:
    partner_id = str(uuid4())
    client_id = str(uuid4())

    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=partner_id,
        type=MarketplaceProductType.SERVICE.value,
        title="MoR product",
        description="Service",
        category="maintenance",
        price_model="FIXED",
        price_config={"amount": "100", "currency": "RUB"},
        status=MarketplaceProductStatus.PUBLISHED.value,
        moderation_status=MarketplaceProductModerationStatus.APPROVED.value,
    )
    db_session.add(product)
    db_session.flush()

    commission_rule = MarketplaceCommissionRule(
        id=str(uuid4()),
        scope=MarketplaceCommissionScope.MARKETPLACE.value,
        partner_id=partner_id,
        product_category="maintenance",
        commission_type=MarketplaceCommissionType.FIXED.value,
        amount=Decimal("15"),
        priority=100,
        status=MarketplaceCommissionStatus.ACTIVE.value,
    )
    db_session.add(commission_rule)
    db_session.commit()

    order_service = MarketplaceOrderService(db_session)
    order = order_service.create_order(
        client_id=client_id,
        product_id=str(product.id),
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
        summary="done",
        actor=MarketplaceOrderActorType.SYSTEM,
    )
    db_session.commit()

    order = db_session.query(MarketplaceOrder).filter(MarketplaceOrder.id == order.id).one()
    breakdown = order.settlement_breakdown_json
    assert order.payment_flow == MarketplacePaymentFlow.PLATFORM_MOR.value
    assert breakdown == {
        "gross_amount": "100",
        "platform_fee_amount": "15",
        "platform_fee_basis": "FIXED",
        "penalties_amount": "0",
        "partner_net_amount": "85",
        "currency": "RUB",
    }

    settlement_item = db_session.query(MarketplaceSettlementItem).filter_by(order_id=order.id).one()
    assert settlement_item.net_partner_amount == Decimal("85")
    snapshot = db_session.query(MarketplaceSettlementSnapshot).filter_by(order_id=order.id).one()
    assert snapshot.partner_net == Decimal("85")
    assert snapshot.hash is not None

    ledger_entry = (
        db_session.query(PartnerLedgerEntry)
        .filter(PartnerLedgerEntry.order_id == str(order.id))
        .filter(PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.EARNED)
        .one()
    )
    assert ledger_entry.amount == Decimal("85")
    assert ledger_entry.meta_json["settlement_snapshot_id"] == str(snapshot.id)

    revenue_entry = db_session.query(PlatformRevenueEntry).filter_by(order_id=order.id).one()
    assert revenue_entry.amount == Decimal("15")
    assert revenue_entry.meta_json["settlement_snapshot_id"] == str(snapshot.id)

    penalty_result = MarketplaceSettlementService(db_session).update_penalty_for_order(
        order_id=str(order.id),
        penalty_amount=Decimal("5"),
    )
    assert penalty_result is not None
    PartnerFinanceService(db_session).record_sla_penalty(
        partner_org_id=partner_id,
        order_id=str(order.id),
        amount=Decimal("5"),
        currency="RUB",
        reason="SLA_BREACH",
    )
    db_session.commit()

    order = db_session.query(MarketplaceOrder).filter(MarketplaceOrder.id == order.id).one()
    assert order.settlement_breakdown_json["penalties_amount"] == "5"
    assert order.settlement_breakdown_json["partner_net_amount"] == "80"

    settlement_item = db_session.query(MarketplaceSettlementItem).filter_by(order_id=order.id).one()
    assert settlement_item.net_partner_amount == Decimal("80")
    snapshot = db_session.query(MarketplaceSettlementSnapshot).filter_by(order_id=order.id).one()
    assert snapshot.penalties == Decimal("5")
    assert snapshot.partner_net == Decimal("80")

    account = db_session.query(PartnerAccount).filter_by(org_id=partner_id).one()
    assert account.balance_available == Decimal("80")
