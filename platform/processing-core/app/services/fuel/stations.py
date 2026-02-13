from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from app.models.fuel import FuelStation


@dataclass(frozen=True)
class NearestStationsQuery:
    lat: float
    lon: float
    radius_km: float
    limit: int
    only_with_coords: bool = True
    status: str | None = None
    partner_id: int | None = None


@dataclass(frozen=True)
class NearestStationResult:
    station: FuelStation
    distance_km: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_earth_km = 6371.0

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad

    haversine = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lon / 2) ** 2
    return 2 * radius_earth_km * asin(sqrt(haversine))


def _bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    delta_lat = radius_km / 111.0
    lat_rad = radians(lat)
    cos_lat = max(abs(cos(lat_rad)), 1e-6)
    delta_lon = radius_km / (111.0 * cos_lat)

    return lat - delta_lat, lat + delta_lat, lon - delta_lon, lon + delta_lon


def find_nearest_stations(db: Session, query: NearestStationsQuery) -> list[NearestStationResult]:
    min_lat, max_lat, min_lon, max_lon = _bounding_box(query.lat, query.lon, query.radius_km)
    candidate_limit = min(query.limit * 50, 2000)

    stmt = db.query(FuelStation)

    if query.only_with_coords:
        stmt = stmt.filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))

    stmt = stmt.filter(
        FuelStation.lat >= min_lat,
        FuelStation.lat <= max_lat,
        FuelStation.lon >= min_lon,
        FuelStation.lon <= max_lon,
    )

    if query.status is not None:
        stmt = stmt.filter(FuelStation.status == query.status)

    # partner_id relation for station is absent in current model; intentionally ignored in MVP.
    _ = query.partner_id

    candidates = stmt.limit(candidate_limit).all()

    nearest: list[NearestStationResult] = []
    for station in candidates:
        if station.lat is None or station.lon is None:
            continue
        distance = haversine_km(query.lat, query.lon, station.lat, station.lon)
        if distance <= query.radius_km:
            nearest.append(NearestStationResult(station=station, distance_km=distance))

    nearest.sort(key=lambda item: item.distance_km)
    return nearest[: query.limit]
