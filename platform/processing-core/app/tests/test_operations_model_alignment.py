from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.operation import (
    Operation,
    OperationStatus,
    OperationType,
    ProductType,
    RiskResult,
)
from app.models.fuel import FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationNetwork

_TABLES = [
    FuelNetwork.__table__,
    FuelStationNetwork.__table__,
    FuelStation.__table__,
    Operation.__table__,
]

def _session_factory() -> tuple[sessionmaker[Session], object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _TABLES:
        table.create(bind=engine, checkfirst=True)
    return (
        sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session),
        engine,
    )


def test_operation_model_supports_full_lifecycle_fields():
    SessionLocal, engine = _session_factory()
    session = SessionLocal()
    try:
        network = FuelNetwork(name="Net", provider_code="NET", status=FuelNetworkStatus.ACTIVE)
        session.add(network)
        session.flush()

        op = Operation(
            operation_id="ext-123",
            operation_type=OperationType.AUTH,
            status=OperationStatus.PENDING,
            merchant_id="m1",
            terminal_id="t1",
            fuel_station_id=None,
            client_id="c1",
            card_id="card-1",
            product_id="fuel-1",
            amount=10_000,
            amount_settled=8_000,
            currency="RUB",
            product_type=ProductType.DIESEL,
            quantity=10,
            unit_price=1000,
            limit_profile_id="lp-1",
            limit_check_result={"approved": True},
            risk_score=0.1,
            risk_result=RiskResult.LOW,
            risk_payload={"rule": "safe"},
            auth_code="A1B2C3",
            parent_operation_id=None,
        )
        session.add(op)
        session.commit()
        session.refresh(op)
    finally:
        session.close()

    assert op.id is not None
    # ensure UUID semantics
    UUID(str(op.id))

    fetched_session = SessionLocal()
    try:
        fetched = fetched_session.query(Operation).filter_by(operation_id="ext-123").first()
        assert fetched is not None
        assert fetched.amount == 10_000
        assert fetched.amount_settled == 8_000
        assert fetched.product_type == ProductType.DIESEL
        assert fetched.quantity == 10
        assert fetched.unit_price == 1000
        assert fetched.limit_profile_id == "lp-1"
        assert fetched.limit_check_result == {"approved": True}
        assert fetched.risk_result == RiskResult.LOW
        assert fetched.risk_payload == {"rule": "safe"}
        assert fetched.auth_code == "A1B2C3"
    finally:
        fetched_session.close()
        engine.dispose()
