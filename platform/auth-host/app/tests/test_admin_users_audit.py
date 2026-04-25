from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes import admin_users
from app.lib import core_api
from app.schemas.admin_users import AdminUserCreateRequest, AdminUserUpdateRequest


def _request(*, path: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("utf-8"), value.encode("utf-8"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


class _FakeConn:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class _FakeCursor:
    def __init__(
        self,
        *,
        fetchone_results: list[dict | None] | None = None,
        fetchall_results: list[list[dict[str, str]]] | None = None,
    ) -> None:
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.executed: list[tuple[str, object | None]] = []

    async def execute(self, query: object, params: object | None = None) -> None:
        self.executed.append((str(query), params))

    async def fetchone(self) -> dict | None:
        if not self.fetchone_results:
            return None
        return self.fetchone_results.pop(0)

    async def fetchall(self) -> list[dict[str, str]]:
        if not self.fetchall_results:
            return []
        return self.fetchall_results.pop(0)


class _FakeConnFactory:
    def __init__(self, contexts: list[tuple[_FakeConn, _FakeCursor]]) -> None:
        self.contexts = contexts

    def __call__(self):
        conn, cur = self.contexts.pop(0)

        @asynccontextmanager
        async def _ctx():
            yield conn, cur

        return _ctx()


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, response: _FakeResponse, sink: dict[str, object], timeout: float) -> None:
        self._response = response
        self._sink = sink
        self._sink["timeout"] = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, *, json: dict, headers: dict[str, str]) -> _FakeResponse:
        self._sink["url"] = url
        self._sink["json"] = json
        self._sink["headers"] = headers
        return self._response


def test_emit_admin_user_audit_via_core_api_uses_internal_canonical_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(core_api, "CORE_API", "http://core-api:8000/api/v1")
    monkeypatch.setattr(
        core_api.httpx,
        "AsyncClient",
        lambda timeout=5.0: _FakeAsyncClient(
            response=_FakeResponse(200, {"status": "ok", "audit_id": "audit-1"}),
            sink=captured,
            timeout=timeout,
        ),
    )

    result = asyncio.run(
        core_api.emit_admin_user_audit_via_core_api(
            admin_bearer_token="Bearer admin-token",
            action="update",
            user_id="user-1",
            before={"roles": ["ANALYST"]},
            after={"roles": ["PLATFORM_ADMIN"]},
            reason="Rotate access",
            correlation_id="corr-admin-users-1",
            request_id="req-admin-users-1",
            trace_id="trace-admin-users-1",
        )
    )

    assert result == {"status": "ok", "audit_id": "audit-1"}
    assert captured["url"] == "http://core-api:8000/api/internal/admin/audit/users"
    assert captured["headers"] == {
        "Authorization": "Bearer admin-token",
        "Content-Type": "application/json",
        "x-request-id": "req-admin-users-1",
        "x-trace-id": "trace-admin-users-1",
    }
    assert captured["json"] == {
        "action": "update",
        "user_id": "user-1",
        "before": {"roles": ["ANALYST"]},
        "after": {"roles": ["PLATFORM_ADMIN"]},
        "reason": "Rotate access",
        "correlation_id": "corr-admin-users-1",
    }


