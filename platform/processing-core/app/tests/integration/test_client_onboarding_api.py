from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.feature_flags import FeatureFlag


@pytest.mark.integration
def test_client_onboarding_flow(make_jwt):
    session = get_sessionmaker()()
    try:
        session.query(ClientOnboardingContract).delete()
        session.query(ClientOnboarding).delete()
        session.query(FeatureFlag).filter(
            FeatureFlag.key.in_(["self_signup_enabled", "auto_activate_after_sign"])
        ).delete()
        session.commit()

        session.add(FeatureFlag(key="self_signup_enabled", on=True))
        session.add(FeatureFlag(key="auto_activate_after_sign", on=True))
        session.commit()
    finally:
        session.close()

    token = make_jwt(roles=("CLIENT_OWNER",), sub="user-123")
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        status = api_client.get("/api/core/client/onboarding/status")
        assert status.status_code == 200
        assert status.json() == {"step": "PROFILE", "status": "DRAFT", "client_type": None}

        profile_payload = {
            "name": "ACME LLC",
            "inn": "7700000000",
            "kpp": "770001001",
            "ogrn": "1234567890123",
            "address": "Moscow, Red Square",
            "contacts": {"email": "ops@acme.test"},
            "client_type": "LEGAL",
        }
        profile = api_client.post("/api/core/client/onboarding/profile", json=profile_payload)
        assert profile.status_code == 200
        assert profile.json() == {"step": "CONTRACT", "status": "DRAFT"}

        generate = api_client.post("/api/core/client/onboarding/contract/generate")
        assert generate.status_code == 200
        contract_payload = generate.json()
        assert contract_payload["contract_id"]
        assert contract_payload["pdf_url"]
        assert contract_payload["version"] == 1

        contract = api_client.get("/api/core/client/onboarding/contract")
        assert contract.status_code == 200
        assert contract.json()["status"] == "DRAFT"

        sign = api_client.post("/api/core/client/onboarding/contract/sign")
        assert sign.status_code == 200
        assert sign.json()["status"] == "ACTIVE"

    session = get_sessionmaker()()
    try:
        onboarding = (
            session.query(ClientOnboarding)
            .filter(ClientOnboarding.owner_user_id == "user-123")
            .one()
        )
        contract = (
            session.query(ClientOnboardingContract)
            .filter(ClientOnboardingContract.id == contract_payload["contract_id"])
            .one()
        )
        client = session.query(Client).filter(Client.id == onboarding.client_id).one()
        assert onboarding.status == "ACTIVE"
        assert onboarding.step == "ACTIVATION"
        assert contract.status == "SIGNED_SIMPLE"
        assert client.status == "ACTIVE"
    finally:
        session.close()
