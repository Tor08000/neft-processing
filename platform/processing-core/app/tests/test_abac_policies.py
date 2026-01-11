from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.abac import AbacPolicy, AbacPolicyEffect, AbacPolicyVersion, AbacPolicyVersionStatus
from app.services.abac import AbacContext, AbacEngine, AbacPrincipal, AbacResource


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_version(session):
    version = AbacPolicyVersion(
        name="default",
        status=AbacPolicyVersionStatus.ACTIVE,
        activated_at=datetime.now(timezone.utc),
    )
    session.add(version)
    session.flush()
    return version


def test_abac_permissions_matrix(db_session):
    version = _seed_version(db_session)
    db_session.add_all(
        [
            AbacPolicy(
                version_id=version.id,
                code="documents_owner_allow",
                effect=AbacPolicyEffect.ALLOW,
                priority=100,
                actions=["documents:download"],
                resource_type="DOCUMENT",
                condition={
                    "all": [
                        {"eq": ["principal.type", "CLIENT"]},
                        {"eq": ["resource.owner_client_id", "principal.client_id"]},
                    ]
                },
                reason_code="DOC_OWNER",
            ),
            AbacPolicy(
                version_id=version.id,
                code="documents_partner_deny",
                effect=AbacPolicyEffect.DENY,
                priority=200,
                actions=["documents:download"],
                resource_type="DOCUMENT",
                condition={"eq": ["principal.type", "PARTNER"]},
                reason_code="PARTNER_DOCS_DENY",
            ),
            AbacPolicy(
                version_id=version.id,
                code="finance_cfo_allow",
                effect=AbacPolicyEffect.ALLOW,
                priority=50,
                actions=["finance:dashboard"],
                resource_type="FINANCE_DASHBOARD",
                condition={"contains": ["principal.roles", "CFO"]},
                reason_code="FINANCE_CFO",
            ),
            AbacPolicy(
                version_id=version.id,
                code="bi_region_allow",
                effect=AbacPolicyEffect.ALLOW,
                priority=70,
                actions=["bi:read"],
                resource_type="BI_SCOPE",
                condition={"in": ["context.region", ["RU-MOW"]]},
                reason_code="BI_REGION",
            ),
            AbacPolicy(
                version_id=version.id,
                code="override_allow",
                effect=AbacPolicyEffect.ALLOW,
                priority=100,
                actions=["payouts:export"],
                resource_type="PAYOUT_BATCH",
                condition={"exists": ["principal.type"]},
                reason_code="OVERRIDE_ALLOW",
            ),
            AbacPolicy(
                version_id=version.id,
                code="override_deny",
                effect=AbacPolicyEffect.DENY,
                priority=100,
                actions=["payouts:export"],
                resource_type="PAYOUT_BATCH",
                condition={"exists": ["principal.type"]},
                reason_code="OVERRIDE_DENY",
            ),
        ]
    )
    db_session.commit()

    engine = AbacEngine(db_session)
    context = AbacContext(ip=None, region="RU-MOW", timestamp=datetime.now(timezone.utc))

    principal_client = AbacPrincipal(
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
    resource_doc = AbacResource("DOCUMENT", {"owner_client_id": "client-1"})
    decision = engine.evaluate(
        principal=principal_client,
        action="documents:download",
        resource=resource_doc,
        entitlements={},
        context=context,
    )
    assert decision.allowed is True

    resource_doc_other = AbacResource("DOCUMENT", {"owner_client_id": "client-2"})
    decision = engine.evaluate(
        principal=principal_client,
        action="documents:download",
        resource=resource_doc_other,
        entitlements={},
        context=context,
    )
    assert decision.allowed is False

    principal_partner = AbacPrincipal(
        type="PARTNER",
        user_id=None,
        client_id=None,
        partner_id="partner-1",
        service_name=None,
        roles=set(),
        scopes=set(),
        region=None,
        raw={},
    )
    decision = engine.evaluate(
        principal=principal_partner,
        action="documents:download",
        resource=resource_doc,
        entitlements={},
        context=context,
    )
    assert decision.allowed is False

    principal_cfo = AbacPrincipal(
        type="USER",
        user_id="user-2",
        client_id=None,
        partner_id=None,
        service_name=None,
        roles={"CFO"},
        scopes=set(),
        region=None,
        raw={},
    )
    decision = engine.evaluate(
        principal=principal_cfo,
        action="finance:dashboard",
        resource=AbacResource("FINANCE_DASHBOARD", {}),
        entitlements={},
        context=context,
    )
    assert decision.allowed is True

    decision = engine.evaluate(
        principal=principal_client,
        action="finance:dashboard",
        resource=AbacResource("FINANCE_DASHBOARD", {}),
        entitlements={},
        context=context,
    )
    assert decision.allowed is False

    decision = engine.evaluate(
        principal=principal_cfo,
        action="payouts:export",
        resource=AbacResource("PAYOUT_BATCH", {}),
        entitlements={},
        context=context,
    )
    assert decision.allowed is False

    principal_service = AbacPrincipal(
        type="SERVICE",
        user_id=None,
        client_id=None,
        partner_id=None,
        service_name="bi-worker",
        roles=set(),
        scopes={"bi:sync"},
        region=None,
        raw={},
    )
    deny_context = AbacContext(ip=None, region="RU-SPE", timestamp=datetime.now(timezone.utc))
    decision = engine.evaluate(
        principal=principal_service,
        action="bi:read",
        resource=AbacResource("BI_SCOPE", {"scope_type": "CLIENT", "scope_id": "client-1"}),
        entitlements={},
        context=deny_context,
    )
    assert decision.allowed is False

    allow_context = AbacContext(ip=None, region="RU-MOW", timestamp=datetime.now(timezone.utc))
    decision = engine.evaluate(
        principal=principal_service,
        action="bi:read",
        resource=AbacResource("BI_SCOPE", {"scope_type": "CLIENT", "scope_id": "client-1"}),
        entitlements={},
        context=allow_context,
    )
    assert decision.allowed is True
