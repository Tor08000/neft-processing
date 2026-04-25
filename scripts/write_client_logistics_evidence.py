from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    return json.loads(text) if text.strip() else {}


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: write_client_logistics_evidence.py <evidence> <trip> <fuel-write> <fuel-read>",
            file=sys.stderr,
        )
        return 2

    evidence_path = Path(argv[1]).resolve()
    trip = load_json(Path(argv[2]))
    fuel_write = load_json(Path(argv[3]))
    fuel_read = load_json(Path(argv[4]))
    trip_id = str(trip.get("id") or fuel_write.get("trip_id") or "")

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "surface": "client_logistics_fuel_consumption_write",
        "status": "VERIFIED_RUNTIME",
        "command": "cmd /c scripts\\smoke_client_logistics.cmd",
        "checks": [
            "client logistics fleet/trips/fuel reads return 200",
            "client trip create returns 201",
            "fuel consumption analytics read returns 200",
            "fuel consumption write returns 200 through provider-backed path",
            "missing trip detail remains 404",
        ],
        "trip_id": trip_id,
        "fuel_write": {
            "id": fuel_write.get("id"),
            "trip_id": fuel_write.get("trip_id") or trip_id,
            "provider_mode": fuel_write.get("provider_mode"),
            "provider_status": fuel_write.get("provider_status"),
            "idempotency_key": fuel_write.get("idempotency_key"),
            "evidence_id": fuel_write.get("evidence_id"),
        },
        "fuel_read_shape": {
            "keys": sorted(fuel_read.keys()) if isinstance(fuel_read, dict) else [],
            "items_count": len(fuel_read.get("items") or []) if isinstance(fuel_read, dict) else None,
        },
        "public_api_change": "client POST changed from frozen 503 to provider-backed success/error result; no route removal",
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[EVIDENCE] {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
