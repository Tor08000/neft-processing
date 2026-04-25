from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.abac import AbacPolicy, AbacPolicyEffect, AbacPolicyVersion, AbacPolicyVersionStatus
from app.services.abac import AbacContext, AbacEngine, AbacPrincipal, AbacResource


@pytest.fixture(autouse=True)
def clean_db():
    tables = [AbacPolicyVersion.__table__, AbacPolicy.__table__]
    Base.metadata.drop_all(bind=engine, tables=tables)
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_abac_explainability(db_session):
    version = AbacPolicyVersion(
        name="explain",
        status=AbacPolicyVersionStatus.ACTIVE,
        activated_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    db_session.flush()
    db_session.add(
        AbacPolicy(
            version_id=version.id,
            code="docs_owner_only",
            effect=AbacPolicyEffect.DENY,
            priority=100,
            actions=["documents:download"],
            resource_type="DOCUMENT",
            condition={"neq": ["resource.owner_client_id", "principal.client_id"]},
            reason_code="DOC_OWNER_ONLY",
        )
    )
    db_session.commit()

    engine = AbacEngine(db_session)
    principal = AbacPrincipal(
        type="CLIENT",
        user_id="user-1",
        client_id="client-1",
        partner_id=None,
        service_name=None,
        roles=set(),
        scopes=set(),
        region=None,
        raw={},
    )
    decision = engine.evaluate(
        principal=principal,
        action="documents:download",
        resource=AbacResource("DOCUMENT", {"owner_client_id": "client-2"}),
        entitlements={},
        context=AbacContext(ip=None, region=None, timestamp=datetime.now(timezone.utc)),
    )
    assert decision.allowed is False
    assert decision.reason_code == "DOC_OWNER_ONLY"
    assert any(item["code"] == "docs_owner_only" for item in decision.matched_policies)
    assert decision.explain.get("policy") == "docs_owner_only"
    assert decision.explain.get("condition") is not None
