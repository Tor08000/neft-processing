from __future__ import annotations

from app.models.audit_log import AuditLog
from app.models.crm import CRMClient, CRMContract, CRMFeatureFlag, CRMSubscription
from app.models.decision_memory import DecisionActionStatsDaily, DecisionOutcome
from app.models.fleet_decision_choice import FleetActionEffectStats
from app.models.fleet import FleetDriver, FleetVehicle
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
from app.models.fuel import FuelCard, FuelFraudSignal, FuelNetwork, FuelStation, FuelTransaction, StationReputationDaily
from app.models.logistics import (
    FuelRouteLink,
    LogisticsOrder,
    LogisticsRiskSignal,
    LogisticsRoute,
    LogisticsStop,
)
from app.models.legal_graph import LegalEdge, LegalNode
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLink


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


FLEET_INTELLIGENCE_CONTROL_TEST_TABLES = _dedupe_tables(
    AuditLog.__table__,
    CRMClient.__table__,
    CRMContract.__table__,
    CRMFeatureFlag.__table__,
    CRMSubscription.__table__,
    DecisionOutcome.__table__,
    DecisionActionStatsDaily.__table__,
    FIDriverDaily.__table__,
    FIDriverScore.__table__,
    FIStationDaily.__table__,
    FIStationTrustScore.__table__,
    FITrendSnapshot.__table__,
    FIVehicleDaily.__table__,
    FIVehicleEfficiencyScore.__table__,
    FIInsight.__table__,
    FISuggestedAction.__table__,
    FIAppliedAction.__table__,
    FIActionEffect.__table__,
)

FLEET_INTELLIGENCE_EXPLAIN_TEST_TABLES = _dedupe_tables(
    *FLEET_INTELLIGENCE_CONTROL_TEST_TABLES,
    FleetDriver.__table__,
    FleetVehicle.__table__,
    FuelCard.__table__,
    FuelNetwork.__table__,
    FuelStation.__table__,
    FuelTransaction.__table__,
    FuelFraudSignal.__table__,
    StationReputationDaily.__table__,
    FleetActionEffectStats.__table__,
    LogisticsOrder.__table__,
    LogisticsRoute.__table__,
    LogisticsStop.__table__,
    FuelRouteLink.__table__,
    LogisticsRiskSignal.__table__,
    LegalNode.__table__,
    LegalEdge.__table__,
    MoneyFlowEvent.__table__,
    MoneyFlowLink.__table__,
)


__all__ = [
    "FLEET_INTELLIGENCE_CONTROL_TEST_TABLES",
    "FLEET_INTELLIGENCE_EXPLAIN_TEST_TABLES",
]
