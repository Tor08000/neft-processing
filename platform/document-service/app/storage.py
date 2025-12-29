from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class StoredObjectMetadata:
    bucket: str
    object_key: str
    size_bytes: int
    content_type: str
    sha256: str | None


class S3Storage:
    def __init__(self, *, bucket: str | None = None) -> None:
        self.bucket = bucket or settings.s3_bucket_docs
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code"))
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise

        params: dict[str, Any] = {"Bucket": self.bucket}
        if settings.s3_region:
            params["CreateBucketConfiguration"] = {"LocationConstraint": settings.s3_region}
        self._client.create_bucket(**params)

    def put_bytes(
        self,
        object_key: str,
        payload: bytes,
        *,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=payload,
            ContentType=content_type,
            Metadata=metadata or {},
        )

    def get_bytes(self, object_key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=object_key)
        except ClientError:
            return None
        body = response.get("Body")
        if body is None:
            return None
        return body.read()

    def head_object(self, object_key: str) -> StoredObjectMetadata | None:
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=object_key)
        except ClientError:
            return None
        metadata = response.get("Metadata") or {}
        sha256 = metadata.get("sha256")
        return StoredObjectMetadata(
            bucket=self.bucket,
            object_key=object_key,
            size_bytes=int(response.get("ContentLength", 0)),
            content_type=response.get("ContentType") or "application/octet-stream",
            sha256=sha256,
        )

    def presign(self, object_key: str, *, ttl_seconds: int) -> str | None:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=ttl_seconds,
            )
        except Exception:
            return None


__all__ = ["S3Storage", "StoredObjectMetadata"]
