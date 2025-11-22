from fastapi import APIRouter
import random

router = APIRouter()

@router.post("/")
def score(payload: dict):
    event = payload.get("event") or {}
    hour = int(event.get("hour") or 12)
    qty = float(event.get("qty") or 0)
    amount = float(event.get("amount") or 0)

    base = 0.25
    if hour in [0,1,2,3,4,5]: base += 0.2
    if qty >= 200 or amount >= 15000: base += 0.3
    base += random.uniform(-0.05, 0.05)
    risk = max(0.05, min(0.95, base))
    hint = "ALLOW" if risk < 0.75 else "SOFT_DECLINE"
    return {"risk_score": round(risk,3), "decision_hint": hint, "reason_codes": []}
