from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)

from app.db import Base


class GeoStationMetricsDaily(Base):
    __tablename__ = "geo_station_metrics_daily"
    __table_args__ = (
        UniqueConstraint(
            "day", "station_id", name="uq_geo_station_metrics_daily_day_station"
        ),
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
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GeoTilesDaily(Base):
    __tablename__ = "geo_tiles_daily"
    __table_args__ = (
        UniqueConstraint(
            "day", "zoom", "tile_x", "tile_y", name="uq_geo_tiles_daily_day_zoom_tile"
        ),
        Index("ix_geo_tiles_daily_day_zoom_tile", "day", "zoom", "tile_x", "tile_y"),
    )

    day = Column(Date, primary_key=True, nullable=False)
    zoom = Column(SmallInteger, primary_key=True, nullable=False)
    tile_x = Column(Integer, primary_key=True, nullable=False)
    tile_y = Column(Integer, primary_key=True, nullable=False)
    tx_count = Column(Integer, nullable=False, default=0, server_default="0")
    captured_count = Column(Integer, nullable=False, default=0, server_default="0")
    declined_count = Column(Integer, nullable=False, default=0, server_default="0")
    amount_sum = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    liters_sum = Column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    risk_red_count = Column(Integer, nullable=False, default=0, server_default="0")
    risk_yellow_count = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GeoTilesDailyOverlay(Base):
    __tablename__ = "geo_tiles_daily_overlays"
    __table_args__ = (
        UniqueConstraint(
            "day",
            "zoom",
            "tile_x",
            "tile_y",
            "overlay_kind",
            name="uq_geo_tiles_daily_overlays_day_zoom_tile_kind",
        ),
        Index(
            "ix_geo_tiles_daily_overlays_day_zoom_kind_tile",
            "day",
            "zoom",
            "overlay_kind",
            "tile_x",
            "tile_y",
        ),
    )

    day = Column(Date, primary_key=True, nullable=False)
    zoom = Column(SmallInteger, primary_key=True, nullable=False)
    tile_x = Column(Integer, primary_key=True, nullable=False)
    tile_y = Column(Integer, primary_key=True, nullable=False)
    overlay_kind = Column(String(32), primary_key=True, nullable=False)
    value = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
