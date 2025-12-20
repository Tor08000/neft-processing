from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db import Base


class PostingBatchStatus(str, Enum):
    APPLIED = "APPLIED"
    REVERSED = "REVERSED"


class PostingBatchType(str, Enum):
    AUTH = "AUTH"
    HOLD = "HOLD"
    COMMIT = "COMMIT"
    CAPTURE = "CAPTURE"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    ADJUSTMENT = "ADJUSTMENT"


class PostingBatch(Base):
    __tablename__ = "posting_batches"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    operation_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    posting_type = Column(SAEnum(PostingBatchType), nullable=False)
    status = Column(SAEnum(PostingBatchStatus), nullable=False, default=PostingBatchStatus.APPLIED)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<PostingBatch id={self.id} type={self.posting_type} status={self.status}>"
