from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")

import neft_integration_hub.main as main_module


def test_integration_hub_defaults_are_sandbox_contract_proof(monkeypatch) -> None:
    for env_name in (
        "DIADOK_MODE",
        "SBIS_MODE",
        "DIADOK_BASE_URL",
        "DIADOK_API_TOKEN",
        "OTP_PROVIDER_MODE",
        "NOTIFICATIONS_MODE",
        "EMAIL_PROVIDER_MODE",
    ):
        monkeypatch.delenv(env_name, raising=False)

    import neft_integration_hub.settings as settings_module

    settings_module = importlib.reload(settings_module)
    settings = settings_module.get_settings()

    assert settings.diadok_mode == "sandbox"
    assert settings.sbis_mode == "sandbox"
    assert settings.diadok_base_url == ""
    assert settings.otp_provider_mode == "sandbox"
    assert settings.notifications_mode == "sandbox"
    assert settings.email_provider_mode == "sandbox"


def test_provider_health_does_not_treat_placeholders_as_configured() -> None:
    original = {
        "diadok_mode": main_module.settings.diadok_mode,
        "diadok_base_url": main_module.settings.diadok_base_url,
        "diadok_api_token": main_module.settings.diadok_api_token,
        "webhook_intake_secret": main_module.settings.webhook_intake_secret,
        "webhook_allow_unsigned": main_module.settings.webhook_allow_unsigned,
    }
    try:
        object.__setattr__(main_module.settings, "diadok_mode", "real")
        object.__setattr__(main_module.settings, "diadok_base_url", "https://diadok.example.com")
        object.__setattr__(main_module.settings, "diadok_api_token", "change-me")
        object.__setattr__(main_module.settings, "webhook_intake_secret", "change-me")
        object.__setattr__(main_module.settings, "webhook_allow_unsigned", False)

        providers = {item["provider"]: item for item in main_module._external_provider_health()}

        assert providers["diadok"]["status"] == "DEGRADED"
        assert providers["diadok"]["configured"] is False
        assert providers["diadok"]["last_error_code"] == "diadok_not_configured"
        assert providers["sbis"]["status"] == "CONFIGURED"
        assert providers["sbis"]["configured"] is True
        assert providers["sbis"]["sandbox_proof"] is True
        assert providers["webhook_intake"]["status"] == "DEGRADED"
        assert providers["webhook_intake"]["configured"] is False
    finally:
        for name, value in original.items():
            object.__setattr__(main_module.settings, name, value)


def test_provider_health_exposes_sandbox_contract_proof() -> None:
    original = {
        "diadok_mode": main_module.settings.diadok_mode,
        "sbis_mode": main_module.settings.sbis_mode,
        "otp_provider_mode": main_module.settings.otp_provider_mode,
        "notifications_mode": main_module.settings.notifications_mode,
        "email_provider_mode": main_module.settings.email_provider_mode,
        "bank_api_mode": main_module.settings.bank_api_mode,
        "erp_1c_mode": main_module.settings.erp_1c_mode,
        "fuel_provider_mode": main_module.settings.fuel_provider_mode,
        "logistics_provider_mode": main_module.settings.logistics_provider_mode,
    }
    try:
        for name in original:
            object.__setattr__(main_module.settings, name, "sandbox")

        providers = {item["provider"]: item for item in main_module._external_provider_health()}
        for provider in (
            "diadok",
            "sbis",
            "smtp_email",
            "otp_sms",
            "notifications",
            "bank_api",
            "erp_1c",
            "fuel_provider",
            "logistics_provider",
        ):
            assert providers[provider]["mode"] == "sandbox"
            assert providers[provider]["status"] == "CONFIGURED"
            assert providers[provider]["configured"] is True
            assert providers[provider]["sandbox_proof"] is True
            assert providers[provider]["retryable"] is False
    finally:
        for name, value in original.items():
            object.__setattr__(main_module.settings, name, value)
