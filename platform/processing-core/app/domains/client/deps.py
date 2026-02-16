from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.client.repo import ClientRepository
from app.security.client_auth import require_client_user


def get_current_client_user(token: dict = Depends(require_client_user)) -> dict:
    return token


def get_client_context(
    token: dict = Depends(get_current_client_user),
    db: Session = Depends(get_db),
) -> tuple[dict, ClientRepository]:
    return token, ClientRepository(db=db)
