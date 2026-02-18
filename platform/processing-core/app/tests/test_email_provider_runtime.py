from app.services.email_provider_runtime import (
    get_email_provider_mode,
    get_email_startup_strict,
    is_email_degraded,
    load_email_provider_startup_config,
    set_email_degraded,
)


def test_email_provider_defaults_for_dev() -> None:
    env = {"APP_ENV": "dev"}
    cfg = load_email_provider_startup_config(env)
    assert cfg.mode == "stub"
    assert cfg.strict is False
    assert cfg.integration_hub_url == "http://integration-hub:8080"
    assert cfg.timeout_seconds == 3
    assert cfg.retries == 1


def test_email_provider_defaults_for_prod() -> None:
    env = {"APP_ENV": "prod"}
    assert get_email_provider_mode(env) == "integration_hub"
    assert get_email_startup_strict(env) is True


def test_email_degraded_flag_roundtrip() -> None:
    set_email_degraded(False)
    assert is_email_degraded() is False
    set_email_degraded(True)
    assert is_email_degraded() is True
    set_email_degraded(False)
