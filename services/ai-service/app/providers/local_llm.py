from __future__ import annotations


def local_tx_score(features: dict) -> dict:
    """
    Очень простая эвристика:
    - базовый риск = 0.1
    - + qty/200 до +0.8
    - +0.1 если сумма > 50_000
    - +0.1 если azs_name неизвестна
    """
    score = 0.1
    reasons = []
    qty = float(features.get("qty", 0) or 0)
    amount = float(features.get("amount", 0) or 0)
    azs = (features.get("merchant") or features.get("azs_name") or "").strip()

    score += min(qty / 200.0, 0.8)
    if amount > 50000:
        score += 0.1
        reasons.append("HIGH_AMOUNT")
    if not azs:
        score += 0.1
        reasons.append("UNKNOWN_LOCATION")

    score = min(score, 0.99)
    return {"score": round(score, 2), "reasons": reasons}
