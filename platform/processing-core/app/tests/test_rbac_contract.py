from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import admin_auth, client_auth, partner_auth
from app.services.marketplace_orders_service import MarketplaceOrdersService, MarketplaceOrdersServiceError


@pytest.fixture(autouse=True)
def _stub_session_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_auth, "ensure_session_active", lambda payload: None)
    monkeypatch.setattr(partner_auth, "ensure_session_active", lambda payload: None)
    monkeypatch.setattr(admin_auth, "ensure_session_active", lambda payload: None)


def test_client_guard_allows_client_me(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(
        client_auth,
        "_decode_token",
        lambda token, key: {"sub": "client-user", "roles": ["CLIENT_USER"], "client_id": "org-A"},
    )

    payload = client_auth.verify_client_token("client-token")

    assert payload["client_id"] == "org-A"


def test_client_guard_denies_partner_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(
        client_auth,
        "_decode_token",
        lambda token, key: {"sub": "partner-user", "portal": "client", "roles": ["PARTNER_USER"], "partner_id": "p-1"},
    )

    with pytest.raises(HTTPException) as exc:
        client_auth.verify_client_token("partner-token")

    assert exc.value.status_code == 403


def test_partner_guard_allows_partner_me(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(partner_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(
        partner_auth,
        "_decode_token",
        lambda token, key: {"sub": "partner-user", "roles": ["PARTNER_MANAGER"], "partner_id": "partner-A"},
    )

    payload = partner_auth.verify_partner_token("partner-token")

    assert payload["partner_id"] == "partner-A"


def test_partner_guard_denies_client_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(partner_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(
        partner_auth,
        "_decode_token",
        lambda token, key: {"sub": "client-user", "portal": "partner", "roles": ["CLIENT_USER"], "client_id": "org-A"},
    )

    with pytest.raises(HTTPException) as exc:
        partner_auth.verify_partner_token("client-token")

    assert exc.value.status_code == 403


def test_admin_guard_allows_admin_verify_me(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(admin_auth, "_decode_token", lambda token, key: {"sub": "admin-user", "roles": ["PLATFORM_ADMIN"]})

    payload = admin_auth.verify_admin_token("admin-token")

    assert payload["sub"] == "admin-user"


def test_admin_guard_denies_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "_resolve_public_key", lambda token, force_refresh=False: ("k", False, False))
    monkeypatch.setattr(admin_auth, "_decode_token", lambda token, key: {"sub": "client-user", "portal": "admin", "roles": ["CLIENT_USER"]})

    with pytest.raises(HTTPException) as exc:
        admin_auth.verify_admin_token("client-token")

    assert exc.value.status_code == 403


def test_scope_client_org_mismatch_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketplaceOrdersService(db=None)
    monkeypatch.setattr(
        service,
        "_resolve_order",
        lambda **kwargs: SimpleNamespace(id="ord-1", client_id="org-B", partner_id="partner-A"),
    )

    with pytest.raises(MarketplaceOrdersServiceError) as exc:
        service.get_order_for_client(order_id="ord-1", client_id="org-A")

    assert str(exc.value) == "forbidden"


def test_scope_partner_id_mismatch_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketplaceOrdersService(db=None)
    monkeypatch.setattr(
        service,
        "_resolve_order",
        lambda **kwargs: SimpleNamespace(id="ord-2", client_id="org-A", partner_id="partner-B"),
    )

    with pytest.raises(MarketplaceOrdersServiceError) as exc:
        service.get_order_for_partner(order_id="ord-2", partner_id="partner-A")

    assert str(exc.value) == "forbidden"
