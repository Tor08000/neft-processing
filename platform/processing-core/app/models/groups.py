from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class ClientGroup(Base):
    __tablename__ = "client_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship(
        "ClientGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class CardGroup(Base):
    __tablename__ = "card_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship(
        "CardGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class ClientGroupMember(Base):
    __tablename__ = "client_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_group_id = Column(Integer, ForeignKey("client_groups.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group = relationship("ClientGroup", back_populates="members")

    __table_args__ = (UniqueConstraint("client_group_id", "client_id", name="uq_client_group_member"),)


class CardGroupMember(Base):
    __tablename__ = "card_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_group_id = Column(Integer, ForeignKey("card_groups.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group = relationship("CardGroup", back_populates="members")

    __table_args__ = (UniqueConstraint("card_group_id", "card_id", name="uq_card_group_member"),)
