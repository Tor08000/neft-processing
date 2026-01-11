from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Mapping

logger = logging.getLogger(__name__)


class EmailSender:
    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str | None,
        text: str | None,
        headers: Mapping[str, str] | None = None,
    ) -> str | None:
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str | None,
        text: str | None,
        headers: Mapping[str, str] | None = None,
    ) -> str | None:
        logger.info("Email to %s: %s\n%s", to, subject, text or html or "")
        return None


class SmtpEmailSender(EmailSender):
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
        self.from_address = os.getenv("SMTP_FROM") or self.username or "no-reply@neft.local"
        tls_env = os.getenv("SMTP_TLS")
        if tls_env is None:
            tls_env = os.getenv("SMTP_USE_TLS", "true")
        self.use_tls = str(tls_env).lower() not in {"0", "false", "no"}

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str | None,
        text: str | None,
        headers: Mapping[str, str] | None = None,
    ) -> str | None:
        if not self.host:
            raise RuntimeError("smtp_host_missing")
        message = EmailMessage()
        message_id = make_msgid(domain="neft.local")
        message["Message-ID"] = message_id
        message["From"] = self.from_address
        message["To"] = to
        message["Subject"] = subject
        if headers:
            for key, value in headers.items():
                message[key] = value

        if text:
            message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
        return message_id


__all__ = ["ConsoleEmailSender", "EmailSender", "SmtpEmailSender"]
