from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
import logging
from pathlib import PurePosixPath
import time
from typing import Iterable

import paramiko

from app.services.accounting_export.delivery.base import DeliveryAdapter, DeliveryPayload, DeliveryResult, build_delivery_result


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SftpDeliveryConfig:
    host: str
    port: int
    username: str
    auth_method: str
    password: str | None
    private_key: str | None
    private_key_passphrase: str | None
    remote_path: str
    timeout_seconds: int
    retries: int
    retry_backoff_seconds: int


class SftpDeliveryAdapter(DeliveryAdapter):
    def __init__(self, config: SftpDeliveryConfig) -> None:
        self._config = config

    def deliver(self, *, payloads: Iterable[DeliveryPayload]) -> DeliveryResult:
        payloads = tuple(payloads)
        for attempt in range(1, self._config.retries + 1):
            try:
                return self._deliver_once(payloads)
            except Exception:
                if attempt >= self._config.retries:
                    raise
                delay = self._config.retry_backoff_seconds * attempt
                logger.warning("sftp_delivery_retry", extra={"attempt": attempt, "delay": delay})
                time.sleep(delay)
        return build_delivery_result(target=self._target(), payloads=payloads)

    def _deliver_once(self, payloads: tuple[DeliveryPayload, ...]) -> DeliveryResult:
        client = self._connect()
        try:
            sftp = client.open_sftp()
            self._ensure_remote_path(sftp, self._config.remote_path)
            for payload in payloads:
                remote_path = PurePosixPath(self._config.remote_path) / payload.filename
                with BytesIO(payload.payload) as stream:
                    sftp.putfo(stream, str(remote_path))
            return build_delivery_result(target=self._target(), payloads=payloads)
        finally:
            client.close()

    def _connect(self) -> paramiko.SSHClient:
        config = self._config
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = None
        if config.auth_method.lower() == "key" and config.private_key:
            key_stream = StringIO(config.private_key)
            pkey = paramiko.RSAKey.from_private_key(key_stream, password=config.private_key_passphrase)
        client.connect(
            hostname=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            pkey=pkey,
            timeout=config.timeout_seconds,
        )
        return client

    def _ensure_remote_path(self, sftp: paramiko.SFTPClient, remote_path: str) -> None:
        path = PurePosixPath(remote_path)
        parts = path.parts
        current = PurePosixPath(parts[0])
        if current.as_posix() == "/":
            current = PurePosixPath("/")
            parts = parts[1:]
        for part in parts:
            current = current / part
            try:
                sftp.stat(str(current))
            except FileNotFoundError:
                sftp.mkdir(str(current))

    def _target(self) -> str:
        return f"sftp://{self._config.host}:{self._config.port}{self._config.remote_path}"


__all__ = ["SftpDeliveryAdapter", "SftpDeliveryConfig"]
