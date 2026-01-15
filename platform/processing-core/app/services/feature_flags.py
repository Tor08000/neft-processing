from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.feature_flags import FeatureFlag


def is_enabled(db: Session, key: str, *, default: bool = False) -> bool:
    record = db.query(FeatureFlag).filter(FeatureFlag.key == key).one_or_none()
    if record is None:
        return default
    return bool(record.on)


__all__ = ["is_enabled"]
