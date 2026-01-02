from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.security.rbac.ownership import (
    require_client_owns_contract,
    require_client_owns_invoice,
    require_partner_owns_settlement,
)
from app.security.rbac.principal import Principal


@dataclass
class DummyInvoice:
    client_id: str


@dataclass
class DummyContract:
    party_a_id: UUID
    party_b_id: UUID


@dataclass
class DummySettlement:
    partner_id: UUID


def _principal(*, client_id: UUID | None = None, partner_id: UUID | None = None, is_admin: bool = False) -> Principal:
    return Principal(
        user_id=uuid4(),
        roles={"admin"} if is_admin else set(),
        scopes=set(),
        client_id=client_id,
        partner_id=partner_id,
        is_admin=is_admin,
        raw_claims={},
    )


def test_client_invoice_ownership_enforced() -> None:
    client_id = uuid4()
    other_client_id = uuid4()
    invoice = DummyInvoice(client_id=str(client_id))

    require_client_owns_invoice(_principal(client_id=client_id), invoice)

    with pytest.raises(HTTPException) as exc:
        require_client_owns_invoice(_principal(client_id=other_client_id), invoice)
    assert exc.value.status_code == 403


def test_client_contract_ownership_enforced() -> None:
    client_id = uuid4()
    other_client_id = uuid4()
    contract = DummyContract(party_a_id=client_id, party_b_id=uuid4())

    require_client_owns_contract(_principal(client_id=client_id), contract)

    with pytest.raises(HTTPException) as exc:
        require_client_owns_contract(_principal(client_id=other_client_id), contract)
    assert exc.value.status_code == 403


def test_partner_settlement_ownership_enforced() -> None:
    partner_id = uuid4()
    other_partner_id = uuid4()
    settlement = DummySettlement(partner_id=partner_id)

    require_partner_owns_settlement(_principal(partner_id=partner_id), settlement)

    with pytest.raises(HTTPException) as exc:
        require_partner_owns_settlement(_principal(partner_id=other_partner_id), settlement)
    assert exc.value.status_code == 403


def test_admin_bypasses_ownership() -> None:
    settlement = DummySettlement(partner_id=uuid4())

    require_partner_owns_settlement(_principal(is_admin=True), settlement)
