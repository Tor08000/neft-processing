from __future__ import annotations

from app.models.decision_memory import DecisionActionStatsDaily, DecisionOutcome
from app.models.fleet_intelligence import (
    FIDriverDaily,
    FIDriverScore,
    FIStationDaily,
    FIStationTrustScore,
    FITrendSnapshot,
    FIVehicleDaily,
    FIVehicleEfficiencyScore,
)
from app.models.fleet_intelligence_actions import FIActionEffect, FIAppliedAction, FIInsight, FISuggestedAction
from app.models.unified_explain import UnifiedExplainSnapshot
from app.tests._crm_test_harness import (
    CRM_FUEL_INTEGRATION_TEST_TABLES,
    CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES,
)
from app.tests._logistics_route_harness import LOGISTICS_FUEL_TEST_TABLES


def _dedupe_tables(*tables):
    seen: set[str] = set()
    ordered = []
    for table in tables:
        key = str(table.key)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(table)
    return tuple(ordered)


EXPLAIN_UNIFIED_FUEL_TEST_TABLES = _dedupe_tables(
    *CRM_FUEL_INTEGRATION_TEST_TABLES,
    *CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES,
    *LOGISTICS_FUEL_TEST_TABLES,
    DecisionActionStatsDaily.__table__,
    DecisionOutcome.__table__,
    FIActionEffect.__table__,
    FIAppliedAction.__table__,
    FIDriverDaily.__table__,
    FIDriverScore.__table__,
    FIInsight.__table__,
    FIStationDaily.__table__,
    FIStationTrustScore.__table__,
    FISuggestedAction.__table__,
    FITrendSnapshot.__table__,
    FIVehicleDaily.__table__,
    FIVehicleEfficiencyScore.__table__,
    UnifiedExplainSnapshot.__table__,
)


__all__ = ["EXPLAIN_UNIFIED_FUEL_TEST_TABLES"]
