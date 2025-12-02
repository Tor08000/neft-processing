from uuid import uuid4

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class ClearingBatchOperation(Base):
    __tablename__ = "clearing_batch_operation"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String(36), ForeignKey("clearing_batch.id"), nullable=False, index=True)
    operation_id = Column(String(64), ForeignKey("operations.operation_id"), nullable=False)
    amount = Column(Integer, nullable=False)

    batch = relationship("ClearingBatch", backref="operations")
