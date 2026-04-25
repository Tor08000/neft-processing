from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.api.v1.endpoints.logistics import router as logistics_router
from app.db import Base, get_db
from app.fastapi_utils import generate_unique_id
from app.models import audit_log as audit_models
from app.models import fleet as fleet_models
from app.models import fuel as fuel_models
from app.models import internal_ledger as internal_ledger_models
from app.models import legal_graph as legal_models
from app.models import logistics as logistics_models
from app.models import risk_decision as risk_decision_models
from app.routers.admin.logistics import router as admin_logistics_router

# Register the nullable logistics stop FK target without pulling the full fuel schema graph.
_ = fuel_models.FuelTransaction.__table__
_ = internal_ledger_models.InternalLedgerTransaction.__table__
_ = risk_decision_models.RiskDecision.__table__

LOGISTICS_ROUTE_TEST_TABLES = [
    audit_models.AuditLog.__table__,
    legal_models.LegalNode.__table__,
    legal_models.LegalEdge.__table__,
    fleet_models.FleetVehicle.__table__,
    fleet_models.FleetDriver.__table__,
    logistics_models.LogisticsOrder.__table__,
    logistics_models.LogisticsRoute.__table__,
    logistics_models.LogisticsStop.__table__,
    logistics_models.LogisticsTrackingEvent.__table__,
    logistics_models.LogisticsETASnapshot.__table__,
    logistics_models.LogisticsRouteConstraint.__table__,
    logistics_models.LogisticsDeviationEvent.__table__,
    logistics_models.LogisticsETAAccuracy.__table__,
    logistics_models.LogisticsRiskSignal.__table__,
    logistics_models.LogisticsRouteSnapshot.__table__,
    logistics_models.LogisticsNavigatorExplain.__table__,
]

LOGISTICS_FUEL_TEST_TABLES = [
    *LOGISTICS_ROUTE_TEST_TABLES,
    fuel_models.FuelCardGroup.__table__,
    fuel_models.FleetOfflineProfile.__table__,
    fuel_models.FuelNetwork.__table__,
    fuel_models.FuelStationNetwork.__table__,
    fuel_models.FuelCard.__table__,
    fuel_models.FuelStation.__table__,
    fuel_models.FuelTransaction.__table__,
    fuel_models.FuelFraudSignal.__table__,
    fuel_models.StationReputationDaily.__table__,
    logistics_models.FuelRouteLink.__table__,
    logistics_models.LogisticsFuelLink.__table__,
    logistics_models.LogisticsFuelAlert.__table__,
]


def _default_admin_claims() -> dict[str, object]:
    return {
        "user_id": "admin-ops-1",
        "sub": "admin-ops-1",
        "email": "ops-admin@example.com",
        "roles": ["NEFT_OPS"],
    }


@contextmanager
def logistics_client_context(
    *,
    include_admin_router: bool = False,
    admin_claims: dict[str, object] | None = None,
) -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine, tables=LOGISTICS_ROUTE_TEST_TABLES)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(logistics_router, prefix="")
    if include_admin_router:
        app.include_router(admin_logistics_router, prefix="/api/core/v1/admin")
        app.dependency_overrides[require_admin_user] = lambda: dict(admin_claims or _default_admin_claims())

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine, tables=LOGISTICS_ROUTE_TEST_TABLES)
        engine.dispose()


@contextmanager
def logistics_fuel_client_context() -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(logistics_router, prefix="")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)
        engine.dispose()


@contextmanager
def admin_logistics_client_context(
    *,
    admin_claims: dict[str, object] | None = None,
) -> Iterator[tuple[TestClient, sessionmaker]]:
    with logistics_client_context(include_admin_router=True, admin_claims=admin_claims) as ctx:
        yield ctx


@contextmanager
def logistics_session_context() -> Iterator[tuple[Session, sessionmaker]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine, tables=LOGISTICS_ROUTE_TEST_TABLES)
    session = testing_session_local()
    try:
        yield session, testing_session_local
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=LOGISTICS_ROUTE_TEST_TABLES)
        engine.dispose()


@contextmanager
def logistics_fuel_session_context() -> Iterator[tuple[Session, sessionmaker]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)
    session = testing_session_local()
    try:
        yield session, testing_session_local
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)
        engine.dispose()


__all__ = [
    "logistics_client_context",
    "logistics_fuel_client_context",
    "admin_logistics_client_context",
    "logistics_session_context",
    "logistics_fuel_session_context",
]
