import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

import app.services.transactions_service as transactions_service
from app.db import Base, SessionLocal, engine
from app.models.operation import Operation, OperationStatus, OperationType, RiskResult as RiskLevel
from app.services import risk_adapter, risk_rules
from app.services.risk_rules import (
    MetricType,
    RuleAction,
    RuleDefinition,
    RuleScope,
    RuleSelector,
    RuleWindow,
)
from app.services.risk_adapter import OperationContext, RiskResult, evaluate_risk
from app.services.transactions_service import authorize_operation


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_rules_detect_graylist_and_night(monkeypatch):
    monkeypatch.setattr(risk_rules, "GRAYLIST_TERMINALS", {"t1"})
    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="t1",
        merchant_id="m1",
        product_type="DIESEL",
        amount=150_000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        created_at=datetime(2023, 1, 1, 2, 30, tzinfo=timezone.utc),
    )

    result = asyncio.run(risk_rules.evaluate_rules(ctx))

    assert result.risk_result in {"HIGH", "BLOCK"}
    assert "graylisted_terminal" in result.reasons
    assert "night_operation" in result.reasons
    assert "amount_above_threshold" in result.reasons


def test_ai_and_rules_combination_prefers_high(monkeypatch):
    async def fake_ai(context):
        return RiskResult(0.1, "LOW", ["ai_low"], {"ai": True}, "AI")

    monkeypatch.setattr(risk_adapter, "call_risk_engine", fake_ai)
    monkeypatch.setattr(risk_rules, "GRAYLIST_TERMINALS", {"gt"})

    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="gt",
        merchant_id="m1",
        product_type="DIESEL",
        amount=10_000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        created_at=datetime.now(timezone.utc),
    )

    result = asyncio.run(evaluate_risk(ctx))

    assert result.risk_result == "HIGH"
    assert result.source == "AI+RULES"
    assert "graylisted_terminal" in result.reasons


def test_ai_block_overrides_rules(monkeypatch):
    async def fake_ai(context):
        return RiskResult(0.95, "BLOCK", ["ai_block"], {"ai": True}, "AI")

    monkeypatch.setattr(risk_adapter, "call_risk_engine", fake_ai)

    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="t1",
        merchant_id="m1",
        product_type="DIESEL",
        amount=1000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        created_at=datetime.now(timezone.utc),
    )

    result = asyncio.run(evaluate_risk(ctx))

    assert result.risk_result == "BLOCK"
    assert "ai_block" in result.reasons


def test_ai_fallback_uses_rules(monkeypatch):
    async def failing_ai(context):  # pragma: no cover - exercised via fallback path
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(risk_adapter, "call_risk_engine", failing_ai)

    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="t1",
        merchant_id="m1",
        product_type="DIESEL",
        amount=150_000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        created_at=datetime.now(timezone.utc),
    )

    result = asyncio.run(evaluate_risk(ctx))

    assert result.risk_result in {"MEDIUM", "HIGH"}
    assert result.source == "RULES_FALLBACK"
    assert "amount_above_threshold" in result.reasons
    assert "ai_error" in result.flags


def test_risk_block_declines_operation(monkeypatch, session):
    from app.models.card import Card
    from app.models.client import Client
    from app.models.merchant import Merchant
    from app.models.terminal import Terminal

    client_pk = uuid4()
    session.add(Client(id=client_pk, name="Test", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_pk), status="ACTIVE"))
    session.add(Merchant(id="m-1", name="M1", status="ACTIVE"))
    session.add(Terminal(id="t-1", merchant_id="m-1", status="ACTIVE"))
    session.commit()

    def blocking_risk(context, db=None):
        return RiskResult(1.0, "BLOCK", ["blacklist"], {}, "AI")

    monkeypatch.setattr(transactions_service, "call_risk_engine_sync", blocking_risk)

    op = authorize_operation(
        session,
        client_id=str(client_pk),
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=10_000,
        currency="RUB",
        ext_operation_id="ext-block",
    )

    assert op.status == OperationStatus.DECLINED
    assert op.response_code == "RISK_BLOCK"
    assert op.risk_result == RiskLevel.BLOCK
    assert op.risk_payload.get("reasons") == ["blacklist"]


