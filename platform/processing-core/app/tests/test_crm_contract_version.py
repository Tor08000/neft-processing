from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.crm import CRMClient, CRMClientStatus, CRMBillingMode, CRMContract, CRMContractStatus
from app.services.crm import contracts


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


def test_contract_version_bumped_on_status_change(session):
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    contract = CRMContract(
        tenant_id=1,
        client_id=client.id,
        contract_number="CNT-1",
        status=CRMContractStatus.DRAFT,
        billing_mode=CRMBillingMode.POSTPAID,
        currency="RUB",
        valid_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session.add_all([client, contract])
    session.commit()

    original_version = contract.crm_contract_version
    updated = contracts.set_contract_status(
        session,
        contract=contract,
        status=CRMContractStatus.ACTIVE,
        request_ctx=None,
    )

    assert updated.crm_contract_version == original_version + 1
