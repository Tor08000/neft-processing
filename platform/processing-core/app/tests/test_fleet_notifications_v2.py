from __future__ import annotations

import smtplib

from app.services.notifications.email_sender import SmtpEmailSender
from app.services.notifications.webpush_sender import build_webpush_payload


def test_smtp_email_sender_uses_headers(monkeypatch) -> None:
    sent = {}

    class DummySMTP:
        def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self) -> "DummySMTP":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            sent["tls"] = True

        def login(self, username: str, password: str) -> None:
            sent["login"] = (username, password)

        def send_message(self, message) -> None:
            sent["message"] = message

    monkeypatch.setenv("SMTP_HOST", "smtp.local")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@neft.local")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)

    sender = SmtpEmailSender()
    message_id = sender.send(
        to="user@example.com",
        subject="Hello",
        html="<strong>Hi</strong>",
        text="Hi",
        headers={"X-Test": "yes"},
    )
    assert sent["host"] == "smtp.local"
    assert sent["port"] == 2525
    assert sent["message"]["To"] == "user@example.com"
    assert sent["message"]["X-Test"] == "yes"
    assert message_id is not None


def test_build_webpush_payload() -> None:
    payload = {"title": "Alert", "body": "Something happened"}
    assert build_webpush_payload(payload) == '{"title": "Alert", "body": "Something happened"}'
