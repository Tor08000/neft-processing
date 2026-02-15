from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint, func

from app.db import Base


class StationElasticity(Base):
    __tablename__ = "station_elasticity"
    __table_args__ = (
        UniqueConstraint("station_id", "product_code", "window_days", name="uq_station_elasticity_station_product_window"),
        Index("ix_station_elasticity_window", "window_days"),
        Index("ix_station_elasticity_station_window", "station_id", "window_days"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(36), nullable=False)
    product_code = Column(String(64), nullable=False, default="", server_default="")
    window_days = Column(Integer, nullable=False)
    elasticity_score = Column(Float, nullable=False, default=0, server_default="0")
    elasticity_abs = Column(Float, nullable=False, default=0, server_default="0")
    confidence_score = Column(Float, nullable=False, default=0, server_default="0")
    sample_points = Column(Integer, nullable=False, default=0, server_default="0")
    total_volume = Column(Float, nullable=False, default=0, server_default="0")
    notes = Column(String(64), nullable=False, default="OK", server_default="OK")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
