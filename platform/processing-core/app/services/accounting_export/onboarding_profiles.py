from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


ONBOARDING_PROFILES_PATH = Path(__file__).resolve().parent / "onboarding_profiles.yaml"


class SftpConfig(BaseModel):
    host: str
    port: int = 22
    username: str
    auth_method: str = Field(default="password", description="password or key")
    password_env: str | None = None
    private_key_env: str | None = None
    private_key_passphrase_env: str | None = None
    remote_path: str = "/"
    timeout_seconds: int = 30
    retries: int = 3
    retry_backoff_seconds: int = 5

    model_config = ConfigDict(extra="forbid")

    def resolve_password(self) -> str | None:
        if not self.password_env:
            return None
        return os.getenv(self.password_env)

    def resolve_private_key(self) -> str | None:
        if not self.private_key_env:
            return None
        return os.getenv(self.private_key_env)

    def resolve_private_key_passphrase(self) -> str | None:
        if not self.private_key_passphrase_env:
            return None
        return os.getenv(self.private_key_passphrase_env)


class DeliveryConfig(BaseModel):
    sftp: SftpConfig | None = None

    model_config = ConfigDict(extra="forbid")


class OnboardingProfile(BaseModel):
    client_id: str
    erp_system: str
    erp_version: str | None = None
    export_format: str
    delivery_method: str
    timezone: str
    currency: str
    vat_rules: str
    decimal_policy: str
    delimiter: str
    encoding: str
    confirm_required: bool
    delivery: DeliveryConfig | None = None

    model_config = ConfigDict(extra="forbid")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if not isinstance(content, dict):
        raise ValueError(f"invalid onboarding profile file: {path}")
    return content


def _parse_profiles(payload: dict[str, Any]) -> dict[str, OnboardingProfile]:
    profiles_raw = payload.get("profiles", [])
    if not isinstance(profiles_raw, list):
        raise ValueError("profiles must be a list")
    profiles: dict[str, OnboardingProfile] = {}
    for profile in profiles_raw:
        if not isinstance(profile, dict):
            raise ValueError("profile must be a mapping")
        parsed = OnboardingProfile.model_validate(profile)
        profiles[parsed.client_id] = parsed
    return profiles


@lru_cache
def onboarding_profiles_index() -> dict[str, OnboardingProfile]:
    if not ONBOARDING_PROFILES_PATH.exists():
        return {}
    payload = _load_yaml(ONBOARDING_PROFILES_PATH)
    return _parse_profiles(payload)


def get_onboarding_profile(client_id: str) -> OnboardingProfile:
    profile = onboarding_profiles_index().get(client_id)
    if not profile:
        raise ValueError("onboarding_profile_not_found")
    return profile


def list_onboarding_profiles() -> list[OnboardingProfile]:
    return list(onboarding_profiles_index().values())


__all__ = ["OnboardingProfile", "SftpConfig", "get_onboarding_profile", "list_onboarding_profiles"]
