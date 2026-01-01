from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.schemas.achievements import AchievementBadge, AchievementStreak, AchievementsSummary
from app.services.kpi_service import build_kpi_summary

DECLINES_STABLE_THRESHOLD = 10


def _resolve_status(value: bool, *, in_progress: bool = True) -> str:
    if value:
        return "unlocked"
    return "in_progress" if in_progress else "locked"


def build_achievements_summary(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    client_id: str | None = None,
) -> AchievementsSummary:
    kpi_summary = build_kpi_summary(db, tenant_id=tenant_id, window_days=window_days, client_id=client_id)
    as_of = datetime.now(timezone.utc)

    kpis = {kpi.key: kpi for kpi in kpi_summary.kpis}
    billing_errors = kpis.get("billing_errors")
    exports_ontime = kpis.get("exports_ontime_percent")
    declines_total = kpis.get("declines_total")

    billing_errors_value = billing_errors.value if billing_errors else 0
    exports_ontime_value = exports_ontime.value if exports_ontime else 0
    declines_total_value = declines_total.value if declines_total else 0
    declines_delta = declines_total.delta if declines_total else None

    clean_billing_ok = billing_errors_value == 0
    exports_sla_ok = exports_ontime_value >= 95
    stable_declines_ok = declines_delta is not None and declines_delta < 0 and declines_total_value < DECLINES_STABLE_THRESHOLD

    history_len = min(window_days, 14)
    history_value = [clean_billing_ok for _ in range(history_len)]
    current_streak = history_len if all(history_value) else 0
    streak_status = _resolve_status(current_streak >= history_len, in_progress=current_streak > 0)

    badges = [
        AchievementBadge(
            key="clean_billing",
            title="Чистый биллинг",
            description="0 критических ошибок за неделю",
            status=_resolve_status(clean_billing_ok),
            progress=1.0 if clean_billing_ok else 0.0,
            how_to="Держите billing_errors=0 за период",
            meta={"window_days": window_days},
        ),
        AchievementBadge(
            key="exports_sla",
            title="Дисциплина выгрузок",
            description="SLA по экспортам за период",
            status=_resolve_status(exports_sla_ok),
            progress=min(exports_ontime_value / 95, 1.0) if exports_ontime_value else 0.0,
            how_to="Держите exports_ontime_percent ≥ 95",
            meta={"target_percent": 95},
        ),
        AchievementBadge(
            key="stable_declines",
            title="Стабильные отказы",
            description="Снижение количества отказов за период",
            status=_resolve_status(stable_declines_ok, in_progress=declines_delta is not None),
            progress=1.0
            if declines_total_value <= 0
            else min(DECLINES_STABLE_THRESHOLD / declines_total_value, 1.0),
            how_to="Снижайте declines_total и держите ниже порога",
            meta={"threshold": DECLINES_STABLE_THRESHOLD},
        ),
    ]

    streak = AchievementStreak(
        key="no_critical_errors",
        title="Серия без ошибок",
        current=current_streak,
        target=history_len,
        history=history_value,
        status=streak_status,
        how_to="Ежедневно без критических ошибок",
    )

    return AchievementsSummary(window_days=window_days, as_of=as_of, badges=badges, streak=streak)


__all__ = ["build_achievements_summary"]
