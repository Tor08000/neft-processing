from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemplateDefinition:
    code: str
    title: str
    engine: str
    template_path: Path
    schema_path: Path
    version: str
    status: str

    def template_hash(self) -> str:
        return _file_hash(self.template_path)

    def schema_hash(self) -> str:
        return _file_hash(self.schema_path)

    def load_template(self) -> str:
        return self.template_path.read_text(encoding="utf-8")

    def load_schema(self) -> dict[str, Any]:
        return json.loads(self.schema_path.read_text(encoding="utf-8"))


class TemplateRegistry:
    def __init__(self, *, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = base_dir
        templates_dir = base_dir / "templates"
        schemas_dir = templates_dir / "schemas"
        self._templates: dict[str, TemplateDefinition] = {
            "contract_main": TemplateDefinition(
                code="contract_main",
                title="Main contract",
                engine="HTML",
                template_path=templates_dir / "contract_main.html",
                schema_path=schemas_dir / "contract_main.schema.json",
                version="1",
                status="ACTIVE",
            ),
            "annex": TemplateDefinition(
                code="annex",
                title="Annex",
                engine="HTML",
                template_path=templates_dir / "annex.html",
                schema_path=schemas_dir / "annex.schema.json",
                version="1",
                status="ACTIVE",
            ),
            "invoice": TemplateDefinition(
                code="invoice",
                title="Invoice",
                engine="HTML",
                template_path=templates_dir / "invoice.html",
                schema_path=schemas_dir / "invoice.schema.json",
                version="1",
                status="ACTIVE",
            ),
            "act_monthly": TemplateDefinition(
                code="act_monthly",
                title="Monthly act",
                engine="HTML",
                template_path=templates_dir / "act_monthly.html",
                schema_path=schemas_dir / "act_monthly.schema.json",
                version="1",
                status="ACTIVE",
            ),
            "reconciliation_act": TemplateDefinition(
                code="reconciliation_act",
                title="Reconciliation act",
                engine="HTML",
                template_path=templates_dir / "reconciliation_act.html",
                schema_path=schemas_dir / "reconciliation_act.schema.json",
                version="1",
                status="ACTIVE",
            ),
            "closing_package_cover_letter": TemplateDefinition(
                code="closing_package_cover_letter",
                title="Closing package cover letter",
                engine="HTML",
                template_path=templates_dir / "closing_package_cover_letter.html",
                schema_path=schemas_dir / "closing_package_cover_letter.schema.json",
                version="1",
                status="ACTIVE",
            ),
        }

    def list_templates(self) -> list[TemplateDefinition]:
        return list(self._templates.values())

    def get_template(self, code: str) -> TemplateDefinition | None:
        return self._templates.get(code)

    def repo_paths(self, template: TemplateDefinition) -> tuple[str, str]:
        return (
            str(template.template_path.relative_to(self.base_dir)),
            str(template.schema_path.relative_to(self.base_dir)),
        )


def _file_hash(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


__all__ = ["TemplateDefinition", "TemplateRegistry"]
