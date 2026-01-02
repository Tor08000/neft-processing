from __future__ import annotations

from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None
    ClientError = Exception  # type: ignore[assignment]

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class ExportStorage:
    def __init__(self, *, bucket: str | None = None):
        if boto3 is None:
            raise RuntimeError("boto3 is required for S3/MinIO storage")

        endpoint = settings.S3_ENDPOINT
        use_ssl = settings.S3_USE_SSL
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            use_ssl = endpoint.startswith("https://")

        self.bucket = bucket or settings.S3_BUCKET_EXPORTS
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION or None,
            use_ssl=use_ssl,
        )

    def put_bytes(self, key: str, content: bytes, *, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    def head(self, key: str) -> dict[str, Any] | None:
        try:
            return self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return None

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body = response.get("Body")
        if body is None:
            return b""
        return body.read()


__all__ = ["ExportStorage"]
