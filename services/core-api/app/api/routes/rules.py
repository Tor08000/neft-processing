from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from app.db.base import get_db

router = APIRouter(prefix='/rules', tags=['rules'])

class SimIn(BaseModel):
    tenant_id: int = 1
    card_token: str
    qty: float = 0

@router.post('/simulate')
def simulate(b: SimIn, db: Session = Depends(get_db)):
    rule = db.execute(text("SELECT value,policy FROM rules WHERE scope='CARD' AND subject_id=:t AND enabled=true AND metric='LITERS' ORDER BY priority ASC LIMIT 1"), {'t': b.card_token}).first()
    if not rule:
        return {'decision': 'ALLOW', 'limit': None, 'used': 0, 'remain': None}
    value, policy = float(rule[0]), rule[1]
    used = db.execute(text("SELECT COALESCE(SUM(qty),0) FROM transactions t JOIN cards c ON c.id=t.card_id WHERE c.token=:t AND t.auth_ts>=date_trunc('day',now()) AND t.state IN ('PRE_AUTH','CAPTURED','SETTLED')"), {'t': b.card_token}).scalar() or 0.0
    remain = max(0.0, value - float(used))
    decision = 'ALLOW' if b.qty <= remain else ('DECLINE' if policy.startswith('HARD') else 'SOFT_DECLINE')
    return {'decision': decision, 'limit': value, 'used': float(used), 'remain': remain}
