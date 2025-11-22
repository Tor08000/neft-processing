# services/core-api/app/deps/db.py
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    DI-зависимость для FastAPI:
    выдаёт Session и гарантированно закрывает её.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
