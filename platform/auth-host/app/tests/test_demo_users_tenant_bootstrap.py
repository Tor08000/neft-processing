from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from app.seeds.demo_users import DemoUser, ensure_user


@dataclass
class _FakeConn:
    async def commit(self):
        return None


class _FakeCursor:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.user_id = uuid4()
        self.roles: set[str] = set()
        self._rows: list[dict[str, Any]] = []

    async def execute(self, query: str, params: tuple[Any, ...] | None = None):
        q = " ".join(query.lower().split())

        if "select to_regclass('public.tenants')" in q:
            self._rows = [{"reg": "public.tenants"}]
            return
        if q.startswith("insert into tenants"):
            self._rows = [{"id": self.tenant_id}]
            return
        if q.startswith("select id, email, username") and "from users" in q:
            self._rows = []
            return
        if q.startswith("insert into users"):
            # ensure tenant_id is present in values tuple
            assert params is not None
            assert params[1] == self.tenant_id
            self._rows = []
            return
        if q.startswith("select role_code from user_roles"):
            self._rows = [{"role_code": r} for r in self.roles]
            return
        if q.startswith("insert into user_roles"):
            assert params is not None
            self.roles.add(str(params[1]))
            self._rows = []
            return
        if q.startswith("delete from user_roles"):
            self._rows = []
            return

        raise AssertionError(f"Unexpected SQL: {query}")

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return list(self._rows)


class _FakeContext:
    def __init__(self, cursor: _FakeCursor):
        self.cursor = cursor

    async def __aenter__(self):
        return _FakeConn(), self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.anyio
async def test_ensure_user_resolves_and_uses_default_tenant(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    cursor = _FakeCursor(tenant_id)

    monkeypatch.setattr("app.seeds.demo_users.get_conn", lambda: _FakeContext(cursor))

    user = DemoUser(
        email="admin@example.com",
        username="admin",
        password="change-me",
        full_name="Platform Admin",
        roles=["ADMIN"],
    )

    status = await ensure_user(user, force_password=True, sync_roles=True)

    assert status == "created"
    assert "ADMIN" in cursor.roles
