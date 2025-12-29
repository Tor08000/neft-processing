from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.db import Base


class FleetActionEffectStats(Base):
    __tablename__ = "fleet_action_effect_stats"

    action_code = Column(String(128), primary_key=True)
    insight_type = Column(String(32), primary_key=True)
    window_days = Column(Integer, primary_key=True)
    applied_count = Column(Integer, nullable=False, default=0)
    improved_count = Column(Integer, nullable=False, default=0)
    no_change_count = Column(Integer, nullable=False, default=0)
    worsened_count = Column(Integer, nullable=False, default=0)
    avg_effect_delta = Column(Numeric, nullable=True)
    last_computed_at = Column(DateTime(timezone=True), nullable=True)


__all__ = ["FleetActionEffectStats"]
