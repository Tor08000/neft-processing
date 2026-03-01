from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.main import app


class _FakeCursor:
    def __init__(self, sid: UUID):
        self.sid = sid
        self._rows: list[dict[str, Any]] = []

    async def execute(self, query: str, params: tuple[Any, ...]):
        q = query.lower().strip()
        if "from auth_sessions" in q:
            self._rows = [
                {
                    "id": self.sid,
                    "revoked_at": None,
                    "revocation_reason": None,
                }
            ]
            return
        self._rows = []

    async def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    async def commit(self):
        return None


class _FakeContext:
    def __init__(self, sid: UUID):
        self.sid = sid

    async def __aenter__(self):
        return _FakeConn(), _FakeCursor(self.sid)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_session_status_returns_200_and_sid_as_string(monkeypatch: pytest.MonkeyPatch):
    sid = uuid4()

    def _fake_get_conn():
        return _FakeContext(sid)

    monkeypatch.setattr(auth, "get_conn", _fake_get_conn)

    response = TestClient(app).get(f"/api/v1/auth/sessions/{sid}/status")

    assert response.status_code == 200
    payload = response.json()
    assert "sid" in payload
    assert isinstance(payload["sid"], str)
    assert payload["sid"] == str(sid)
