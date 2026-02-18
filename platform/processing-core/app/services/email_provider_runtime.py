from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailProviderStartupConfig:
    mode: str
    strict: bool
    integration_hub_url: str
    timeout_seconds: int
    retries: int


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_env(environ: dict[str, str] | None = None) -> str:
    env = environ or os.environ
    return (env.get("APP_ENV") or "dev").strip().lower()


def get_email_provider_mode(environ: dict[str, str] | None = None) -> str:
    env = environ or os.environ
    raw_mode = (env.get("EMAIL_PROVIDER_MODE") or "").strip().lower()
    if raw_mode in {"disabled", "stub", "integration_hub"}:
        return raw_mode
    return "integration_hub" if _app_env(env) == "prod" else "stub"


def get_email_startup_strict(environ: dict[str, str] | None = None) -> bool:
    env = environ or os.environ
    raw = env.get("EMAIL_STARTUP_STRICT")
    if raw is None:
        return _app_env(env) == "prod"
    return _is_truthy(raw)


def load_email_provider_startup_config(environ: dict[str, str] | None = None) -> EmailProviderStartupConfig:
    env = environ or os.environ
    mode = get_email_provider_mode(env)
    strict = get_email_startup_strict(env)
    integration_hub_url = (env.get("INTEGRATION_HUB_URL") or "http://integration-hub:8080").rstrip("/")
    timeout_seconds = max(1, int(env.get("EMAIL_STARTUP_TIMEOUT_SECONDS", "3")))
    retries = max(1, int(env.get("EMAIL_STARTUP_RETRIES", "1")))
    return EmailProviderStartupConfig(
        mode=mode,
        strict=strict,
        integration_hub_url=integration_hub_url,
        timeout_seconds=timeout_seconds,
        retries=retries,
    )


_EMAIL_DEGRADED = False


def set_email_degraded(value: bool) -> None:
    global _EMAIL_DEGRADED
    _EMAIL_DEGRADED = bool(value)


def is_email_degraded() -> bool:
    return _EMAIL_DEGRADED


__all__ = [
    "EmailProviderStartupConfig",
    "get_email_provider_mode",
    "get_email_startup_strict",
    "is_email_degraded",
    "load_email_provider_startup_config",
    "set_email_degraded",
]
