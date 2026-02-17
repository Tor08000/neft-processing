"""Centralized model import registry for deterministic ORM mapper initialization."""

from __future__ import annotations


def import_all_models() -> None:
    """Import ORM modules once to register all mapped classes in Base.metadata."""

    # Core entities
    from app.models import (  # noqa: F401
        account,
        card,
        groups,
        ledger_entry,
        limit_rule,
        merchant,
        operation,
        partner,
        posting_batch,
        risk_decision,
        risk_policy,
        risk_rule,
        risk_threshold,
        risk_threshold_set,
        risk_training_snapshot,
        terminal,
    )

    # Notifications and client portal models
    from app.models import (  # noqa: F401
        client_user_roles,
        client_users,
        notifications,
        notification_outbox,
    )

    # Domain models
    from app.domains.client.docflow import models as client_docflow_models  # noqa: F401
    from app.domains.client.generated_docs import models as generated_docs_models  # noqa: F401
    from app.domains.client.onboarding import models as onboarding_models  # noqa: F401
    from app.domains.client.onboarding.documents import models as onboarding_documents_models  # noqa: F401


__all__ = ["import_all_models"]
