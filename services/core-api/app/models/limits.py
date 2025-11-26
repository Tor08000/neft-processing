from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db import Base


class ClientGroup(Base):
    __tablename__ = "client_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    memberships = relationship(
        "ClientGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class CardGroup(Base):
    __tablename__ = "card_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    memberships = relationship(
        "CardGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class ClientGroupMembership(Base):
    __tablename__ = "client_group_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("client_groups.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(64), nullable=False, index=True)

    group = relationship("ClientGroup", back_populates="memberships")


class CardGroupMembership(Base):
    __tablename__ = "card_group_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("card_groups.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(String(64), nullable=False, index=True)

    group = relationship("CardGroup", back_populates="memberships")


class LimitRule(Base):
    __tablename__ = "limits_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=0)
    daily_limit = Column(Integer, nullable=False)
    limit_per_tx = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False, default="RUB")

    client_group_id = Column(Integer, ForeignKey("client_groups.id", ondelete="SET NULL"), nullable=True)
    card_group_id = Column(Integer, ForeignKey("card_groups.id", ondelete="SET NULL"), nullable=True)

    client_group = relationship("ClientGroup")
    card_group = relationship("CardGroup")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
