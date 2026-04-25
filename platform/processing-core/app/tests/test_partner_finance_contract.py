from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.partner_finance import (
    PartnerLedgerDirection,
    PartnerLedgerEntry,
    PartnerLedgerEntryType,
)
from app.routers.partner_finance import router as partner_finance_router
from app.security.rbac.principal import Principal, get_principal
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def test_partner_finance_ledger_returns_next_cursor_and_totals() -> None:
    partner_org_id = str(uuid4())

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "partner-finance@example.com",
                "user_id": "partner-finance-user",
                "partner_id": partner_org_id,
                "subject_type": "partner_user",
                "roles": ["PARTNER_OWNER"],
            },
        )

    now = datetime.now(timezone.utc)
    with scoped_session_context(tables=(PartnerLedgerEntry.__table__,)) as session:
        assert isinstance(session, Session)
        session.add_all(
            [
                PartnerLedgerEntry(
                    id=str(uuid4()),
                    partner_org_id=partner_org_id,
                    order_id="order-1",
                    entry_type=PartnerLedgerEntryType.EARNED,
                    amount=Decimal("1500"),
                    currency="RUB",
                    direction=PartnerLedgerDirection.CREDIT,
                    meta_json={"source_type": "order", "source_id": "order-1"},
                    created_at=now,
                ),
                PartnerLedgerEntry(
                    id=str(uuid4()),
                    partner_org_id=partner_org_id,
                    order_id="order-2",
                    entry_type=PartnerLedgerEntryType.SLA_PENALTY,
                    amount=Decimal("200"),
                    currency="RUB",
                    direction=PartnerLedgerDirection.DEBIT,
                    meta_json={"description": "Penalty"},
                    created_at=now - timedelta(minutes=1),
                ),
                PartnerLedgerEntry(
                    id=str(uuid4()),
                    partner_org_id=partner_org_id,
                    order_id="order-3",
                    entry_type=PartnerLedgerEntryType.ADJUSTMENT,
                    amount=Decimal("75"),
                    currency="RUB",
                    direction=PartnerLedgerDirection.CREDIT,
                    meta_json={"description": "Adjustment"},
                    created_at=now - timedelta(minutes=2),
                ),
            ]
        )
        session.commit()

        with router_client_context(
            router=partner_finance_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={get_principal: _override_principal},
        ) as client:
            response = client.get("/api/core/partner/ledger?limit=2")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["items"]) == 2
        assert payload["cursor"] == "2"
        assert payload["next_cursor"] == "2"
        assert payload["total"] == 3
        assert payload["totals"] == {"in": "1575.0000", "out": "200.0000", "net": "1375.0000"}
