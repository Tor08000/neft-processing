from app.services.policy import Action, ActorContext, PolicyEngine, ResourceContext


def test_admin_finance_can_finalize_period():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-1",
    )
    resource = ResourceContext(
        resource_type="BILLING_PERIOD",
        tenant_id=1,
        client_id=None,
        status="OPEN",
    )

    decision = engine.check(actor=actor, action=Action.BILLING_PERIOD_FINALIZE, resource=resource)

    assert decision.allowed


def test_client_cannot_finalize_period():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="CLIENT",
        tenant_id=1,
        client_id="client-1",
        roles={"CLIENT_OWNER"},
        user_id="client-user",
    )
    resource = ResourceContext(
        resource_type="BILLING_PERIOD",
        tenant_id=1,
        client_id=None,
        status="OPEN",
    )

    decision = engine.check(actor=actor, action=Action.BILLING_PERIOD_FINALIZE, resource=resource)

    assert not decision.allowed


def test_admin_without_finance_role_cannot_finalize_period():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN"},
        user_id="user-2",
    )
    resource = ResourceContext(
        resource_type="BILLING_PERIOD",
        tenant_id=1,
        client_id=None,
        status="OPEN",
    )

    decision = engine.check(actor=actor, action=Action.BILLING_PERIOD_FINALIZE, resource=resource)

    assert not decision.allowed


def test_finalize_denied_for_wrong_status():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-3",
    )
    resource = ResourceContext(
        resource_type="BILLING_PERIOD",
        tenant_id=1,
        client_id=None,
        status="FINALIZED",
    )

    decision = engine.check(actor=actor, action=Action.BILLING_PERIOD_FINALIZE, resource=resource)

    assert not decision.allowed


def test_document_acknowledge_requires_client_owner():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="CLIENT",
        tenant_id=1,
        client_id="client-1",
        roles={"CLIENT_ACCOUNTANT"},
        user_id="client-user",
    )
    resource = ResourceContext(
        resource_type="DOCUMENT",
        tenant_id=1,
        client_id="client-1",
        status="ISSUED",
    )

    decision = engine.check(actor=actor, action=Action.DOCUMENT_ACKNOWLEDGE, resource=resource)

    assert not decision.allowed


def test_document_finalize_requires_admin_finance():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-1",
    )
    resource = ResourceContext(
        resource_type="DOCUMENT",
        tenant_id=1,
        client_id="client-1",
        status="ACKNOWLEDGED",
    )

    decision = engine.check(actor=actor, action=Action.DOCUMENT_FINALIZE, resource=resource)

    assert decision.allowed


def test_document_send_for_signing_requires_admin_finance():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-1",
    )
    resource = ResourceContext(
        resource_type="DOCUMENT",
        tenant_id=1,
        client_id="client-1",
        status="ISSUED",
    )

    decision = engine.check(actor=actor, action=Action.DOCUMENT_SEND_FOR_SIGNING, resource=resource)

    assert decision.allowed


def test_document_finalize_with_signature_requires_admin_finance():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-1",
    )
    resource = ResourceContext(
        resource_type="DOCUMENT",
        tenant_id=1,
        client_id="client-1",
        status="ACKNOWLEDGED",
    )

    decision = engine.check(actor=actor, action=Action.DOCUMENT_FINALIZE_WITH_SIGNATURE, resource=resource)

    assert decision.allowed


def test_closing_package_finalize_denied_without_ack():
    engine = PolicyEngine()
    actor = ActorContext(
        actor_type="ADMIN",
        tenant_id=1,
        client_id=None,
        roles={"ADMIN_FINANCE"},
        user_id="user-1",
    )
    resource = ResourceContext(
        resource_type="CLOSING_PACKAGE",
        tenant_id=1,
        client_id="client-1",
        status="ISSUED",
    )

    decision = engine.check(actor=actor, action=Action.CLOSING_PACKAGE_FINALIZE, resource=resource)

    assert not decision.allowed
