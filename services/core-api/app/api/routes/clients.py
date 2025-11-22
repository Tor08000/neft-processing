from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.client import ClientCreate
from app.services import client_service
from app.db.base import get_db

router = APIRouter(prefix='/clients', tags=['clients'])

@router.post('')
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    o = client_service.create(db, payload.name, payload.inn)
    return {'id': o.id, 'name': o.name, 'inn': o.inn, 'status': o.status}

@router.get('')
def list_clients(limit: int = 50, db: Session = Depends(get_db)):
    return [{'id': c.id, 'name': c.name, 'inn': c.inn, 'status': c.status} for c in client_service.list_(db, limit)]
