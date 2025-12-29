from __future__ import annotations


def build_decision_choice_answers(decision_choice: dict | None) -> dict[str, str]:
    if not decision_choice:
        return {
            "decision_choice": "Данные о выборе действия недоступны.",
            "decision_choice_why": "Недостаточно данных для обоснования выбора.",
        }
    recommended = decision_choice.get("recommended_action") if isinstance(decision_choice, dict) else None
    reasoning = decision_choice.get("reasoning") if isinstance(decision_choice, dict) else None
    action = recommended.get("action") if isinstance(recommended, dict) else None
    confidence = recommended.get("confidence") if isinstance(recommended, dict) else None
    confidence_pct = f"{round(confidence * 100)}%" if isinstance(confidence, (int, float)) else None
    if action and confidence_pct:
        summary = f"Сейчас наиболее эффективно: {action} (уверенность {confidence_pct})."
    elif action:
        summary = f"Сейчас наиболее эффективно: {action}."
    else:
        summary = "Не удалось определить наиболее эффективное действие."

    if isinstance(reasoning, dict):
        why_parts = [
            reasoning.get("why"),
            reasoning.get("comparison"),
            reasoning.get("benchmark"),
        ]
        why_text = " ".join(part for part in why_parts if part)
    else:
        why_text = "Недостаточно данных для обоснования выбора."

    return {
        "decision_choice": summary,
        "decision_choice_why": why_text,
    }


__all__ = ["build_decision_choice_answers"]
