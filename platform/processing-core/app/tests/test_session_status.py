from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import session_status


class _Resp:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class _Client:
    def __init__(self, response: _Resp):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, _url: str):
        return self._response


def test_ensure_session_active_rejects_revoked(monkeypatch: pytest.MonkeyPatch):
    session_status._cache.clear()
    monkeypatch.setattr(session_status.httpx, "Client", lambda timeout=2.0: _Client(_Resp(200, {"active": False})))

    with pytest.raises(HTTPException) as exc:
        session_status.ensure_session_active({"sid": "sid-1"})

    assert exc.value.status_code == 401
    assert exc.value.detail == "session_revoked"


def test_ensure_session_active_accepts_active(monkeypatch: pytest.MonkeyPatch):
    session_status._cache.clear()
    monkeypatch.setattr(session_status.httpx, "Client", lambda timeout=2.0: _Client(_Resp(200, {"active": True})))

    session_status.ensure_session_active({"sid": "sid-2"})
