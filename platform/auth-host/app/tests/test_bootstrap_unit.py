from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.bootstrap import bootstrap_admin_account, seed_demo_client_account
from app.settings import Settings


@dataclass
class _FakeState:
    users: list[dict[str, Any]]
    roles: set[tuple[str, str]]


class _FakeCursor:
    def __init__(self, state: _FakeState):
        self.state = state
        self._rows: list[dict[str, Any]] = []

    async def execute(self, query: str, params: tuple[Any, ...]):
        q = query.lower().strip()

        if "from users" in q:
            email = params[0].lower()
            user = next((u for u in self.state.users if u["email"].lower() == email), None)
            self._rows = [user] if user else []
        elif q.startswith("insert into users"):
            user_id, email, full_name, password_hash = params
            existing = next((u for u in self.state.users if u["email"].lower() == email.lower()), None)
            if not existing:
                self.state.users.append(
                    {
                        "id": user_id,
                        "email": email,
                        "full_name": full_name,
                        "password_hash": password_hash,
                        "is_active": True,
                    }
                )
                self._rows = [{"id": user_id}]
            else:
                self._rows = []
        elif q.startswith("update users set is_active"):
            user_id = params[0]
            for user in self.state.users:
                if user["id"] == user_id:
                    user["is_active"] = True
            self._rows = []
        elif q.startswith("update users set password_hash"):
            password_hash, user_id = params
            for user in self.state.users:
                if user["id"] == user_id:
                    user["password_hash"] = password_hash
            self._rows = []
        elif "from user_roles" in q:
            user_id = str(params[0])
            rows = [{"role": role} for uid, role in self.state.roles if str(uid) == user_id]
            self._rows = rows
        elif q.startswith("insert into user_roles"):
            user_id, role = params
            self.state.roles.add((user_id, role))
            self._rows = []
        else:
            self._rows = []

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, state: _FakeState):
        self.state = state

    async def commit(self):
        return None


class _FakeContext:
    def __init__(self, state: _FakeState):
        self.state = state

    async def __aenter__(self):
        return _FakeConn(self.state), _FakeCursor(self.state)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _patch_db(monkeypatch: pytest.MonkeyPatch, state: _FakeState):
    def _fake_get_conn():
        return _FakeContext(state)

    async def _fake_init_db():
        return None

    monkeypatch.setattr("app.bootstrap.get_conn", _fake_get_conn)
    monkeypatch.setattr("app.bootstrap.init_db", _fake_init_db)


@pytest.mark.anyio
async def test_bootstrap_admin_idempotent_without_db(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState(users=[], roles=set())
    _patch_db(monkeypatch, state)

    settings = Settings(
        bootstrap_admin_email="admin@neft.local",
        bootstrap_admin_password="pass1",
        bootstrap_admin_roles=["ADMIN", "SUPERADMIN"],
    )

    await bootstrap_admin_account(settings=settings)
    await bootstrap_admin_account(settings=settings)

    assert len(state.users) == 1
    user = state.users[0]
    assert user["email"] == "admin@neft.local"

    roles = {role for (_uid, role) in state.roles}
    assert roles == {"ADMIN", "SUPERADMIN"}


@pytest.mark.anyio
async def test_bootstrap_client_and_admin_without_db(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState(users=[], roles=set())
    _patch_db(monkeypatch, state)

    settings = Settings(
        demo_client_email="client@example.com",
        demo_client_password="client-pass",
        demo_client_full_name="Client",
        bootstrap_admin_email="root@example.com",
        bootstrap_admin_password="root-pass",
        bootstrap_admin_roles=["ADMIN"],
    )

    await seed_demo_client_account(settings)

    emails = {user["email"] for user in state.users}
    assert {"client@example.com", "root@example.com"} <= emails
    role_map = {}
    for user_id, role in state.roles:
        role_map.setdefault(user_id, set()).add(role)
    assert any("ADMIN" in roles for roles in role_map.values())
