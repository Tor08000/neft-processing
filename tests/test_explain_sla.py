import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_CORE = ROOT / "platform" / "processing-core"
sys.path.insert(0, str(PROCESSING_CORE))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/test")

from app.models.unified_explain import PrimaryReason
from app.services.explain.sla import build_sla


def test_sla_limit_snapshot():
    started_at = datetime(2025, 1, 10, 10, 15, tzinfo=timezone.utc)
    now = datetime(2025, 1, 10, 11, 15, tzinfo=timezone.utc)

    sla = build_sla(PrimaryReason.LIMIT, started_at=started_at, now=now)

    assert sla is not None
    assert sla.started_at == "2025-01-10T10:15:00Z"
    assert sla.expires_at == "2025-01-11T10:15:00Z"
    assert sla.remaining_minutes == 1380


def test_sla_secondary_reasons_do_not_affect_primary():
    started_at = datetime(2025, 1, 10, 10, 15, tzinfo=timezone.utc)

    sla = build_sla(PrimaryReason.RISK, started_at=started_at, now=started_at)

    assert sla is not None
    assert sla.remaining_minutes == 120
