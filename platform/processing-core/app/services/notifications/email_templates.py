from __future__ import annotations

from typing import Any


_EVENT_TITLES = {
    "LIMIT_BREACH": "Limit breach",
    "ANOMALY": "Anomaly detected",
    "POLICY_ACTION": "Policy action",
    "INGEST_FAILED": "Ingest failed",
    "TEST": "Test notification",
}


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def _render_summary_lines(payload: dict[str, Any]) -> list[str]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return [f"{key}: {_format_value(value)}" for key, value in summary.items()]
    if summary:
        return [str(summary)]
    return []


def render_notification_email(payload: dict[str, Any]) -> tuple[str, str, str]:
    event_type = payload.get("event_type")
    severity = payload.get("severity")
    title = _EVENT_TITLES.get(str(event_type), str(event_type) if event_type else "Fleet notification")
    subject = f"[NEFT] {title} {severity or ''}".strip()

    summary_lines = _render_summary_lines(payload)
    card_alias = payload.get("card_alias") or payload.get("card_id")
    group_alias = payload.get("group_name") or payload.get("group_id")
    link = payload.get("route") or "/client/fleet/notifications/alerts"

    info_lines = [
        f"Summary: {summary_lines[0] if summary_lines else 'See details in the portal.'}",
        f"Card: {_format_value(card_alias)}",
        f"Group: {_format_value(group_alias)}",
        f"Amount/volume: {_format_value(payload.get('amount'))}",
        f"Link: {link}",
    ]
    text_body = "\n".join(info_lines)

    html_lines = "".join(f"<li>{line}</li>" for line in info_lines)
    html_body = f"""
    <div>
      <h2>{subject}</h2>
      <ul>
        {html_lines}
      </ul>
    </div>
    """.strip()
    return subject, html_body, text_body


__all__ = ["render_notification_email"]
