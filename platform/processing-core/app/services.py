from sqlalchemy import text

from app.models.audit_log import ActorType, AuditVisibility
from app.services.audit_service import AuditService, RequestContext

def resolve_price(db, azs_id: int, product_id: int):
    row = db.execute(text("""
      SELECT price FROM price_list
      WHERE azs_id=:azs AND product_id=:prod AND status='ACTIVE'
        AND (start_at IS NULL OR start_at <= now())
        AND (end_at   IS NULL OR end_at   >= now())
      ORDER BY version DESC, id DESC LIMIT 1
    """), {"azs": azs_id, "prod": product_id}).fetchone()
    return float(row[0]) if row else None

def evaluate_rules(event: dict, rules: list[dict]) -> dict:
    def _match(ev, sel):
        if not sel: return True
        for k, v in sel.items():
            e = ev.get(k)
            if isinstance(v, list):
                if e not in v: return False
            else:
                if e != v: return False
        return True
    actives = [r for r in rules if r.get("enabled", True)]
    actives.sort(key=lambda r: r.get("priority", 100))
    for r in actives:
        if _match(event, r.get("selector") or {}):
            return {"decision": r.get("policy","ALLOW"), "rule_id": r.get("id"), "value": r.get("value")}
    return {"decision": "ALLOW"}

def audit_log(db, actor: str, action: str, target: str, payload: dict):
    AuditService(db).audit(
        event_type=str(action),
        entity_type="operation",
        entity_id=str(target),
        action=str(action),
        visibility=AuditVisibility.INTERNAL,
        after=payload,
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id=str(actor)),
    )
    db.commit()
