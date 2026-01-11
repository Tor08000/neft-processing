from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from neft_shared.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class DocumentRenderRequest:
    template_kind: str
    template_id: str | None
    template_html: str
    data: dict
    output_format: str
    tenant_id: int
    client_id: str | None
    idempotency_key: str
    meta: dict | None
    doc_id: str
    doc_type: str
    version: int
    document_date: str | None


@dataclass(frozen=True)
class DocumentRenderResult:
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str
    version: int


@dataclass(frozen=True)
class DocumentStorageRef:
    bucket: str
    object_key: str
    sha256: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class DocumentSignRequest:
    document_id: str
    provider: str
    input: DocumentStorageRef
    output_bucket: str
    output_prefix: str
    idempotency_key: str
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentSignResult:
    status: str
    provider_request_id: str | None
    signed: DocumentStorageRef
    signature: DocumentStorageRef
    certificate: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentVerifyRequest:
    provider: str
    input: DocumentStorageRef
    signature: DocumentStorageRef
    signed: DocumentStorageRef | None = None
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentVerifyResult:
    status: str
    verified: bool
    error_code: str | None = None
    certificate: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentTemplateMetadata:
    code: str
    title: str
    engine: str
    repo_path: str
    schema_path: str
    template_hash: str
    schema_hash: str
    version: str
    status: str
    schema: dict[str, Any] | None = None


class DocumentServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.DOCUMENT_SERVICE_URL).rstrip("/")
        self.timeout = httpx.Timeout(connect=2.0, read=30.0, write=30.0, pool=2.0)

    def render(self, request: DocumentRenderRequest) -> DocumentRenderResult:
        payload = {
            "template_kind": request.template_kind,
            "template_id": request.template_id,
            "template_html": request.template_html,
            "data": request.data,
            "output_format": request.output_format,
            "tenant_id": request.tenant_id,
            "client_id": request.client_id,
            "idempotency_key": request.idempotency_key,
            "meta": request.meta,
            "doc_id": request.doc_id,
            "doc_type": request.doc_type,
            "version": request.version,
            "document_date": request.document_date,
        }

        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/v1/render", json=payload)
                response.raise_for_status()
                data = response.json()
                return DocumentRenderResult(
                    bucket=data["bucket"],
                    object_key=data["object_key"],
                    sha256=data["sha256"],
                    size_bytes=int(data["size_bytes"]),
                    content_type=data["content_type"],
                    version=int(data["version"]),
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_render_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error

    def sign(self, request: DocumentSignRequest) -> DocumentSignResult:
        payload = {
            "document_id": request.document_id,
            "provider": request.provider,
            "input": {
                "bucket": request.input.bucket,
                "object_key": request.input.object_key,
                "sha256": request.input.sha256,
            },
            "output": {"bucket": request.output_bucket, "prefix": request.output_prefix},
            "idempotency_key": request.idempotency_key,
            "meta": request.meta,
        }

        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/v1/sign", json=payload)
                response.raise_for_status()
                data = response.json()
                return DocumentSignResult(
                    status=data["status"],
                    provider_request_id=data.get("provider_request_id"),
                    signed=DocumentStorageRef(
                        bucket=data["signed"]["bucket"],
                        object_key=data["signed"]["object_key"],
                        sha256=data["signed"]["sha256"],
                        size_bytes=int(data["signed"]["size_bytes"]),
                    ),
                    signature=DocumentStorageRef(
                        bucket=data["signature"]["bucket"],
                        object_key=data["signature"]["object_key"],
                        sha256=data["signature"]["sha256"],
                        size_bytes=int(data["signature"]["size_bytes"]),
                    ),
                    certificate=data.get("certificate"),
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_sign_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error

    def verify(self, request: DocumentVerifyRequest) -> DocumentVerifyResult:
        payload = {
            "provider": request.provider,
            "input": {
                "bucket": request.input.bucket,
                "object_key": request.input.object_key,
                "sha256": request.input.sha256,
            },
            "signature": {
                "bucket": request.signature.bucket,
                "object_key": request.signature.object_key,
                "sha256": request.signature.sha256,
            },
            "signed": (
                {
                    "bucket": request.signed.bucket,
                    "object_key": request.signed.object_key,
                    "sha256": request.signed.sha256,
                }
                if request.signed
                else None
            ),
            "meta": request.meta,
        }

        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/v1/verify", json=payload)
                response.raise_for_status()
                data = response.json()
                return DocumentVerifyResult(
                    status=data["status"],
                    verified=bool(data["verified"]),
                    error_code=data.get("error_code"),
                    certificate=data.get("certificate"),
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_verify_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error

    def list_templates(self) -> list[DocumentTemplateMetadata]:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(f"{self.base_url}/v1/templates")
                response.raise_for_status()
                data = response.json()
                return [
                    DocumentTemplateMetadata(
                        code=item["code"],
                        title=item["title"],
                        engine=item["engine"],
                        repo_path=item["repo_path"],
                        schema_path=item["schema_path"],
                        template_hash=item["template_hash"],
                        schema_hash=item["schema_hash"],
                        version=item["version"],
                        status=item["status"],
                    )
                    for item in data
                ]
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_templates_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error

    def get_template(self, code: str) -> DocumentTemplateMetadata:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(f"{self.base_url}/v1/templates/{code}")
                response.raise_for_status()
                item = response.json()
                return DocumentTemplateMetadata(
                    code=item["code"],
                    title=item["title"],
                    engine=item["engine"],
                    repo_path=item["repo_path"],
                    schema_path=item["schema_path"],
                    template_hash=item["template_hash"],
                    schema_hash=item["schema_hash"],
                    version=item["version"],
                    status=item["status"],
                    schema=item.get("schema"),
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_template_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error


__all__ = [
    "DocumentServiceClient",
    "DocumentRenderRequest",
    "DocumentRenderResult",
    "DocumentStorageRef",
    "DocumentSignRequest",
    "DocumentSignResult",
    "DocumentVerifyRequest",
    "DocumentVerifyResult",
]
