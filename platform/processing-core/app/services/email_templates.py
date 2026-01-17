from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


TEMPLATE_SUBJECTS = {
    "export_ready": "[NEFT] Экспорт готов",
    "export_failed": "[NEFT] Ошибка экспорта",
    "scheduled_report_ready": "[NEFT] Запланированный отчёт готов",
    "support_ticket_commented": "[NEFT] Новый комментарий по тикету",
    "support_sla_first_response_breached": "[NEFT] SLA нарушен: первый ответ",
    "support_sla_resolution_breached": "[NEFT] SLA нарушен: решение",
}


def _base_path() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "email"


@lru_cache(maxsize=64)
def _load_template(path: str) -> str:
    template_path = _base_path() / path
    return template_path.read_text(encoding="utf-8")


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _apply_template(template: str, context: dict[str, str]) -> str:
    return template.format_map(_SafeDict(context))


def build_portal_url(path: str | None) -> str:
    base_url = os.getenv("NEFT_PUBLIC_BASE_URL", "").rstrip("/")
    if not path:
        return base_url or ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    if not base_url:
        return path
    return f"{base_url}{path}"


def render_email_template(template_key: str, context: dict[str, str]) -> tuple[str, str, str | None]:
    subject = TEMPLATE_SUBJECTS.get(template_key, "[NEFT] Уведомление")
    text_template = _load_template(f"{template_key}.txt")
    html_template = _load_template(f"{template_key}.html")
    text_body = _apply_template(text_template, context)
    html_body = _apply_template(html_template, context)
    return subject, text_body, html_body


__all__ = ["build_portal_url", "render_email_template"]
