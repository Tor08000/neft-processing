from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"
if SHARED_PATH.exists():
    sys.path.append(str(SHARED_PATH))

from app.api.routes.auth import router
from app.services import keys


@pytest.fixture
def rsa_pair() -> Tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def key_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "keys"
    monkeypatch.setenv("AUTH_KEY_DIR", str(directory))
    monkeypatch.delenv("AUTH_JWT_KEY_DIR", raising=False)
    monkeypatch.delenv("AUTH_JWT_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("AUTH_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("AUTH_PUBLIC_KEY_PATH", raising=False)
    return directory


def _reset_keys_module(monkeypatch: pytest.MonkeyPatch, key_dir: Path | None = None) -> None:
    monkeypatch.delenv("AUTH_JWT_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("AUTH_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("AUTH_PUBLIC_KEY", raising=False)
    if key_dir:
        shutil.rmtree(key_dir, ignore_errors=True)
    import app.services as app_services

    sys.modules["app.services"] = app_services
    keys._PRIVATE_KEY_PEM = None
    keys._PUBLIC_KEY_PEM = None
    sys.modules["app.services.keys"] = keys


def test_keys_generated_when_env_missing(monkeypatch: pytest.MonkeyPatch, key_dir: Path):
    _reset_keys_module(monkeypatch, key_dir)
    importlib.reload(keys)

    private_pem = keys.get_private_key_pem()
    public_pem = keys.get_public_key_pem()

    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert private_pem != ""
    assert public_pem != ""


def test_keys_loaded_from_env(monkeypatch: pytest.MonkeyPatch, rsa_pair: Tuple[str, str], key_dir: Path):
    private_pem, public_pem = rsa_pair
    _reset_keys_module(monkeypatch, key_dir)
    monkeypatch.setenv("AUTH_JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY", public_pem)
    importlib.reload(keys)

    assert keys.get_private_key_pem() == private_pem
    assert keys.get_public_key_pem() == public_pem


def test_public_key_endpoint_returns_pem(monkeypatch: pytest.MonkeyPatch, rsa_pair: Tuple[str, str], key_dir: Path):
    private_pem, public_pem = rsa_pair
    _reset_keys_module(monkeypatch, key_dir)
    monkeypatch.setenv("AUTH_JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY", public_pem)
    importlib.reload(keys)

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)
    resp = client.get("/v1/auth/public-key")

    assert resp.status_code == 200
    assert resp.text == public_pem


def test_public_key_endpoint_stable(monkeypatch: pytest.MonkeyPatch, key_dir: Path):
    _reset_keys_module(monkeypatch, key_dir)
    importlib.reload(keys)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    first = client.get("/v1/auth/public-key")
    assert first.status_code == 200

    # simulate process restart: clear in-memory cache
    keys._PRIVATE_KEY_PEM = None
    keys._PUBLIC_KEY_PEM = None

    second = client.get("/v1/auth/public-key")

    assert second.status_code == 200
    assert second.text == first.text
