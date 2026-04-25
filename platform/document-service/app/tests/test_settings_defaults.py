from __future__ import annotations

import importlib


def test_provider_x_mode_defaults_to_real(monkeypatch) -> None:
    monkeypatch.delenv("PROVIDER_X_MODE", raising=False)

    import app.settings as settings_module

    settings_module = importlib.reload(settings_module)
    settings = settings_module.get_settings()

    assert settings.provider_x_mode == "real"
    assert settings.provider_x_api_key == ""
    assert settings.provider_x_api_secret == ""
