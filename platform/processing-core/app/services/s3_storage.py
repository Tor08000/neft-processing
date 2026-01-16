from __future__ import annotations

from typing import Optional

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


class S3Storage:
    """Thin wrapper around boto3 for S3/MinIO storage."""

    def __init__(self, *, bucket: str | None = None):
        if boto3 is None:
            raise RuntimeError("boto3 is required for S3/MinIO storage")

        self.bucket = (
            bucket
            or settings.NEFT_S3_BUCKET_INVOICES
            or settings.NEFT_S3_BUCKET
            or settings.NEFT_INVOICE_PDF_BUCKET
        )
        self.public_base = (settings.NEFT_S3_PUBLIC_URL_BASE or "").rstrip("/") or None
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.NEFT_S3_ENDPOINT,
            aws_access_key_id=settings.NEFT_S3_ACCESS_KEY,
            aws_secret_access_key=settings.NEFT_S3_SECRET_KEY,
            region_name=settings.NEFT_S3_REGION,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:  # pragma: no cover - depends on AWS credentials
            error_code = str(exc.response.get("Error", {}).get("Code"))
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise

        params = {"Bucket": self.bucket}
        if settings.NEFT_S3_REGION:
            params["CreateBucketConfiguration"] = {"LocationConstraint": settings.NEFT_S3_REGION}
        self._client.create_bucket(**params)

    def put_bytes(self, key: str, payload: bytes, *, content_type: str = "application/pdf") -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType=content_type)
        return self._public_url(key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if key:
                    keys.append(key)
        return keys

    def get_bytes(self, key: str) -> Optional[bytes]:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body = response.get("Body")
            if body is None:
                return None
            return body.read()
        except ClientError:
            return None

    def presign(self, key: str, *, expires: int = 3600) -> Optional[str]:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except Exception:  # pragma: no cover - optional presign failure
            logger.warning("s3.presign_failed", extra={"key": key})
            return None

    def presign_put(
        self,
        key: str,
        *,
        content_type: str,
        expires: int = 3600,
    ) -> Optional[str]:
        try:
            return self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires,
            )
        except Exception:  # pragma: no cover - optional presign failure
            logger.warning("s3.presign_put_failed", extra={"key": key})
            return None

    def _public_url(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base}/{key}"
        return f"s3://{self.bucket}/{key}"

    def public_url(self, key: str) -> str:
        return self._public_url(key)


__all__ = ["S3Storage"]
