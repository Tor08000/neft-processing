from __future__ import annotations

from datetime import datetime
from typing import Any


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        display = value.get("display")
        if display:
            return str(display)
        if value.get("redacted"):
            return "REDACTED"
    return str(value)


def _format_datetime(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _render_card_line(payload: dict[str, Any]) -> str:
    alias = payload.get("alias")
    card_id = payload.get("card_id")
    card_label = _format_value(alias) if alias else _format_value(card_id)
    return f"Card: {card_label}"


def _render_group_line(payload: dict[str, Any]) -> str:
    group_label = payload.get("group_label")
    group_id = payload.get("group_id")
    if group_label or group_id:
        return f"Group: {_format_value(group_label) if group_label else _format_value(group_id)}"
    return "Group: —"


def _render_links(payload: dict[str, Any]) -> list[str]:
    links = ["• Open in portal: /fleet/notifications"]
    link_type = payload.get("link_type")
    link_id = payload.get("link_id")
    if link_type == "card" and link_id:
        links.append(f"• Card details: /fleet/cards/{link_id}")
    return links


def render_telegram_message(payload: dict[str, Any]) -> str:
    event_type = payload.get("event_type")
    severity = payload.get("severity")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    if event_type == "LIMIT_BREACH":
        breach_type = summary.get("breach_type")
        threshold = summary.get("threshold")
        observed = summary.get("observed")
        delta = summary.get("delta")
        period = summary.get("period")
        occurred_at = summary.get("occurred_at")
        lines = [
            f"⛽️ NEFT Fleet Alert — LIMIT_BREACH ({severity})",
            _render_card_line(payload),
            _render_group_line(payload),
            f"Observed: {_format_value(observed)} ₽ {period or ''}".strip(),
            f"Limit: {_format_value(threshold)} ₽",
            f"Delta: {_format_value(delta)}",
            f"Why: {breach_type} breach" if breach_type else "Why: —",
            f"When: {_format_datetime(occurred_at)}",
            "Actions:",
            *_render_links(payload),
        ]
        return "\n".join(lines)

    if event_type == "ANOMALY":
        anomaly_type = summary.get("anomaly_type")
        occurred_at = summary.get("occurred_at")
        lines = [
            f"📈 NEFT Fleet Alert — ANOMALY ({severity})",
            f"Type: {_format_value(anomaly_type)}",
            _render_card_line(payload),
            _render_group_line(payload),
            f"When: {_format_datetime(occurred_at)}",
            "Open: /fleet/notifications",
        ]
        return "\n".join(lines)

    if event_type == "POLICY_ACTION":
        action = payload.get("action")
        reason = payload.get("reason") or payload.get("breach_kind")
        status = payload.get("status")
        status_suffix = f" ({status})" if status else ""
        lines = [
            "🛡 Policy action applied" + status_suffix,
            f"Action: {_format_value(action)}",
            f"Reason: {_format_value(reason)}" if reason else "Reason: —",
            _render_card_line(payload),
            _render_group_line(payload),
            "Open: /fleet/notifications",
        ]
        return "\n".join(lines)

    if event_type == "INGEST_FAILED":
        lines = [
            f"⚠️ NEFT Fleet Alert — INGEST_FAILED ({severity})",
            f"Job: {_format_value(summary.get('job_id') if summary else None)}",
            f"Error: {_format_value(summary.get('error') if summary else None)}",
            "Open: /fleet/notifications",
        ]
        return "\n".join(lines)

    title = f"NEFT Fleet Alert — {event_type or 'EVENT'} ({severity})"
    return "\n".join([title, "Open: /fleet/notifications"])


__all__ = ["render_telegram_message"]
