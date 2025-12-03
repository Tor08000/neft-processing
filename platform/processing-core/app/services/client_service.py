from sqlalchemy.orm import Session
from app.repositories.client_repo import create_client, list_clients

def create(db: Session, name: str, inn: str|None):
    return create_client(db, name, inn)

def list_(db: Session, limit: int=50):
    return list_clients(db, limit)
