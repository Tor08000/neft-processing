from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from neft_shared.settings import Settings as SharedSettings


def _env_or_default(key: str, default: str, *, fallback_keys: Iterable[str] = ()) -> str:
    for candidate in (key, *fallback_keys):
        value = os.getenv(candidate)
        if value is not None:
            return value
    return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(key: str, default: int, *, fallback_keys: Iterable[str] = ()) -> int:
    for candidate in (key, *fallback_keys):
        raw = os.getenv(candidate)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    return default


def _roles_env(key: str, default: list[str], *, fallback_keys: Iterable[str] = ()) -> list[str]:
    for candidate in (key, *fallback_keys):
        raw = os.getenv(candidate)
        if raw:
            return [part.strip() for part in raw.split(",") if part.strip()]
    return default


def _path_env(key: str, default: str, *, fallback_keys: Iterable[str] = ()) -> str:
    for candidate in (key, *fallback_keys):
        raw = os.getenv(candidate)
        if raw:
            return raw
    return default


@dataclass
class Settings(SharedSettings):
    core_api: str = _env_or_default("CORE_API_URL", "http://core-api:8000/api/v1")
    ai_url: str = _env_or_default("AI_URL", "http://ai-service:8000")
    tenant_id: int = int(_env_or_default("TENANT_ID", "1"))
    service_token: str = _env_or_default("SERVICE_TOKEN", "svc-dev")
    auth_issuer: str = _env_or_default("NEFT_AUTH_ISSUER", "neft-auth", fallback_keys=("AUTH_ISSUER",))
    auth_audience: str = _env_or_default("NEFT_AUTH_AUDIENCE", "neft-admin", fallback_keys=("AUTH_AUDIENCE",))
    auth_client_issuer: str = _env_or_default(
        "NEFT_CLIENT_ISSUER",
        "neft-client",
        fallback_keys=("CLIENT_AUTH_ISSUER",),
    )
    auth_client_audience: str = _env_or_default(
        "NEFT_CLIENT_AUDIENCE",
        "neft-client",
        fallback_keys=("CLIENT_AUTH_AUDIENCE",),
    )
    auth_key_dir: str = _env_or_default("AUTH_KEY_DIR", "/app/.keys", fallback_keys=("AUTH_JWT_KEY_DIR",))
    auth_private_key_path: str = field(
        default_factory=lambda: _path_env(
            "AUTH_PRIVATE_KEY_PATH",
            str(Path(_env_or_default("AUTH_KEY_DIR", "/app/.keys", fallback_keys=("AUTH_JWT_KEY_DIR",))) / "jwt_private.pem"),
            fallback_keys=("AUTH_JWT_PRIVATE_KEY_PATH",),
        )
    )
    auth_public_key_path: str = field(
        default_factory=lambda: _path_env(
            "AUTH_PUBLIC_KEY_PATH",
            str(Path(_env_or_default("AUTH_KEY_DIR", "/app/.keys", fallback_keys=("AUTH_JWT_KEY_DIR",))) / "jwt_public.pem"),
            fallback_keys=("AUTH_JWT_PUBLIC_KEY_PATH",),
        )
    )

    demo_client_email: str = _env_or_default(
        "NEFT_DEMO_CLIENT_EMAIL",
        "client@neft.local",
        fallback_keys=("DEMO_CLIENT_EMAIL",),
    )
    demo_client_password: str = _env_or_default(
        "NEFT_DEMO_CLIENT_PASSWORD", "client", fallback_keys=("DEMO_CLIENT_PASSWORD",)
    )
    demo_client_id: str = _env_or_default(
        "NEFT_DEMO_CLIENT_ID", "demo-client", fallback_keys=("DEMO_CLIENT_ID",)
    )
    demo_org_id: int = _env_int("NEFT_DEMO_ORG_ID", 1, fallback_keys=("DEMO_ORG_ID",))
    demo_client_full_name: str = _env_or_default(
        "NEFT_DEMO_CLIENT_FULL_NAME",
        "Demo Client",
        fallback_keys=("DEMO_CLIENT_FULL_NAME",),
    )
    demo_client_uuid: str = _env_or_default(
        "NEFT_DEMO_CLIENT_UUID",
        "00000000-0000-0000-0000-000000000001",
        fallback_keys=("DEMO_CLIENT_UUID",),
    )

    demo_admin_email: str = _env_or_default(
        "NEFT_DEMO_ADMIN_EMAIL",
        "admin@example.com",
        fallback_keys=("DEMO_ADMIN_EMAIL",),
    )
    demo_admin_username: str = _env_or_default(
        "NEFT_DEMO_ADMIN_USERNAME",
        "admin",
        fallback_keys=("DEMO_ADMIN_USERNAME",),
    )
    demo_admin_password: str = _env_or_default(
        "NEFT_DEMO_ADMIN_PASSWORD", "admin123", fallback_keys=("DEMO_ADMIN_PASSWORD",)
    )
    demo_admin_full_name: str = _env_or_default(
        "NEFT_DEMO_ADMIN_FULL_NAME",
        "Platform Admin",
        fallback_keys=("DEMO_ADMIN_FULL_NAME",),
    )
    demo_admin_roles: list[str] = field(
        default_factory=lambda: _roles_env(
            "NEFT_DEMO_ADMIN_ROLES", ["ADMIN", "SUPERADMIN"], fallback_keys=("DEMO_ADMIN_ROLES",)
        )
    )
    demo_seed_force_password_reset: bool = _env_bool("DEMO_SEED_FORCE_PASSWORD_RESET", True)
    bootstrap_password_version: int = int(_env_or_default("NEFT_BOOTSTRAP_PASSWORD_VERSION", "1"))
    bootstrap_enabled: bool = _env_bool(
        "NEFT_BOOTSTRAP_ENABLED",
        _env_bool("DEMO_SEED_ENABLED", True),
    )
    bootstrap_admin_email: str = _env_or_default(
        "NEFT_BOOTSTRAP_ADMIN_EMAIL",
        _env_or_default("NEFT_DEMO_ADMIN_EMAIL", "admin@example.com", fallback_keys=("DEMO_ADMIN_EMAIL",)),
    )
    bootstrap_admin_username: str = _env_or_default(
        "NEFT_BOOTSTRAP_ADMIN_USERNAME",
        _env_or_default("NEFT_DEMO_ADMIN_USERNAME", "admin", fallback_keys=("DEMO_ADMIN_USERNAME",)),
    )
    bootstrap_admin_password: str = _env_or_default(
        "NEFT_BOOTSTRAP_ADMIN_PASSWORD",
        _env_or_default("NEFT_DEMO_ADMIN_PASSWORD", "admin123", fallback_keys=("DEMO_ADMIN_PASSWORD",)),
    )
    bootstrap_admin_full_name: str = _env_or_default(
        "NEFT_BOOTSTRAP_ADMIN_FULL_NAME",
        _env_or_default("NEFT_DEMO_ADMIN_FULL_NAME", "Platform Admin", fallback_keys=("DEMO_ADMIN_FULL_NAME",)),
    )
    bootstrap_admin_roles: list[str] = field(
        default_factory=lambda: _roles_env(
            "NEFT_BOOTSTRAP_ADMIN_ROLES",
            _roles_env("NEFT_DEMO_ADMIN_ROLES", ["ADMIN"], fallback_keys=("DEMO_ADMIN_ROLES",)),
        )
    )

    def __post_init__(self) -> None:
        self.core_api = _env_or_default("CORE_API_URL", self.core_api)
        self.ai_url = _env_or_default("AI_URL", self.ai_url)
        self.tenant_id = int(_env_or_default("TENANT_ID", str(self.tenant_id)))
        self.service_token = _env_or_default("SERVICE_TOKEN", self.service_token)
        self.auth_issuer = _env_or_default("NEFT_AUTH_ISSUER", self.auth_issuer, fallback_keys=("AUTH_ISSUER",))
        self.auth_audience = _env_or_default("NEFT_AUTH_AUDIENCE", self.auth_audience, fallback_keys=("AUTH_AUDIENCE",))
        self.auth_key_dir = _env_or_default("AUTH_KEY_DIR", self.auth_key_dir, fallback_keys=("AUTH_JWT_KEY_DIR",))
        self.auth_private_key_path = _path_env(
            "AUTH_PRIVATE_KEY_PATH",
            self.auth_private_key_path,
            fallback_keys=("AUTH_JWT_PRIVATE_KEY_PATH",),
        )
        self.auth_public_key_path = _path_env(
            "AUTH_PUBLIC_KEY_PATH",
            self.auth_public_key_path,
            fallback_keys=("AUTH_JWT_PUBLIC_KEY_PATH",),
        )

        self.demo_client_email = _env_or_default(
            "NEFT_DEMO_CLIENT_EMAIL", self.demo_client_email, fallback_keys=("DEMO_CLIENT_EMAIL",)
        )
        self.demo_client_password = _env_or_default(
            "NEFT_DEMO_CLIENT_PASSWORD", self.demo_client_password, fallback_keys=("DEMO_CLIENT_PASSWORD",)
        )
        self.demo_client_id = _env_or_default("NEFT_DEMO_CLIENT_ID", self.demo_client_id, fallback_keys=("DEMO_CLIENT_ID",))
        self.demo_org_id = _env_int("NEFT_DEMO_ORG_ID", self.demo_org_id, fallback_keys=("DEMO_ORG_ID",))
        self.demo_client_full_name = _env_or_default(
            "NEFT_DEMO_CLIENT_FULL_NAME", self.demo_client_full_name, fallback_keys=("DEMO_CLIENT_FULL_NAME",)
        )
        self.demo_client_uuid = _env_or_default(
            "NEFT_DEMO_CLIENT_UUID", self.demo_client_uuid, fallback_keys=("DEMO_CLIENT_UUID",)
        )

        self.demo_admin_email = _env_or_default(
            "NEFT_DEMO_ADMIN_EMAIL", self.demo_admin_email, fallback_keys=("DEMO_ADMIN_EMAIL",)
        )
        self.demo_admin_username = _env_or_default(
            "NEFT_DEMO_ADMIN_USERNAME", self.demo_admin_username, fallback_keys=("DEMO_ADMIN_USERNAME",)
        )
        self.demo_admin_password = _env_or_default(
            "NEFT_DEMO_ADMIN_PASSWORD", self.demo_admin_password, fallback_keys=("DEMO_ADMIN_PASSWORD",)
        )
        self.demo_admin_full_name = _env_or_default(
            "NEFT_DEMO_ADMIN_FULL_NAME", self.demo_admin_full_name, fallback_keys=("DEMO_ADMIN_FULL_NAME",)
        )
        self.demo_admin_roles = _roles_env(
            "NEFT_DEMO_ADMIN_ROLES", self.demo_admin_roles, fallback_keys=("DEMO_ADMIN_ROLES",)
        )
        self.demo_seed_force_password_reset = _env_bool(
            "DEMO_SEED_FORCE_PASSWORD_RESET", self.demo_seed_force_password_reset
        )

        self.bootstrap_password_version = int(
            _env_or_default("NEFT_BOOTSTRAP_PASSWORD_VERSION", str(self.bootstrap_password_version))
        )
        self.bootstrap_enabled = _env_bool(
            "NEFT_BOOTSTRAP_ENABLED",
            _env_bool("DEMO_SEED_ENABLED", self.bootstrap_enabled),
        )
        self.bootstrap_admin_email = _env_or_default(
            "NEFT_BOOTSTRAP_ADMIN_EMAIL", self.bootstrap_admin_email
        )
        self.bootstrap_admin_username = _env_or_default(
            "NEFT_BOOTSTRAP_ADMIN_USERNAME", self.bootstrap_admin_username
        )
        self.bootstrap_admin_password = _env_or_default(
            "NEFT_BOOTSTRAP_ADMIN_PASSWORD", self.bootstrap_admin_password
        )
        self.bootstrap_admin_full_name = _env_or_default(
            "NEFT_BOOTSTRAP_ADMIN_FULL_NAME", self.bootstrap_admin_full_name
        )
        self.bootstrap_admin_roles = _roles_env(
            "NEFT_BOOTSTRAP_ADMIN_ROLES", self.bootstrap_admin_roles
        )


def get_settings() -> Settings:
    return Settings()


settings = get_settings()

CORE_API = settings.core_api.rstrip("/")
AI_URL = settings.ai_url
TENANT = settings.tenant_id
REDIS_URL = settings.redis_url
SERVICE_TOKEN = settings.service_token
