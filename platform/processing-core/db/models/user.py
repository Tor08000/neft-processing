from sqlalchemy import BigInteger, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base  # вместо app.db.base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="admin")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
