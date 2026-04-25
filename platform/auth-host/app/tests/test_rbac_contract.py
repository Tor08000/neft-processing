from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.routes import admin_users
from app.api.routes.admin_users import _require_admin


def test_admin_endpoint_allows_platform_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_users, "decode_access_token", lambda _: {"sub": "admin@neft.local", "roles": ["PLATFORM_ADMIN"]})

    payload = asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="admin-token")))

    assert payload["sub"] == "admin@neft.local"


def test_admin_endpoint_allows_superadmin_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_users, "decode_access_token", lambda _: {"sub": "superadmin@example.com", "roles": ["NEFT_SUPERADMIN"]})

    payload = asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="superadmin-token")))

    assert payload["sub"] == "superadmin@example.com"


def test_admin_endpoint_denies_client_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_users, "decode_access_token", lambda _: {"sub": "client@example.com", "roles": ["CLIENT_USER"]})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="client-token")))

    assert exc.value.status_code == 403


def test_admin_endpoint_denies_finance_admin_without_access_management_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_users, "decode_access_token", lambda _: {"sub": "finance@example.com", "roles": ["NEFT_FINANCE"]})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="finance-token")))

    assert exc.value.status_code == 403


def test_admin_endpoint_denies_partner_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_users, "decode_access_token", lambda _: {"sub": "partner@example.com", "roles": ["PARTNER_USER"]})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="partner-token")))

    assert exc.value.status_code == 403


def test_protected_dependency_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(None))

    assert exc.value.status_code == 401


def test_protected_dependency_rejects_wrong_auth_scheme() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Basic", credentials="not-a-bearer")))

    assert exc.value.status_code == 401


def test_protected_dependency_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> dict:
        raise HTTPException(status_code=401, detail="invalid_token")

    monkeypatch.setattr(admin_users, "decode_access_token", _raise)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")))

    assert exc.value.status_code == 401
