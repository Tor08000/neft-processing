from __future__ import annotations

from app.services.accounting_export.delivery.base import DeliveryAdapter, DeliveryPayload, DeliveryResult
from app.services.accounting_export.delivery.noop import NoopDeliveryAdapter
from app.services.accounting_export.delivery.sftp import SftpDeliveryAdapter, SftpDeliveryConfig
from app.services.accounting_export.onboarding_profiles import OnboardingProfile


def build_delivery_adapter(profile: OnboardingProfile) -> DeliveryAdapter:
    method = profile.delivery_method.upper()
    if method == "SFTP":
        if not profile.delivery or not profile.delivery.sftp:
            raise ValueError("sftp_delivery_config_missing")
        sftp = profile.delivery.sftp
        return SftpDeliveryAdapter(
            SftpDeliveryConfig(
                host=sftp.host,
                port=sftp.port,
                username=sftp.username,
                auth_method=sftp.auth_method,
                password=sftp.resolve_password(),
                private_key=sftp.resolve_private_key(),
                private_key_passphrase=sftp.resolve_private_key_passphrase(),
                remote_path=sftp.remote_path,
                timeout_seconds=sftp.timeout_seconds,
                retries=sftp.retries,
                retry_backoff_seconds=sftp.retry_backoff_seconds,
            )
        )
    return NoopDeliveryAdapter()


__all__ = [
    "DeliveryAdapter",
    "DeliveryPayload",
    "DeliveryResult",
    "NoopDeliveryAdapter",
    "SftpDeliveryAdapter",
    "SftpDeliveryConfig",
    "build_delivery_adapter",
]
