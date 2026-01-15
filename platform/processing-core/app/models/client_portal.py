from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, ExistingEnum, new_uuid_str


class ClientCard(Base):
    __tablename__ = "client_cards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    card_id = Column(String, nullable=False, index=True)
    pan_masked = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClientOperation(Base):
    __tablename__ = "client_operations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    card_id = Column(String, nullable=True, index=True)
    operation_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fuel_type = Column(String, nullable=True)


class ClientLimit(Base):
    __tablename__ = "client_limits"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    limit_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    used_amount = Column(Numeric, nullable=True, server_default="0")
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)


class CardAccessScope(str, Enum):
    VIEW = "VIEW"
    USE = "USE"
    MANAGE = "MANAGE"


class CardAccess(Base):
    __tablename__ = "card_access"
    __table_args__ = (UniqueConstraint("card_id", "user_id", name="uq_card_access_user_card"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    card_id = Column(String, nullable=False, index=True)
    scope = Column(ExistingEnum(CardAccessScope, name="card_access_scope"), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    effective_to = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CardLimit(Base):
    __tablename__ = "card_limits"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    card_id = Column(String, nullable=False, index=True)
    limit_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientUserRole(Base):
    __tablename__ = "client_user_roles"
    __table_args__ = (UniqueConstraint("client_id", "user_id", name="uq_client_user_role"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    roles = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
