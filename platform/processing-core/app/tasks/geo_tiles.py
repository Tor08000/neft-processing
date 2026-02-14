from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.celery_client import celery_client
from app.db import SessionLocal
from app.services.geo_analytics import (
    build_geo_overlay_tiles_for_day,
    build_geo_tiles_for_day,
    geo_overlay_tiles_backfill,
    geo_tiles_backfill,
)

ZOOMS = [8, 10, 12]


@celery_client.task(name="geo.tiles_refresh")
def geo_tiles_refresh_task(zooms: list[int] | None = None) -> dict[str, object]:
    target_zooms = zooms or ZOOMS
    today = datetime.now(tz=timezone.utc).date()
    days = [today, today - timedelta(days=1)]
    built: list[dict[str, object]] = []

    with SessionLocal() as db:
        for day in days:
            for zoom in target_zooms:
                count = build_geo_tiles_for_day(db, day=day, zoom=zoom)
                built.append({"day": day.isoformat(), "zoom": zoom, "tiles": count})

    return {"built": built}


@celery_client.task(name="geo.tiles_backfill")
def geo_tiles_backfill_task(
    days: int = 7, zooms: list[int] | None = None
) -> dict[str, object]:
    target_zooms = zooms or ZOOMS
    with SessionLocal() as db:
        rebuilt = geo_tiles_backfill(db, days=days, zooms=target_zooms)
    return {
        "days": days,
        "zooms": target_zooms,
        "rebuilt": [
            {"day": day.isoformat(), "zoom": zoom, "tiles": count}
            for day, zoom, count in rebuilt
        ],
    }


@celery_client.task(name="geo.tiles_overlays_refresh")
def geo_tiles_overlays_refresh_task(
    zooms: list[int] | None = None,
) -> dict[str, object]:
    target_zooms = zooms or ZOOMS
    today = datetime.now(tz=timezone.utc).date()
    days = [today, today - timedelta(days=1)]
    built: list[dict[str, object]] = []

    with SessionLocal() as db:
        for day in days:
            for zoom in target_zooms:
                count = build_geo_overlay_tiles_for_day(db, day=day, zoom=zoom)
                built.append({"day": day.isoformat(), "zoom": zoom, "tiles": count})

    return {"built": built}


@celery_client.task(name="geo.tiles_overlays_backfill")
def geo_tiles_overlays_backfill_task(
    days: int = 7, zooms: list[int] | None = None
) -> dict[str, object]:
    target_zooms = zooms or ZOOMS
    with SessionLocal() as db:
        rebuilt = geo_overlay_tiles_backfill(db, days=days, zooms=target_zooms)
    return {
        "days": days,
        "zooms": target_zooms,
        "rebuilt": [
            {"day": day.isoformat(), "zoom": zoom, "tiles": count}
            for day, zoom, count in rebuilt
        ],
    }


__all__ = [
    "geo_tiles_refresh_task",
    "geo_tiles_backfill_task",
    "geo_tiles_overlays_refresh_task",
    "geo_tiles_overlays_backfill_task",
    "ZOOMS",
]
