from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingDataset:
    rows: list[dict]
    schema_version: str
    dataset_hash: str


def build_dataset(*, shadow_rows: list[dict], schema_version: str) -> TrainingDataset:
    payload = {
        "schema_version": schema_version,
        "rows": shadow_rows,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    dataset_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return TrainingDataset(rows=shadow_rows, schema_version=schema_version, dataset_hash=dataset_hash)


__all__ = ["TrainingDataset", "build_dataset"]
