from __future__ import annotations

from sqlalchemy import Column, DateTime, Numeric, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class PlatformRevenueEntry(Base):
    __tablename__ = "platform_revenue_entries"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), nullable=True, index=True)
    partner_id = Column(GUID(), nullable=True, index=True)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    fee_basis = Column(String(16), nullable=False)
    meta_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = ["PlatformRevenueEntry"]