def test_emit_admin_user_audit_via_core_api_fails_closed_on_core_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_api, "CORE_API", "http://core-api:8000/api/v1")
    monkeypatch.setattr(
        core_api.httpx,
        "AsyncClient",
        lambda timeout=5.0: _FakeAsyncClient(
            response=_FakeResponse(403, {"detail": "forbidden"}),
            sink={},
            timeout=timeout,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            core_api.emit_admin_user_audit_via_core_api(
                admin_bearer_token="Bearer admin-token",
                action="create",
                user_id="user-2",
                before=None,
                after={"roles": ["PLATFORM_ADMIN"]},
                reason="Create admin",
                correlation_id="corr-admin-users-2",
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "core_audit_rejected"


def test_create_user_emits_admin_audit_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    created_at = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    tenant_id = "00000000-0000-0000-0000-000000000000"
    primary_conn = _FakeConn()
    primary_cursor = _FakeCursor(
        fetchone_results=[
            None,
            {
                "id": "user-100",
                "email": "admin100@neft.test",
                "full_name": "Admin 100",
                "is_active": True,
                "created_at": created_at,
            },
        ]
    )
    monkeypatch.setattr(
        admin_users,
        "get_conn",
        _FakeConnFactory(
            [
                (primary_conn, primary_cursor),
            ]
        ),
    )
    monkeypatch.setattr(admin_users, "hash_password", lambda value: f"hashed::{value}")

    captured: dict[str, object] = {}

    async def fake_emit(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "audit_id": "audit-created"}

    monkeypatch.setattr(admin_users, "emit_admin_user_audit_via_core_api", fake_emit)

    payload = AdminUserCreateRequest(
        email="admin100@neft.test",
        password="secret123",
        full_name="Admin 100",
        roles=["PLATFORM_ADMIN"],
        reason="Create platform admin for regional rollout",
        correlation_id="corr-admin-create-1",
    )

    result = asyncio.run(
        admin_users.create_user(
            payload,
            _request(
                path="/api/v1/admin/users",
                headers={
                    "authorization": "Bearer admin-token",
                    "x-request-id": "req-admin-create-1",
                    "x-trace-id": "trace-admin-create-1",
                },
            ),
            _admin={"sub": "admin-root", "roles": ["PLATFORM_ADMIN"], "tenant_id": tenant_id},
        )
    )

    assert result.id == "user-100"
    assert result.roles == ["PLATFORM_ADMIN"]
    assert primary_conn.commit_calls == 1
    assert primary_cursor.executed[0][1] == (tenant_id, "admin100@neft.test")
    insert_params = primary_cursor.executed[1][1]
    UUID(insert_params[0])
    assert insert_params[1:] == (tenant_id, "admin100@neft.test", "Admin 100", "hashed::secret123")
    assert captured == {
        "admin_bearer_token": "Bearer admin-token",
        "action": "create",
        "user_id": "user-100",
        "before": None,
        "after": {
            "email": "admin100@neft.test",
            "full_name": "Admin 100",
            "is_active": True,
            "roles": ["PLATFORM_ADMIN"],
        },
        "reason": "Create platform admin for regional rollout",
        "correlation_id": "corr-admin-create-1",
        "request_id": "req-admin-create-1",
        "trace_id": "trace-admin-create-1",
    }


def test_update_user_emits_before_after_admin_audit_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    created_at = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
    primary_conn = _FakeConn()
    primary_cursor = _FakeCursor(
        fetchone_results=[
            {
                "id": "user-200",
                "email": "support200@neft.test",
                "full_name": "Support 200",
                "is_active": True,
                "created_at": created_at,
            },
            {
                "id": "user-200",
                "email": "support200@neft.test",
                "full_name": "Support Lead",
                "is_active": False,
                "created_at": created_at,
            },
        ],
        fetchall_results=[[{"role_code": "ANALYST"}]],
    )
    monkeypatch.setattr(
        admin_users,
        "get_conn",
        _FakeConnFactory(
            [
                (primary_conn, primary_cursor),
            ]
        ),
    )

    captured: dict[str, object] = {}

    async def fake_emit(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "audit_id": "audit-updated"}

    monkeypatch.setattr(admin_users, "emit_admin_user_audit_via_core_api", fake_emit)

    payload = AdminUserUpdateRequest(
        full_name="Support Lead",
        is_active=False,
        roles=["NEFT_SUPPORT"],
        reason="Promote analyst to support admin",
        correlation_id="corr-admin-update-1",
    )

    result = asyncio.run(
        admin_users.update_user(
            "user-200",
            payload,
            _request(
                path="/api/v1/admin/users/user-200",
                headers={"authorization": "Bearer admin-token", "x-request-id": "req-admin-update-1"},
            ),
            _admin={"sub": "platform-admin", "roles": ["PLATFORM_ADMIN"]},
        )
    )

    assert result.id == "user-200"
    assert result.roles == ["NEFT_SUPPORT"]
    assert primary_conn.commit_calls == 1
    assert captured == {
        "admin_bearer_token": "Bearer admin-token",
        "action": "update",
        "user_id": "user-200",
        "before": {
            "email": "support200@neft.test",
            "full_name": "Support 200",
            "is_active": True,
            "roles": ["ANALYST"],
        },
        "after": {
            "email": "support200@neft.test",
            "full_name": "Support Lead",
            "is_active": False,
            "roles": ["NEFT_SUPPORT"],
        },
        "reason": "Promote analyst to support admin",
        "correlation_id": "corr-admin-update-1",
        "request_id": "req-admin-update-1",
        "trace_id": None,
    }
