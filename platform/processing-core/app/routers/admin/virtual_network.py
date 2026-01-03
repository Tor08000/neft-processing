from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import random
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.fuel.providers.virtual_network.store import VirtualNetworkStore
from app.models.fuel import FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationNetwork, FuelStationStatus
from app.schemas.virtual_network import (
    VirtualNetworkConfigOut,
    VirtualNetworkEnableAnomaliesIn,
    VirtualNetworkEnableAnomaliesOut,
    VirtualNetworkGenerateTxnsIn,
    VirtualNetworkGenerateTxnsOut,
    VirtualNetworkReloadOut,
    VirtualNetworkSeedStationsIn,
    VirtualNetworkSeedStationsOut,
    VirtualNetworkSetPricesIn,
    VirtualNetworkSetPricesOut,
)

router = APIRouter(prefix="/virtual-network", tags=["admin", "virtual-network"])

PROVIDER_CODE = "virtual_fuel_network"
DEFAULT_PRODUCTS = {
    "AI92": Decimal("55.10"),
    "AI95": Decimal("60.20"),
    "DT": Decimal("62.00"),
    "GAS": Decimal("32.50"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_station_coords(rng: random.Random) -> tuple[str, str]:
    lat = 55.5 + rng.random() * 1.2
    lon = 37.3 + rng.random() * 1.2
    return f"{lat:.6f}", f"{lon:.6f}"


def _ensure_network(db: Session) -> FuelNetwork:
    network = db.query(FuelNetwork).filter(FuelNetwork.provider_code == PROVIDER_CODE).one_or_none()
    if network:
        return network
    network = FuelNetwork(name="Virtual Fuel Network", provider_code=PROVIDER_CODE, status=FuelNetworkStatus.ACTIVE)
    db.add(network)
    db.flush()
    return network


def _ensure_station_network(db: Session, *, brand: str | None) -> FuelStationNetwork:
    name = brand or "Virtual Network"
    station_network = db.query(FuelStationNetwork).filter(FuelStationNetwork.name == name).one_or_none()
    if station_network:
        return station_network
    station_network = FuelStationNetwork(name=name, meta={"brand": brand} if brand else None)
    db.add(station_network)
    db.flush()
    return station_network


@router.get("/config", response_model=VirtualNetworkConfigOut)
def get_config() -> VirtualNetworkConfigOut:
    store = VirtualNetworkStore()
    return VirtualNetworkConfigOut(config=store.load_config())


@router.post("/config/reload", response_model=VirtualNetworkReloadOut)
def reload_config() -> VirtualNetworkReloadOut:
    store = VirtualNetworkStore()
    config = store.load_config()
    return VirtualNetworkReloadOut(status="reloaded", config=config)


@router.post("/stations/seed", response_model=VirtualNetworkSeedStationsOut)
def seed_stations(payload: VirtualNetworkSeedStationsIn, db: Session = Depends(get_db)) -> VirtualNetworkSeedStationsOut:
    store = VirtualNetworkStore()
    config = store.load_config()
    existing = config.get("stations") or []
    rng = random.Random(payload.seed if payload.seed is not None else config.get("seed", 7))
    created: list[dict[str, Any]] = []
    for idx in range(payload.count):
        station_id = f"VN-{len(existing) + idx + 1:04d}"
        lat, lon = _seed_station_coords(rng)
        station = {
            "station_id": station_id,
            "name": f"Virtual Station {len(existing) + idx + 1}",
            "brand": payload.brand or "VirtualFuel",
            "geo": {"lat": lat, "lon": lon},
            "region": payload.region or "Moscow",
            "city": payload.city or "Moscow",
            "services": {"wash": rng.random() > 0.6, "cafe": rng.random() > 0.5},
            "terminals": rng.randint(2, 6),
        }
        created.append(station)
    merged = existing + created
    store.update_state({"stations": merged})

    if payload.persist_db:
        network = _ensure_network(db)
        station_network = _ensure_station_network(db, brand=payload.brand)
        for station in created:
            existing_row = (
                db.query(FuelStation)
                .filter(FuelStation.network_id == network.id)
                .filter(FuelStation.station_code == station["station_id"])
                .one_or_none()
            )
            if existing_row:
                continue
            db.add(
                FuelStation(
                    network_id=network.id,
                    station_network_id=station_network.id,
                    station_code=station["station_id"],
                    name=station["name"],
                    country="RU",
                    region=station.get("region"),
                    city=station.get("city"),
                    lat=station.get("geo", {}).get("lat"),
                    lon=station.get("geo", {}).get("lon"),
                    status=FuelStationStatus.ACTIVE,
                )
            )
        db.commit()
    return VirtualNetworkSeedStationsOut(created=len(created), stations=created)


@router.post("/prices/set", response_model=VirtualNetworkSetPricesOut)
def set_prices(payload: VirtualNetworkSetPricesIn) -> VirtualNetworkSetPricesOut:
    store = VirtualNetworkStore()
    normalized = {
        station_id: {product: str(price) for product, price in products.items()}
        for station_id, products in payload.prices.items()
    }
    store.update_state({"prices": normalized})
    return VirtualNetworkSetPricesOut(updated=len(normalized))


@router.post("/anomalies/enable", response_model=VirtualNetworkEnableAnomaliesOut)
def enable_anomalies(payload: VirtualNetworkEnableAnomaliesIn) -> VirtualNetworkEnableAnomaliesOut:
    store = VirtualNetworkStore()
    store.update_state({"anomalies": payload.anomalies})
    return VirtualNetworkEnableAnomaliesOut(updated=len(payload.anomalies))


@router.post("/txns/generate", response_model=VirtualNetworkGenerateTxnsOut)
def generate_txns(payload: VirtualNetworkGenerateTxnsIn) -> VirtualNetworkGenerateTxnsOut:
    store = VirtualNetworkStore()
    config = store.load_config()
    rng = random.Random(payload.seed if payload.seed is not None else config.get("seed", 7))

    stations = config.get("stations") or []
    station_ids = [station.get("station_id") for station in stations if station.get("station_id")]
    station_lookup = {station.get("station_id"): station for station in stations}

    start_at = payload.start_at or _now()
    end_at = payload.end_at or start_at
    start_ts = start_at.timestamp()
    end_ts = end_at.timestamp()
    if end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts

    items: list[dict[str, Any]] = []
    prices = config.get("prices") or {}
    for idx in range(payload.count):
        station_id = payload.station_id or rng.choice(station_ids) if station_ids else "VN-0001"
        station = station_lookup.get(station_id) or {}
        product_prices = prices.get(station_id) or DEFAULT_PRODUCTS
        unit_price = Decimal(str(product_prices.get("AI95") or list(product_prices.values())[0]))
        liters = payload.liters if payload.liters is not None else Decimal("25")
        amount = payload.amount if payload.amount is not None else (unit_price * liters)
        occurred_at = datetime.fromtimestamp(rng.uniform(start_ts, end_ts), tz=timezone.utc)
        provider_tx_id = f"VN-{uuid4()}"
        raw_payload = {
            "provider_tx_id": provider_tx_id,
            "provider_card_id": payload.card_alias,
            "card_alias": payload.card_alias,
            "station_id": station_id,
            "product": "AI95",
            "virtual_anomalies": [payload.anomaly_type] if payload.anomaly_type else [],
        }
        items.append(
            {
                "provider_tx_id": provider_tx_id,
                "provider_card_id": payload.card_alias,
                "occurred_at": occurred_at.isoformat(),
                "amount": str(amount),
                "currency": payload.currency,
                "volume_liters": str(liters),
                "category": "FUEL",
                "merchant_name": station.get("name") or "Virtual Fuel Station",
                "station_id": station_id,
                "location": station.get("city") or station.get("region"),
                "raw_payload": raw_payload,
                "client_id": payload.client_id,
            }
        )
    store.append_transactions(items)
    return VirtualNetworkGenerateTxnsOut(created=len(items), items=items)
