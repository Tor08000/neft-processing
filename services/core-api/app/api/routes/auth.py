from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from ...db import get_db

router = APIRouter()

@router.post("/internal/pricing/resolve")
def internal_pricing(azs_id: int, product_id: int, db=Depends(get_db)):
    row = db.execute(text("""
      SELECT price FROM price_list
      WHERE azs_id=:azs AND product_id=:prod AND status='ACTIVE'
        AND (start_at IS NULL OR start_at <= now())
        AND (end_at   IS NULL OR end_at   >= now())
      ORDER BY version DESC, id DESC LIMIT 1
    """), {"azs": azs_id, "prod": product_id}).fetchone()
    if not row:
        raise HTTPException(404, "PRICE_NOT_FOUND")
    return {"price": float(row[0])}

@router.post("/internal/rules/evaluate")
def internal_rules(event: dict, db=Depends(get_db)):
    token = event.get("card_token") or ""
    client_id = str(event.get("client_id") or "")
    azs_id = str(event.get("azs_id") or "")

    rows = db.execute(text("""
      SELECT id, selector, policy, value, priority, enabled
      FROM rules
      WHERE enabled = true AND (
        (scope='CARD'    AND subject_id=:token) OR
        (scope='CLIENT'  AND subject_id=:client) OR
        (scope='AZS'     AND subject_id=:azs) OR
        (scope='SEGMENT' AND subject_id=:segment)
      )
      ORDER BY priority ASC
    """), {"token": token, "client": client_id, "azs": azs_id,
           "segment": str(event.get("segment") or "")}).mappings().all()

    def _match_selector(ev: dict, sel: dict) -> bool:
        if not sel: return True
        for k, v in sel.items():
            e = ev.get(k)
            if isinstance(v, list):
                if e not in v: return False
            else:
                if e != v: return False
        return True

    for r in rows:
        if _match_selector(event, r["selector"] or {}):
            return {"decision": r["policy"], "rule_id": r["id"], "value": r.get("value")}
    return {"decision": "ALLOW"}
