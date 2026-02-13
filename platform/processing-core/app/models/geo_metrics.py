from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func

from app.db import Base


class GeoStationMetricsDaily(Base):
    __tablename__ = "geo_station_metrics_daily"
    __table_args__ = (
        UniqueConstraint("day", "station_id", name="uq_geo_station_metrics_daily_day_station"),
        Index("ix_geo_station_metrics_daily_day", "day"),
        Index("ix_geo_station_metrics_daily_station_day", "station_id", "day"),
        Index("ix_geo_station_metrics_daily_day_amount_sum", "day", "amount_sum"),
        Index("ix_geo_station_metrics_daily_day_tx_count", "day", "tx_count"),
    )

    day = Column(Date, primary_key=True, nullable=False)
    station_id = Column(String(36), primary_key=True, nullable=False)
    tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    captured_count = Column(Integer, nullable=False, default=0, server_default="0")
    declined_count = Column(Integer, nullable=False, default=0, server_default="0")
    amount_sum = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    liters_sum = Column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    risk_red_count = Column(Integer, nullable=False, default=0, server_default="0")
    risk_yellow_count = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
