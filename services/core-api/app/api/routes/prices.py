from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.deps.db import get_db

router = APIRouter(prefix='/prices', tags=['prices'])

@router.get('/active')
def active_price(azs_name: str = 'АЗС-1', product_code: str = 'AI95', db: Session = Depends(get_db)):
    row = db.execute(text("""
    SELECT pl.price FROM price_list pl
    JOIN azs a ON a.id=pl.azs_id
    JOIN products p ON p.id=pl.product_id
    WHERE a.name=:azs AND p.code=:code
      AND pl.status='ACTIVE' AND pl.start_at<=now() AND pl.end_at>=now()
    ORDER BY pl.start_at DESC LIMIT 1
    """), {'azs': azs_name, 'code': product_code}).first()
    if not row:
        raise HTTPException(404, 'price not found')
    return {'price': float(row[0])}
