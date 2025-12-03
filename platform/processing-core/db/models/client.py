import uuid

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base  # ВАЖНО: вместо app.db.base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    inn: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, default="ACTIVE")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
