from __future__ import annotations

import json

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import bootstrap


def test_merge_org_roles_preserves_existing_partner_role() -> None:
    assert json.loads(bootstrap._merge_org_roles(["PARTNER"], ("CLIENT",))) == ["CLIENT", "PARTNER"]


def test_merge_org_roles_accepts_jsonb_text() -> None:
    assert json.loads(bootstrap._merge_org_roles('["partner"]', ("client",))) == ["CLIENT", "PARTNER"]


def test_ensure_demo_subscription_seed_creates_plan_modules_and_subscription(monkeypatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    metadata = MetaData()

    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String, primary_key=True),
        Column("code", String, nullable=False),
        Column("version", Integer, nullable=True),
        Column("billing_period_months", Integer, nullable=True),
        Column("title", String, nullable=True),
        Column("description", String, nullable=True),
        Column("currency", String, nullable=True),
        Column("is_active", Boolean, nullable=True),
        Column("price_cents", Integer, nullable=True),
        Column("discount_percent", Integer, nullable=True),
    )
    subscription_plan_modules = Table(
        "subscription_plan_modules",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("plan_id", String, nullable=False),
        Column("module_code", String, nullable=False),
        Column("enabled", Boolean, nullable=False),
        Column("tier", String, nullable=True),
        Column("limits_json", String, nullable=True),
    )
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String, nullable=False),
        Column("plan_id", String, nullable=False),
        Column("status", String, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
        Column("start_at", DateTime(timezone=True), nullable=True),
    )
    metadata.create_all(bind=engine)

    monkeypatch.setattr(bootstrap, "DB_SCHEMA", "main", raising=False)
    monkeypatch.setattr(bootstrap, "_filter_columns", lambda table_name, db, values: values)

    with session_local() as session:
        bootstrap._ensure_demo_subscription_seed(
            session,
            conn=session.connection(),
            table_names={"subscription_plans", "subscription_plan_modules", "client_subscriptions"},
            client_id="00000000-0000-0000-0000-000000000001",
            org_id=1,
        )
        session.commit()

        stored_plan = session.execute(select(subscription_plans)).mappings().one()
        stored_subscription = session.execute(select(client_subscriptions)).mappings().one()
        module_codes = {
            row["module_code"]
            for row in session.execute(select(subscription_plan_modules.c.module_code)).mappings().all()
        }

    assert stored_plan["code"] == bootstrap.DEFAULT_DEMO_PLAN_CODE
    assert stored_subscription["tenant_id"] == 1
    assert stored_subscription["client_id"] == "00000000-0000-0000-0000-000000000001"
    assert {"FUEL_CORE", "MARKETPLACE", "ANALYTICS", "SLA"}.issubset(module_codes)


def test_ensure_demo_subscription_seed_does_not_overwrite_commercial_plan(monkeypatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    metadata = MetaData()

    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String, primary_key=True),
        Column("code", String, nullable=False),
        Column("version", Integer, nullable=True),
        Column("billing_period_months", Integer, nullable=True),
        Column("title", String, nullable=True),
        Column("description", String, nullable=True),
        Column("currency", String, nullable=True),
        Column("is_active", Boolean, nullable=True),
        Column("price_cents", Integer, nullable=True),
        Column("discount_percent", Integer, nullable=True),
    )
    subscription_plan_modules = Table(
        "subscription_plan_modules",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("plan_id", String, nullable=False),
        Column("module_code", String, nullable=False),
        Column("enabled", Boolean, nullable=False),
        Column("tier", String, nullable=True),
        Column("limits_json", String, nullable=True),
    )
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String, nullable=False),
        Column("plan_id", String, nullable=False),
        Column("status", String, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
        Column("start_at", DateTime(timezone=True), nullable=True),
    )
    metadata.create_all(bind=engine)

    monkeypatch.setattr(bootstrap, "DB_SCHEMA", "main", raising=False)
    monkeypatch.setattr(bootstrap, "_filter_columns", lambda table_name, db, values: values)

    with session_local() as session:
        session.execute(
            subscription_plans.insert().values(
                id="commercial-control-individual-1m",
                code="CONTROL_INDIVIDUAL_1M",
                version=1,
                billing_period_months=1,
                title="CONTROL INDIVIDUAL 1M",
                description="Commercial individual control plan",
                currency="RUB",
                is_active=True,
                price_cents=9900,
                discount_percent=0,
            )
        )
        bootstrap._ensure_demo_subscription_seed(
            session,
            conn=session.connection(),
            table_names={"subscription_plans", "subscription_plan_modules", "client_subscriptions"},
            client_id="00000000-0000-0000-0000-000000000001",
            org_id=1,
        )
        session.commit()

        plans = {
            row["code"]: row
            for row in session.execute(select(subscription_plans)).mappings().all()
        }
        stored_subscription = session.execute(select(client_subscriptions)).mappings().one()

    assert plans["CONTROL_INDIVIDUAL_1M"]["price_cents"] == 9900
    assert plans[bootstrap.DEFAULT_DEMO_PLAN_CODE]["price_cents"] == 0
    assert stored_subscription["plan_id"] == bootstrap.DEFAULT_DEMO_PLAN_ID
