from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, String, Text, text

from app.db import Base
from app.db.types import GUID, new_uuid_str


class Partner(Base):
    __tablename__ = "partners"

    id = Column(GUID(), primary_key=True, default=new_uuid_str, index=True)
    name = Column(String(255), nullable=True)
    type = Column(String(32), nullable=True)
    allowed_ips = Column(JSON, default=list)
    token = Column(String(255), nullable=True)

    code = Column(Text, nullable=False, unique=True)
    legal_name = Column(Text, nullable=False)
    brand_name = Column(Text, nullable=True)
    partner_type = Column(Text, nullable=False)
    inn = Column(Text, nullable=True)
    ogrn = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    contacts = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        CheckConstraint(
            "partner_type IN ('FUEL_NETWORK','SERVICE_PROVIDER','EDO_PROVIDER','LOGISTICS_PROVIDER','OTHER')",
            name="ck_partners_partner_type_v1",
        ),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','PENDING')", name="ck_partners_status_v1"),
    )
