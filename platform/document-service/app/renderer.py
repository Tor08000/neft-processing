from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment, StrictUndefined
from weasyprint import HTML


@dataclass
class HtmlRenderResult:
    html: str
    pdf_bytes: bytes


class HtmlRenderer:
    def __init__(self) -> None:
        self._env = Environment(autoescape=True, undefined=StrictUndefined)

    def render(self, template_html: str, data: dict) -> HtmlRenderResult:
        template = self._env.from_string(template_html)
        rendered_html = template.render(**data)
        pdf_bytes = HTML(string=rendered_html).write_pdf()
        return HtmlRenderResult(html=rendered_html, pdf_bytes=pdf_bytes)


__all__ = ["HtmlRenderer", "HtmlRenderResult"]
