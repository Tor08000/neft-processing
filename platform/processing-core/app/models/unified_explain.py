from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, JSON, String, UniqueConstraint, func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class UnifiedExplainSnapshot(Base):
    __tablename__ = "unified_explain_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "snapshot_hash",
            name="uq_unified_explain_snapshots_scope",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    subject_type = Column(String(64), nullable=False)
    subject_id = Column(String(128), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(String(64), nullable=True)


__all__ = ["UnifiedExplainSnapshot"]
