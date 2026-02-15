from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, func, Index, UniqueConstraint

from app.db import Base


class StationMarginDay(Base):
    __tablename__ = "station_margin_day"
    __table_args__ = (
        UniqueConstraint("day", "station_id", name="uq_station_margin_day_day_station"),
        Index("ix_station_margin_day_day", "day"),
        Index("ix_station_margin_day_station_day", "station_id", "day"),
    )

    day = Column(Date, primary_key=True, nullable=False)
    station_id = Column(String(36), primary_key=True, nullable=False)
    revenue_sum = Column(Float, nullable=False, default=0, server_default="0")
    cost_sum = Column(Float, nullable=False, default=0, server_default="0")
    gross_margin = Column(Float, nullable=False, default=0, server_default="0")
    tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
