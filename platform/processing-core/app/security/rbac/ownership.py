from __future__ import annotations

from fastapi import HTTPException

from .principal import Principal


def _ownership_detail(reason: str, *, resource: str) -> dict:
    return {
        "error": "forbidden",
        "reason": reason,
        "resource": resource,
    }


def _compare_ids(left: object | None, right: object | None) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def require_client_owns_invoice(principal: Principal, invoice: object) -> None:
    if principal.is_admin:
        return
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail=_ownership_detail("missing_ownership_context", resource="invoice"),
        )
    if not _compare_ids(principal.client_id, getattr(invoice, "client_id", None)):
        raise HTTPException(status_code=403, detail=_ownership_detail("not_owner", resource="invoice"))


def require_client_owns_contract(principal: Principal, contract: object) -> None:
    if principal.is_admin:
        return
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail=_ownership_detail("missing_ownership_context", resource="contract"),
        )
    party_a = getattr(contract, "party_a_id", None)
    party_b = getattr(contract, "party_b_id", None)
    if not (_compare_ids(principal.client_id, party_a) or _compare_ids(principal.client_id, party_b)):
        raise HTTPException(status_code=403, detail=_ownership_detail("not_owner", resource="contract"))


def require_partner_owns_settlement(principal: Principal, settlement: object) -> None:
    if principal.is_admin:
        return
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail=_ownership_detail("missing_ownership_context", resource="settlement"),
        )
    if not _compare_ids(principal.partner_id, getattr(settlement, "partner_id", None)):
        raise HTTPException(status_code=403, detail=_ownership_detail("not_owner", resource="settlement"))


__all__ = [
    "require_client_owns_contract",
    "require_client_owns_invoice",
    "require_partner_owns_settlement",
]
