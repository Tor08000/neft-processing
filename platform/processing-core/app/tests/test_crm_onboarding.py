from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.client_actions import DocumentAcknowledgement
from app.models.crm import (
    CRMBillingCycle,
    CRMBillingMode,
    CRMClient,
    CRMClientStatus,
    CRMContract,
    CRMContractStatus,
    CRMLimitProfile,
    CRMProfileStatus,
    CRMSubscription,
    CRMSubscriptionStatus,
)
from app.services.crm import onboarding, repository


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_onboarding_recompute_progression():
    db = SessionLocal()
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        tax_id=None,
        kpp=None,
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    db.add(client)
    limit_profile = CRMLimitProfile(
        tenant_id=1,
        name="Default",
        status=CRMProfileStatus.ACTIVE,
        definition={"daily": 1000},
    )
    db.add(limit_profile)
    db.commit()
    contract = CRMContract(
        tenant_id=1,
        client_id=client.id,
        contract_number="C-1",
        status=CRMContractStatus.ACTIVE,
        billing_mode=CRMBillingMode.POSTPAID,
        currency="RUB",
        limit_profile_id=limit_profile.id,
        valid_from=datetime.now(timezone.utc),
    )
    subscription = CRMSubscription(
        tenant_id=1,
        client_id=client.id,
        tariff_plan_id="tariff-1",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime.now(timezone.utc),
    )
    acknowledgement = DocumentAcknowledgement(
        tenant_id=1,
        client_id=client.id,
        document_type="OFFER",
        document_id="doc-1",
    )
    db.add_all([contract, subscription, acknowledgement])
    db.commit()

    state = repository.initialize_onboarding_state(db, client_id=client.id)
    state.meta = {"cards_skipped": True, "first_operation_allowed": True}
    repository.upsert_onboarding_state(db, state)

    updated, facts = onboarding.recompute(db, client_id=client.id, request_ctx=None)
    assert facts.legal_accepted is True
    assert updated.state.value == "FIRST_OPERATION_ALLOWED"
    db.close()


def test_onboarding_blocks_without_legal():
    db = SessionLocal()
    client = CRMClient(
        id="client-2",
        tenant_id=1,
        legal_name="Client",
        tax_id=None,
        kpp=None,
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    db.add(client)
    db.commit()
    repository.initialize_onboarding_state(db, client_id=client.id)

    state, _facts = onboarding.advance(
        db,
        client_id=client.id,
        action=onboarding.OnboardingAction.SIGN_CONTRACT,
        request_ctx=None,
    )
    assert state.is_blocked is True
    assert state.block_reason == "legal_not_accepted"
    db.close()
