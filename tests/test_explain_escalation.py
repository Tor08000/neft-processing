import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_CORE = ROOT / "platform" / "processing-core"
sys.path.insert(0, str(PROCESSING_CORE))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/test")

from app.models.unified_explain import PrimaryReason
from app.services.explain.escalation import build_escalation


def test_escalation_target_limit():
    escalation = build_escalation(PrimaryReason.LIMIT)

    assert escalation is not None
    assert escalation.target == "CRM"
    assert escalation.status == "PENDING"


def test_escalation_target_risk():
    escalation = build_escalation(PrimaryReason.RISK)

    assert escalation is not None
    assert escalation.target == "COMPLIANCE"
    assert escalation.status == "PENDING"


def test_escalation_target_logistics():
    escalation = build_escalation(PrimaryReason.LOGISTICS)

    assert escalation is not None
    assert escalation.target == "LOGISTICS"
    assert escalation.status == "PENDING"


def test_secondary_reasons_do_not_affect_escalation():
    escalation = build_escalation(PrimaryReason.MONEY)

    assert escalation is not None
    assert escalation.target == "FINANCE"
