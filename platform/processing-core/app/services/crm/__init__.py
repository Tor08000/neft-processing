"""CRM Core v1 services."""

from app.services.crm import (  # noqa: F401
    clients,
    contracts,
    decision_context,
    events,
    repository,
    settings,
    subscription_billing,
    subscription_pricing_engine,
    subscription_usage_collector,
    subscriptions,
    sync,
    tariffs,
)

__all__ = [
    "clients",
    "contracts",
    "decision_context",
    "events",
    "repository",
    "settings",
    "subscription_billing",
    "subscription_pricing_engine",
    "subscription_usage_collector",
    "subscriptions",
    "sync",
    "tariffs",
]
