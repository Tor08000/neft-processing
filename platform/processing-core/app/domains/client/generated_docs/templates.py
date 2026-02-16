from __future__ import annotations

from dataclasses import dataclass

from app.domains.client.generated_docs.models import GeneratedDocKind


@dataclass(frozen=True)
class DocumentTemplateSpec:
    doc_kind: GeneratedDocKind
    template_id: str
    filename_pattern: str


ONBOARDING_TEMPLATES: tuple[DocumentTemplateSpec, ...] = (
    DocumentTemplateSpec(GeneratedDocKind.OFFER, "offer_v1", "NEFT_OFFER_{inn}.pdf"),
    DocumentTemplateSpec(GeneratedDocKind.SERVICE_AGREEMENT, "agreement_v1", "NEFT_SERVICE_AGREEMENT_{inn}.pdf"),
    DocumentTemplateSpec(GeneratedDocKind.DPA, "dpa_v1", "NEFT_DPA_{inn}.pdf"),
)
