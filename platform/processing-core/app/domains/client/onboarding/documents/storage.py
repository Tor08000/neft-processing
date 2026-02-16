from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import BinaryIO

import boto3


@dataclass(slots=True)
class OnboardingDocumentsStorage:
    endpoint: str
    access_key: str
    secret_key: str
    secure: bool

    @classmethod
    def from_env(cls) -> "OnboardingDocumentsStorage":
        endpoint = os.getenv("MINIO_ENDPOINT") or os.getenv("NEFT_S3_ENDPOINT")
        access_key = os.getenv("MINIO_ACCESS_KEY") or os.getenv("NEFT_S3_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY") or os.getenv("NEFT_S3_SECRET_KEY")
        secure = (os.getenv("MINIO_SECURE") or "0") == "1"
        if not endpoint or not access_key or not secret_key:
            raise RuntimeError("MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY are required")
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            endpoint_url = endpoint
        else:
            scheme = "https" if secure else "http"
            endpoint_url = f"{scheme}://{endpoint}"
        return cls(endpoint=endpoint_url, access_key=access_key, secret_key=secret_key, secure=secure)

    @property
    def client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def ensure_bucket(self, bucket: str) -> None:
        client = self.client
        try:
            client.head_bucket(Bucket=bucket)
            return
        except Exception:
            client.create_bucket(Bucket=bucket)

    def put_object(self, bucket: str, key: str, payload: bytes, content_type: str, metadata: dict[str, str] | None = None) -> None:
        self.client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType=content_type, Metadata=metadata or {})

    def get_object_stream(self, bucket: str, key: str) -> BinaryIO:
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response.get("Body")
        if body is None:
            return io.BytesIO(b"")
        return body

    def stat_object(self, bucket: str, key: str) -> dict:
        return self.client.head_object(Bucket=bucket, Key=key)
