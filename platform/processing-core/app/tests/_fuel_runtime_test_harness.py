from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.billing_summary import BillingSummary
from app.domains.ledger.models import LedgerAccountBalanceV1, LedgerAccountV1, LedgerEntryV1, LedgerLineV1
from app.models.billing_period import BillingPeriod
from app.models.fleet_intelligence import (
    FIDriverScore,
    FIStationTrustScore,
    FITrendSnapshot,
    FIVehicleEfficiencyScore,
)
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.money_flow_v3 import MoneyFlowLink
from app.models.vehicle_profile import VehicleCardLink, VehicleProfile
from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationOutbox,
    FleetNotificationPolicy,
    FleetTelegramBinding,
    FuelAnalyticsEvent,
    FuelAnomalyEvent,
    FuelCard,
    FuelFraudSignal,
    FuelLimitBreach,
    FuelMisuseSignal,
    FuelStationOutlier,
    NotificationDeliveryLog,
    StationReputationDaily,
)
from app.models.operation import Operation

from ._crm_test_harness import (
    CRM_FUEL_INTEGRATION_TEST_TABLES,
    CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES,
    crm_session_context,
)
from ._logistics_route_harness import LOGISTICS_FUEL_TEST_TABLES


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


FUEL_AUTHORIZE_TEST_TABLES = _dedupe_tables(
    *CRM_FUEL_INTEGRATION_TEST_TABLES,
    *CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES,
    *LOGISTICS_FUEL_TEST_TABLES,
    AuditLog.__table__,
    FuelAnomalyEvent.__table__,
    FuelAnalyticsEvent.__table__,
    FuelFraudSignal.__table__,
    FuelMisuseSignal.__table__,
    FuelStationOutlier.__table__,
    StationReputationDaily.__table__,
    FIDriverScore.__table__,
    FIStationTrustScore.__table__,
    FIVehicleEfficiencyScore.__table__,
    FITrendSnapshot.__table__,
    VehicleProfile.__table__,
    VehicleCardLink.__table__,
)

FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES = _dedupe_tables(
    FuelCard.__table__,
    FuelLimitBreach.__table__,
    FleetTelegramBinding.__table__,
    FleetNotificationChannel.__table__,
    FleetNotificationPolicy.__table__,
    FleetNotificationOutbox.__table__,
    NotificationDeliveryLog.__table__,
)

FUEL_BILLING_FEED_TEST_TABLES = _dedupe_tables(
    *FUEL_AUTHORIZE_TEST_TABLES,
    LedgerAccountV1.__table__,
    LedgerEntryV1.__table__,
    LedgerLineV1.__table__,
    LedgerAccountBalanceV1.__table__,
    BillingSummary.__table__,
    Operation.__table__,
)

FUEL_SETTLEMENT_LEDGER_TEST_TABLES = _dedupe_tables(
    *FUEL_BILLING_FEED_TEST_TABLES,
    BillingPeriod.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    MoneyFlowLink.__table__,
)

FUEL_FRAUD_SIGNAL_TEST_TABLES = FUEL_AUTHORIZE_TEST_TABLES


@contextmanager
def fuel_runtime_session_context(*, tables=FUEL_AUTHORIZE_TEST_TABLES) -> Iterator[Session]:
    with crm_session_context(tables=tables) as session:
        yield session


__all__ = [
    "FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES",
    "FUEL_BILLING_FEED_TEST_TABLES",
    "FUEL_FRAUD_SIGNAL_TEST_TABLES",
    "FUEL_AUTHORIZE_TEST_TABLES",
    "FUEL_SETTLEMENT_LEDGER_TEST_TABLES",
    "fuel_runtime_session_context",
]
