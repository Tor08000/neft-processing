from sqlalchemy.orm import Session
from app.db.models.client import Client

def create_client(db: Session, name: str, inn: str|None):
    obj = Client(name=name, inn=inn)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_clients(db: Session, limit: int=50):
    return db.query(Client).order_by(Client.id.desc()).limit(limit).all()
