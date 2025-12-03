from __future__ import annotations

import os
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_PRIVATE_KEY_PEM: Optional[str] = None
_PUBLIC_KEY_PEM: Optional[str] = None


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


def _ensure_keys_loaded() -> None:
    global _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM

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

    _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM = _generate_rsa_key_pair()


def get_private_key_pem() -> str:
    _ensure_keys_loaded()
    assert _PRIVATE_KEY_PEM is not None
    return _PRIVATE_KEY_PEM


def get_public_key_pem() -> str:
    _ensure_keys_loaded()
    assert _PUBLIC_KEY_PEM is not None
    return _PUBLIC_KEY_PEM
