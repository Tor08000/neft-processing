from app.services import jwt_support


class _Logger:
    def __init__(self):
        self.warning_calls: list[tuple[str, dict]] = []
        self.debug_calls: list[tuple[str, dict]] = []

    def warning(self, event: str, *, extra: dict):
        self.warning_calls.append((event, extra))

    def debug(self, event: str, *, extra: dict):
        self.debug_calls.append((event, extra))


def test_log_token_rejection_is_throttled_within_window(monkeypatch):
    logger = _Logger()
    token = "bad-token"

    jwt_support._rejection_log_window.clear()
    monkeypatch.setenv("ENV", "")

    jwt_support.log_token_rejection(logger, token, reason="wrong_portal", event="client_auth.token_rejected", path="/api/core/legal/required")
    jwt_support.log_token_rejection(logger, token, reason="wrong_portal", event="client_auth.token_rejected", path="/api/core/legal/required")

    assert len(logger.warning_calls) == 1


def test_log_token_rejection_uses_path_in_dedupe_key(monkeypatch):
    logger = _Logger()
    token = "bad-token"

    jwt_support._rejection_log_window.clear()
    monkeypatch.setenv("ENV", "")

    jwt_support.log_token_rejection(logger, token, reason="wrong_portal", event="client_auth.token_rejected", path="/api/core/legal/required")
    jwt_support.log_token_rejection(logger, token, reason="wrong_portal", event="client_auth.token_rejected", path="/api/core/profile/me")

    assert len(logger.warning_calls) == 2
