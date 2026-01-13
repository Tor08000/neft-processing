from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from app.settings import get_settings

logger = logging.getLogger(__name__)

_PRIVATE_KEY_PEM: Optional[str] = None
_PUBLIC_KEY_PEM: Optional[str] = None
_KEY_ERROR: Optional[str] = None
_KEY_LOCK = threading.Lock()

settings = get_settings()

_DEFAULT_KEY_DIR = Path(settings.auth_key_dir or "/app/.keys")
_PRIVATE_KEY_PATH = Path(settings.auth_private_key_path or (_DEFAULT_KEY_DIR / "jwt_private.pem"))
_PUBLIC_KEY_PATH = Path(settings.auth_public_key_path or (_DEFAULT_KEY_DIR / "jwt_public.pem"))


class InvalidRSAKeyError(RuntimeError):
    pass


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


def _validate_private_key(private_pem: str) -> rsa.RSAPrivateKey:
    try:
        private_key = serialization.load_pem_private_key(
            private_pem.encode("utf-8"), password=None
        )
    except Exception as exc:  # pragma: no cover - defensive logging only
        raise InvalidRSAKeyError("invalid_rsa_private_key") from exc
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise InvalidRSAKeyError("invalid_rsa_private_key")
    if private_key.key_size < 2048:
        raise InvalidRSAKeyError("rsa_key_too_small")
    return private_key


def _validate_public_key(public_pem: str) -> rsa.RSAPublicKey:
    try:
        public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive logging only
        raise InvalidRSAKeyError("invalid_rsa_public_key") from exc
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise InvalidRSAKeyError("invalid_rsa_public_key")
    if public_key.key_size < 2048:
        raise InvalidRSAKeyError("rsa_key_too_small")
    return public_key


def _validate_key_pair(private_pem: str, public_pem: str) -> None:
    private_key = _validate_private_key(private_pem)
    public_key = _validate_public_key(public_pem)
    if private_key.public_key().public_numbers() != public_key.public_numbers():
        raise InvalidRSAKeyError("rsa_keypair_mismatch")


def _load_from_env() -> tuple[str | None, str | None]:
    private_key_env = os.getenv("AUTH_JWT_PRIVATE_KEY") or os.getenv("AUTH_PRIVATE_KEY")
    public_key_env = os.getenv("AUTH_JWT_PUBLIC_KEY") or os.getenv("AUTH_PUBLIC_KEY")
    return private_key_env, public_key_env


def _load_from_files() -> tuple[str | None, str | None]:
    if not _PRIVATE_KEY_PATH.exists() or not _PUBLIC_KEY_PATH.exists():
        return None, None

    try:
        private_key_file = _PRIVATE_KEY_PATH.read_text()
        public_key_file = _PUBLIC_KEY_PATH.read_text()
        _validate_key_pair(private_key_file, public_key_file)
        return private_key_file, public_key_file
    except InvalidRSAKeyError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning("Failed to load JWT keypair from disk: %s", exc)
        return None, None


def _persist_to_files(private_pem: str, public_pem: str) -> None:
    try:
        _PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PRIVATE_KEY_PATH.write_text(private_pem)
        _PUBLIC_KEY_PATH.write_text(public_pem)
        _PRIVATE_KEY_PATH.chmod(0o600)
        _PUBLIC_KEY_PATH.chmod(0o644)
    except OSError as exc:  # pragma: no cover - persistence best-effort
        logger.warning("Failed to persist JWT keypair to disk: %s", exc)


def _ensure_keys_loaded() -> None:
    global _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM, _KEY_ERROR

    if _PRIVATE_KEY_PEM and _PUBLIC_KEY_PEM:
        return
    if _KEY_ERROR:
        return

    with _KEY_LOCK:
        if _PRIVATE_KEY_PEM and _PUBLIC_KEY_PEM:
            return
        if _KEY_ERROR:
            return

        env_private, env_public = _load_from_env()
        if env_private or env_public:
            try:
                if not env_private:
                    raise InvalidRSAKeyError("missing_private_key")
                private_key = _validate_private_key(env_private)
                if env_public:
                    _validate_key_pair(env_private, env_public)
                    _PUBLIC_KEY_PEM = env_public
                else:
                    _PUBLIC_KEY_PEM = private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    ).decode("utf-8")
                _PRIVATE_KEY_PEM = env_private
                return
            except InvalidRSAKeyError as exc:
                _KEY_ERROR = str(exc)
                logger.error("auth-host: invalid RSA keys from env: %s", exc)
                return

        try:
            file_private, file_public = _load_from_files()
            if file_private and file_public:
                _PRIVATE_KEY_PEM = file_private
                _PUBLIC_KEY_PEM = file_public
                logger.info("[keys] keys already exist at %s", _PRIVATE_KEY_PATH.parent)
                return
        except InvalidRSAKeyError as exc:
            _KEY_ERROR = str(exc)
            logger.error("auth-host: invalid RSA keypair at %s", _PRIVATE_KEY_PATH.parent)
            return

        _PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM = _generate_rsa_key_pair()
        _persist_to_files(_PRIVATE_KEY_PEM, _PUBLIC_KEY_PEM)
        logger.info("auth-host: generated RSA keypair at %s", _PRIVATE_KEY_PATH.parent)


def get_private_key_pem() -> str:
    _ensure_keys_loaded()
    if _KEY_ERROR:
        raise InvalidRSAKeyError(_KEY_ERROR)
    assert _PRIVATE_KEY_PEM is not None
    return _PRIVATE_KEY_PEM


def get_public_key_pem() -> str:
    _ensure_keys_loaded()
    if _KEY_ERROR:
        raise InvalidRSAKeyError(_KEY_ERROR)
    assert _PUBLIC_KEY_PEM is not None
    return _PUBLIC_KEY_PEM


def initialize_keys() -> None:
    _ensure_keys_loaded()


def validate_keypair_files() -> tuple[bool, str | None]:
    if _KEY_ERROR:
        return False, "invalid_rsa_keys"
    if not _PRIVATE_KEY_PATH.exists() or not _PUBLIC_KEY_PATH.exists():
        return False, None

    try:
        private_pem = _PRIVATE_KEY_PATH.read_text()
        public_pem = _PUBLIC_KEY_PATH.read_text()
        _validate_key_pair(private_pem, public_pem)
    except InvalidRSAKeyError:
        return False, "invalid_rsa_keys"
    except Exception:
        return False, "invalid_rsa_keys"

    return True, None
