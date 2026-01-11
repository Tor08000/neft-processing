from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SbisCredentials:
    base_url: str
    client_id: str | None = None
    client_secret: str | None = None
    app_id: str | None = None
    login: str | None = None
    password: str | None = None
    token: str | None = None
    certificate: str | None = None
    thumbprint: str | None = None
    private_key: str | None = None
    sender_box_id: str | None = None
    sender_inn: str | None = None
    token_url: str | None = None
    meta: dict | None = None


class CredentialsStore:
    def __init__(self) -> None:
        self._vault_hook = os.getenv("VAULT_HOOK_URL")

    def get_credentials(self, credentials_ref: str) -> SbisCredentials:
        raw = self._load_secret(credentials_ref)
        data = json.loads(raw)
        return SbisCredentials(
            base_url=data["base_url"],
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            app_id=data.get("app_id"),
            login=data.get("login"),
            password=data.get("password"),
            token=data.get("token"),
            certificate=data.get("certificate"),
            thumbprint=data.get("thumbprint"),
            private_key=data.get("private_key"),
            sender_box_id=data.get("sender_box_id"),
            sender_inn=data.get("sender_inn"),
            token_url=data.get("token_url"),
            meta=data.get("meta"),
        )

    def get_webhook_secret(self, webhook_secret_ref: str) -> str:
        return self._load_secret(webhook_secret_ref)

    def _load_secret(self, secret_ref: str) -> str:
        if secret_ref.startswith("env:"):
            env_key = secret_ref.split("env:", 1)[1]
            value = os.getenv(env_key)
            if value is None:
                raise RuntimeError(f"secret_not_found:{env_key}")
            return value
        if secret_ref.startswith("file:"):
            path = secret_ref.split("file:", 1)[1]
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        if secret_ref.startswith("vault:"):
            raise RuntimeError("vault_hook_not_configured")
        raise RuntimeError("unsupported_secret_ref")


__all__ = ["CredentialsStore", "SbisCredentials"]
