from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.routes.admin_users import _require_admin


@pytest.mark.asyncio
async def test_admin_endpoint_allows_platform_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.admin_users.decode_access_token",
        lambda _: {"sub": "admin@example.com", "roles": ["PLATFORM_ADMIN"]},
    )

    payload = await _require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="admin-token"))

    assert payload["sub"] == "admin@example.com"


@pytest.mark.asyncio
async def test_admin_endpoint_denies_client_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.admin_users.decode_access_token",
        lambda _: {"sub": "client@example.com", "roles": ["CLIENT_USER"]},
    )

    with pytest.raises(HTTPException) as exc:
        await _require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="client-token"))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_denies_partner_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.admin_users.decode_access_token",
        lambda _: {"sub": "partner@example.com", "roles": ["PARTNER_USER"]},
    )

    with pytest.raises(HTTPException) as exc:
        await _require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="partner-token"))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_protected_dependency_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc:
        await _require_admin(None)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_protected_dependency_rejects_wrong_auth_scheme() -> None:
    with pytest.raises(HTTPException) as exc:
        await _require_admin(HTTPAuthorizationCredentials(scheme="Basic", credentials="not-a-bearer"))

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_protected_dependency_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> dict:
        raise HTTPException(status_code=401, detail="invalid_token")

    monkeypatch.setattr("app.api.routes.admin_users.decode_access_token", _raise)

    with pytest.raises(HTTPException) as exc:
        await _require_admin(HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token"))

    assert exc.value.status_code == 401
