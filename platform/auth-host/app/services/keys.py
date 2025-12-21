from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

_PRIVATE_KEY_PEM: Optional[str] = None
_PUBLIC_KEY_PEM: Optional[str] = None
_KEY_LOCK = threading.Lock()

_DEFAULT_KEY_DIR = Path(os.getenv("AUTH_JWT_KEY_DIR", "/app/.keys"))
_PRIVATE_KEY_PATH = Path(os.getenv("AUTH_JWT_PRIVATE_KEY_PATH") or (_DEFAULT_KEY_DIR / "jwt_private.pem"))
_PUBLIC_KEY_PATH = Path(os.getenv("AUTH_JWT_PUBLIC_KEY_PATH") or (_DEFAULT_KEY_DIR / "jwt_public.pem"))


def _generate_rsa_key_pair() -> tuple[str, str]:
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


def _load_from_env() -> tuple[str | None, str | None]:
    private_key_env = os.getenv("AUTH_JWT_PRIVATE_KEY")
    public_key_env = os.getenv("AUTH_JWT_PUBLIC_KEY")
    return private_key_env, public_key_env


def _load_from_files() -> tuple[str | None, str | None]:
    private_key_file: str | None = None
    public_key_file: str | None = None

    try:
        if _PRIVATE_KEY_PATH.exists():
            private_key_file = _PRIVATE_KEY_PATH.read_text()

        if _PUBLIC_KEY_PATH.exists():
            public_key_file = _PUBLIC_KEY_PATH.read_text()

        if private_key_file and not public_key_file:
            private_key = serialization.load_pem_private_key(
                private_key_file.encode("utf-8"), password=None
            )
            public_key_file = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

        if private_key_file and public_key_file:
            return private_key_file, public_key_file
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning("Failed to load JWT keypair from disk: %s", exc)

    return None, None


def _persist_to_files(private_pem: str, public_pem: str) -> None:
    try:
        _PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PRIVATE_KEY_PATH.write_text(private_pem)
        _PUBLIC_KEY_PATH.write_text(public_pem)
    except OSError as exc:  # pragma: no cover - persistence best-effort
        logger.warning("Failed to persist JWT keypair to disk: %s", exc)


def _ensure_keys_loaded() -> None:
    global _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM

    if _PRIVATE_KEY_PEM and _PUBLIC_KEY_PEM:
        return

    with _KEY_LOCK:
        if _PRIVATE_KEY_PEM and _PUBLIC_KEY_PEM:
            return

        env_private, env_public = _load_from_env()
        if env_private:
            _PRIVATE_KEY_PEM = env_private
            if env_public:
                _PUBLIC_KEY_PEM = env_public
            else:
                private_key = serialization.load_pem_private_key(
                    env_private.encode("utf-8"), password=None
                )
                _PUBLIC_KEY_PEM = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("utf-8")
            return

        file_private, file_public = _load_from_files()
        if file_private and file_public:
            _PRIVATE_KEY_PEM = file_private
            _PUBLIC_KEY_PEM = file_public
            return

        _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM = _generate_rsa_key_pair()
        _persist_to_files(_PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM)


def get_private_key_pem() -> str:
    _ensure_keys_loaded()
    assert _PRIVATE_KEY_PEM is not None
    return _PRIVATE_KEY_PEM


def get_public_key_pem() -> str:
    _ensure_keys_loaded()
    assert _PUBLIC_KEY_PEM is not None
    return _PUBLIC_KEY_PEM
