from app.services.client_entitlements import build_client_entitlements


def test_entitlements_disabled_when_org_not_active():
    result = build_client_entitlements(
        roles=["OWNER"],
        org_status="ONBOARDING",
        modules={"FLEET": {"enabled": True}},
        limits={"max_cards": {"value_int": 5}},
        role_entitlements=[{"scope": "all"}],
    )

    assert result.enabled_modules == []
    assert result.permissions == []
    assert result.limits["max_cards"]["value_int"] == 5
    assert result.org_status == "ONBOARDING"


def test_entitlements_union_roles_and_subscription():
    result = build_client_entitlements(
        roles=["CLIENT_ADMIN", "CLIENT_ACCOUNTANT"],
        org_status="ACTIVE",
        modules={"FLEET": {"enabled": True}, "DOCS": {"enabled": False}},
        limits={"max_cards": {"value_int": 10}},
        role_entitlements=[{"permissions": ["exports:view"]}],
    )

    assert result.enabled_modules == ["FLEET"]
    assert "exports:view" in result.permissions
    assert "*" in result.permissions
