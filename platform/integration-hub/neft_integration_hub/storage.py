from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from neft_integration_hub.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
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

    def get_bytes(self, object_key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=object_key)
        except ClientError:
            return None
        body = response.get("Body")
        if body is None:
            return None
        return body.read()


__all__ = ["S3Storage", "StoredObject"]
