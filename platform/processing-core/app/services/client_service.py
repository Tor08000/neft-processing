from sqlalchemy.orm import Session

from app.repositories.client_repo import create_client, list_clients
from app.services.subscription_service import DEFAULT_TENANT_ID, ensure_free_subscription

def create(db: Session, name: str, inn: str | None):
    client = create_client(db, name, inn)
    ensure_free_subscription(db, tenant_id=DEFAULT_TENANT_ID, client_id=str(client.id))
    return client

def list_(db: Session, limit: int = 50):
    return list_clients(db, limit)
