from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_BASE_DIR = Path("data/virtual_fuel_network")
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_STATE_FILE = "state.json"
DEFAULT_TX_FILE = "transactions.jsonl"


@dataclass(frozen=True)
class VirtualNetworkPaths:
    base_dir: Path
    config_path: Path
    state_path: Path
    transactions_path: Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_paths() -> VirtualNetworkPaths:
    base_dir = Path(os.getenv("VIRTUAL_FUEL_NETWORK_DIR", DEFAULT_BASE_DIR)).resolve()
    config_path = Path(os.getenv("VIRTUAL_FUEL_NETWORK_CONFIG", base_dir / DEFAULT_CONFIG_FILE)).resolve()
    state_path = Path(os.getenv("VIRTUAL_FUEL_NETWORK_STATE", base_dir / DEFAULT_STATE_FILE)).resolve()
    tx_path = Path(os.getenv("VIRTUAL_FUEL_NETWORK_TX", base_dir / DEFAULT_TX_FILE)).resolve()
    return VirtualNetworkPaths(
        base_dir=base_dir,
        config_path=config_path,
        state_path=state_path,
        transactions_path=tx_path,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return payload or {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class VirtualNetworkStore:
    def __init__(self, paths: VirtualNetworkPaths | None = None) -> None:
        self.paths = paths or resolve_paths()

    def load_config(self) -> dict[str, Any]:
        base = _load_yaml(self.paths.config_path)
        overlay = _load_json(self.paths.state_path)
        config = _deep_merge(base, overlay)
        config.setdefault("seed", 7)
        config.setdefault("deterministic", True)
        config.setdefault("stations", [])
        config.setdefault("prices", {})
        config.setdefault("anomalies", [])
        config.setdefault("delays", {})
        config.setdefault("cards", [])
        config.setdefault("blocked_cards", {})
        return config

    def update_state(self, updates: dict[str, Any]) -> dict[str, Any]:
        state = _load_json(self.paths.state_path)
        state = _deep_merge(state, updates)
        _write_json(self.paths.state_path, state)
        return state

    def reset_state(self) -> None:
        if self.paths.state_path.exists():
            self.paths.state_path.unlink()

    def append_transactions(self, rows: list[dict[str, Any]]) -> None:
        self.paths.transactions_path.parent.mkdir(parents=True, exist_ok=True)
        with self.paths.transactions_path.open("a", encoding="utf-8") as handle:
            for row in rows:
                if not row.get("created_at"):
                    row["created_at"] = _now_iso()
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")

    def list_transactions(
        self,
        *,
        since: datetime,
        until: datetime,
        cursor: str | None,
        limit: int,
        client_id: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not self.paths.transactions_path.exists():
            return [], None
        offset = 0
        if cursor:
            try:
                offset = int(cursor)
            except ValueError:
                offset = 0
        rows: list[dict[str, Any]] = []
        with self.paths.transactions_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                occurred_at_raw = payload.get("occurred_at")
                if not occurred_at_raw:
                    continue
                occurred_at = datetime.fromisoformat(occurred_at_raw)
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=timezone.utc)
                if occurred_at < since or occurred_at >= until:
                    continue
                if client_id and payload.get("client_id") and payload.get("client_id") != client_id:
                    continue
                rows.append(payload)
        rows.sort(key=lambda item: item.get("occurred_at") or "")
        paged = rows[offset : offset + limit]
        next_cursor = None
        if offset + limit < len(rows):
            next_cursor = str(offset + limit)
        return paged, next_cursor
