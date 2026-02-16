import pytest

from app.services.startup_validation import (
    BASE_REQUIRED_TABLES,
    EMBEDDED_REQUIRED_TABLES,
    get_auth_host_mode,
    get_missing_required_tables,
)


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_HOST_MODE", raising=False)
    monkeypatch.delenv("NEFT_AUTH_MODE", raising=False)


def test_auth_host_mode_defaults_to_external() -> None:
    assert get_auth_host_mode() == "external"


def test_auth_host_mode_supports_deprecated_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEFT_AUTH_MODE", "embedded")
    assert get_auth_host_mode() == "embedded"


def test_external_mode_does_not_require_users_table() -> None:
    existing = set(BASE_REQUIRED_TABLES)

    missing = get_missing_required_tables(existing, auth_mode="external")

    assert missing == []
    assert "users" not in missing


def test_embedded_mode_requires_users_table() -> None:
    existing = set(BASE_REQUIRED_TABLES)

    missing = get_missing_required_tables(existing, auth_mode="embedded")

    assert missing == list(EMBEDDED_REQUIRED_TABLES)
    assert "users" in missing


def test_embedded_mode_with_users_table_passes() -> None:
    existing = set(BASE_REQUIRED_TABLES) | {"users"}

    missing = get_missing_required_tables(existing, auth_mode="embedded")

    assert missing == []
