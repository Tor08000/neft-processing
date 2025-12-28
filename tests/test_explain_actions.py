import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_CORE = ROOT / "platform" / "processing-core"
sys.path.insert(0, str(PROCESSING_CORE))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/test")

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions import build_actions


def test_action_hint_limit():
    actions = build_actions(PrimaryReason.LIMIT)

    assert [action.model_dump() for action in actions] == [
        {
            "code": "INCREASE_LIMIT",
            "title": "Increase limit",
            "description": "Fuel limit exceeded for this period",
            "target": "CRM",
            "severity": "REQUIRED",
        }
    ]


def test_action_hint_risk():
    actions = build_actions(PrimaryReason.RISK)

    assert [action.model_dump() for action in actions] == [
        {
            "code": "REQUEST_OVERRIDE",
            "title": "Request risk override",
            "description": "Operation blocked by risk policy",
            "target": "COMPLIANCE",
            "severity": "REQUIRED",
        }
    ]


def test_action_hint_logistics():
    actions = build_actions(PrimaryReason.LOGISTICS)

    assert [action.model_dump() for action in actions] == [
        {
            "code": "ADJUST_ROUTE",
            "title": "Adjust route",
            "description": "Fuel usage detected outside approved route",
            "target": "ROUTES",
            "severity": "INFO",
        }
    ]


def test_secondary_reasons_do_not_affect_actions():
    actions = build_actions(PrimaryReason.LIMIT)

    assert actions[0].code == "INCREASE_LIMIT"