def test_rule_anomalies_from_history(monkeypatch, session):
    from datetime import timedelta

    from app.models.operation import Operation, OperationType

    now = datetime.now(timezone.utc)
    client_pk = uuid4()
    card_id = "card-history"

    # Historical operations to build stats
    past_ops = [
        Operation(
            ext_operation_id=f"ext-old-{idx}",
            operation_id=f"ext-old-{idx}",
            operation_type=OperationType.AUTH,
            status=OperationStatus.COMPLETED,
            merchant_id="m-1",
            terminal_id="t-1",
            client_id=str(client_pk),
            card_id=card_id,
            product_id=None,
            amount=20_000,
            currency="RUB",
            product_type="DIESEL",
            authorized=True,
            response_code="00",
            response_message="OK",
            created_at=now - timedelta(days=2),
        )
        for idx in range(1)
    ]

    recent_ops = [
        Operation(
            ext_operation_id=f"ext-recent-{idx}",
            operation_id=f"ext-recent-{idx}",
            operation_type=OperationType.AUTH,
            status=OperationStatus.COMPLETED,
            merchant_id="m-1",
            terminal_id="t-1",
            client_id=str(client_pk),
            card_id=card_id,
            product_id=None,
            amount=500,
            currency="RUB",
            product_type="DIESEL",
            authorized=True,
            response_code="00",
            response_message="OK",
            created_at=now - timedelta(minutes=20),
        )
        for idx in range(6)
    ]

    for op in [*past_ops, *recent_ops]:
        session.add(op)
    session.commit()

    ctx = OperationContext(
        client_id=client_pk,
        card_id=card_id,
        terminal_id="t-1",
        merchant_id="m-1",
        product_type="GAS",
        amount=60_000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        created_at=now,
    )

    result = asyncio.run(risk_rules.evaluate_rules(ctx, db=session))

    assert result.risk_result == "HIGH"
    assert "amount_spike" in result.reasons
    assert "high_frequency" in result.reasons
    assert "unusual_fuel_type" in result.reasons


def test_hard_and_soft_limits(monkeypatch):
    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="t1",
        merchant_id="m1",
        amount=120_000,
        currency="RUB",
        quantity=120.5,
        created_at=datetime(2024, 5, 5, 10, tzinfo=timezone.utc),
    )

    rules = [
        RuleDefinition(
            name="hard_amount_limit",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.AMOUNT,
            value=100_000,
            action=RuleAction.BLOCK,
            reason="hard_amount_limit",
        ),
        RuleDefinition(
            name="soft_quantity_limit",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.QUANTITY,
            value=100,
            action=RuleAction.MANUAL_REVIEW,
            reason="soft_quantity_limit",
        ),
    ]

    result = asyncio.run(risk_rules.evaluate_rules(ctx, rules=rules))

    assert result.risk_result == "BLOCK"
    assert set(result.reasons) == {"hard_amount_limit", "soft_quantity_limit"}


def test_tariff_rule_and_window_count(monkeypatch, session):
    now = datetime(2024, 6, 1, 9, tzinfo=timezone.utc)
    client_pk = uuid4()
    card_id = uuid4()

    for idx in range(3):
        session.add(
            Operation(
                ext_operation_id=f"ext-tariff-{idx}",
                operation_id=f"int-tariff-{idx}",
                operation_type=OperationType.AUTH,
                status=OperationStatus.COMPLETED,
                merchant_id="m-1",
                terminal_id="t-1",
                client_id=str(client_pk),
                card_id=str(card_id),
                product_id=None,
                amount=10_000,
                currency="RUB",
                product_type="DIESEL",
                authorized=True,
                response_code="00",
                response_message="OK",
                created_at=now - timedelta(minutes=10 * (idx + 1)),
            )
        )
    session.commit()

    ctx = OperationContext(
        client_id=client_pk,
        card_id=card_id,
        terminal_id="t-1",
        merchant_id="m-1",
        amount=5_000,
        currency="RUB",
        tariff_id="T-1",
        created_at=now,
    )

    rules = [
        RuleDefinition(
            name="tariff_window_count",
            scope=RuleScope.TARIFF,
            subject_id="T-1",
            selector=RuleSelector(),
            metric=MetricType.COUNT,
            value=2,
            action=RuleAction.MEDIUM,
            window=RuleWindow.hours(1),
            reason="tariff_count_limit",
        )
    ]

    result = asyncio.run(risk_rules.evaluate_rules(ctx, db=session, rules=rules))

    assert result.risk_result == "MEDIUM"
    assert result.reasons == ["tariff_count_limit"]


def test_geo_and_time_selector(monkeypatch):
    ctx = OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="t1",
        merchant_id="m1",
        amount=10_000,
        currency="RUB",
        geo="RU-MOW",
        created_at=datetime(2024, 6, 1, 3, tzinfo=timezone.utc),
    )

    rules = [
        RuleDefinition(
            name="geo_time_window",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(geo={"RU-MOW"}, hours=range(0, 6)),
            metric=MetricType.ALWAYS,
            value=1,
            action=RuleAction.HIGH,
            reason="geo_time_match",
        )
    ]

    result = asyncio.run(risk_rules.evaluate_rules(ctx, rules=rules))

    assert result.risk_result == "HIGH"
    assert result.reasons == ["geo_time_match"]
