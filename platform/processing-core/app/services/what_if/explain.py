from __future__ import annotations

from app.services.what_if.scoring import RiskOutlook


def build_explain_lines(
    *,
    probability_improved_pct: int,
    sample_size: int,
    memory_penalty_pct: int,
    risk_outlook: RiskOutlook,
) -> list[str]:
    lines = [
        f"Исторически улучшало ситуацию в {probability_improved_pct}% случаев (n={sample_size})",
        _memory_line(memory_penalty_pct),
        _risk_line(risk_outlook),
    ]
    return lines


def _memory_line(memory_penalty_pct: int) -> str:
    if memory_penalty_pct >= 60:
        return "Memory penalty высокий: действие недавно проваливалось"
    if memory_penalty_pct >= 30:
        return "Memory penalty умеренный: есть недавний негативный опыт"
    return "Memory penalty низкий: действие не проваливалось недавно"


def _risk_line(risk_outlook: RiskOutlook) -> str:
    if risk_outlook == RiskOutlook.IMPROVE:
        return "Ожидается улучшение risk posture"
    if risk_outlook == RiskOutlook.UNCERTAIN:
        return "Risk improvement uncertain из-за памяти решений"
    return "Risk posture без заметных изменений"


__all__ = ["build_explain_lines"]
