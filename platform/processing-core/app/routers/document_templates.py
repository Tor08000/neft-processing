from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.services.document_service_client import DocumentServiceClient, DocumentTemplateMetadata

router = APIRouter(prefix="/documents", tags=["document-templates"])


def _template_to_dict(template: DocumentTemplateMetadata) -> dict:
    payload = {
        "code": template.code,
        "title": template.title,
        "engine": template.engine,
        "repo_path": template.repo_path,
        "schema_path": template.schema_path,
        "template_hash": template.template_hash,
        "schema_hash": template.schema_hash,
        "version": template.version,
        "status": template.status,
    }
    if template.schema is not None:
        payload["schema"] = template.schema
    return payload


@router.get("/templates")
def list_templates(_: dict = Depends(require_admin_user)) -> list[dict]:
    templates = DocumentServiceClient().list_templates()
    return [_template_to_dict(template) for template in templates]


@router.get("/templates/{code}")
def get_template(code: str, _: dict = Depends(require_admin_user)) -> dict:
    template = DocumentServiceClient().get_template(code)
    return _template_to_dict(template)
