from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app import db
from app import bootstrap
from app.bootstrap import seed_demo_client_account
from app.demo import DEMO_CLIENT_EMAIL


@dataclass
class FakeDBState:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    clients: dict[str, dict[str, Any]] = field(default_factory=dict)
    statements: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0


class FakeCursor:
    def __init__(self, state: FakeDBState):
        self.state = state
        self.fetchone_result: Any | None = None

    async def execute(self, query: str, params: tuple[Any, ...] | None = None):
        params = params or tuple()
        normalized = " ".join(query.split())
        self.state.statements.append(normalized)

        if normalized.startswith("INSERT INTO users"):
            user_id, email, full_name, password_hash = params
            email_lower = email.lower()
            existing = self.state.users.get(email_lower)
            if existing:
                existing.update(
                    {
                        "full_name": full_name,
                        "password_hash": password_hash,
                        "is_active": True,
                    }
                )
                self.fetchone_result = {"id": existing["id"]}
            else:
                self.state.users[email_lower] = {
                    "id": str(user_id),
                    "email": email_lower,
                    "full_name": full_name,
                    "password_hash": password_hash,
                    "is_active": True,
                }
                self.fetchone_result = {"id": str(user_id)}
        elif normalized.startswith("INSERT INTO clients"):
            client_id, name, email, full_name = params
            self.state.clients[str(client_id)] = {
                "id": str(client_id),
                "name": name,
                "email": email,
                "full_name": full_name,
                "status": "ACTIVE",
            }
            self.fetchone_result = None
        elif normalized.startswith("SELECT id, full_name FROM clients"):
            email = params[0].lower()
            found = next(
                (c for c in self.state.clients.values() if c["email"].lower() == email),
                None,
            )
            self.fetchone_result = found and {"id": found["id"], "full_name": found.get("full_name")}
        elif normalized.startswith("SELECT id, email, full_name, password_hash"):
            email = params[0].lower()
            user = self.state.users.get(email)
            self.fetchone_result = (
                user
                and {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user.get("full_name"),
                    "password_hash": user.get("password_hash"),
                    "is_active": user.get("is_active", True),
                    "created_at": None,
                }
            )
        else:
            self.fetchone_result = None

    async def fetchone(self):
        return self.fetchone_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.fetchone_result = None
        return False


class FakeCursorManager:
    def __init__(self, cursor: FakeCursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        await self.cursor.__aexit__(exc_type, exc, tb)
        return False


class FakeConnection:
    def __init__(self, state: FakeDBState):
        self.state = state
        self.closed = False

    def cursor(self, *args, **kwargs):
        return FakeCursorManager(FakeCursor(self.state))

    async def commit(self):
        self.state.commits += 1

    async def rollback(self):
        self.state.rollbacks += 1

    async def close(self):
        self.closed = True


class FakeConnContext:
    def __init__(self, state: FakeDBState):
        self.state = state
        self.connection = FakeConnection(state)
        self.cursor = FakeCursor(state)

    async def __aenter__(self):
        return self.connection, self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        await self.connection.close()
        return False


@pytest.mark.anyio
async def test_init_db_runs_idempotently(monkeypatch):
    state = FakeDBState()

    async def fake_connect(_dsn):
        return FakeConnection(state)

    monkeypatch.setattr(db.psycopg.AsyncConnection, "connect", staticmethod(fake_connect))

    await db.init_db()
    await db.init_db()

    assert state.commits == 2
    assert any("CREATE TABLE IF NOT EXISTS users" in stmt for stmt in state.statements)
    assert any("CREATE TABLE IF NOT EXISTS clients" in stmt for stmt in state.statements)
    assert any("lower(email)" in stmt for stmt in state.statements)


@pytest.mark.anyio
async def test_seed_demo_client_account_idempotent(monkeypatch):
    state = FakeDBState()
    init_calls: list[int] = []

    async def fake_init_db():
        init_calls.append(1)

    monkeypatch.setattr(bootstrap, "init_db", fake_init_db)
    monkeypatch.setattr(bootstrap, "get_conn", lambda: FakeConnContext(state))

    await seed_demo_client_account()
    await seed_demo_client_account()

    assert len(state.users) == 1
    assert DEMO_CLIENT_EMAIL.lower() in state.users
    assert len(state.clients) == 1
    assert len(init_calls) == 2
    stored_user = state.users[DEMO_CLIENT_EMAIL.lower()]
    assert stored_user["password_hash"]
