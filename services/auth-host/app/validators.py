from typing import Tuple

async def ensure_card_can_spend(cur, card: dict, amount: float) -> Tuple[bool, str | None]:
    # минимальные правила: активность и дневной лимит
    limit_day = float(card["limit_day"] or 0)
    spent_day = float(card["spent_day"] or 0)
    if limit_day > 0 and (spent_day + amount) > limit_day:
        return False, "day_limit_exceeded"
    return True, None
