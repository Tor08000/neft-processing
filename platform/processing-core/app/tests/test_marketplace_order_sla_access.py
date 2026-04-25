from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.marketplace_order_sla import MarketplaceOrderContractLink
from app.models.marketplace_orders import MarketplaceOrder
from app.routers.portal import _assert_marketplace_order_access


class _Query:
    def __init__(self, result: object | None) -> None:
        self._result = result

    def filter(self, *_args: object, **_kwargs: object) -> "_Query":
        return self

    def one_or_none(self) -> object | None:
        return self._result


class _Db:
    def __init__(self, *, order: MarketplaceOrder | None = None) -> None:
        self._order = order

    def query(self, model: object) -> _Query:
        if model is MarketplaceOrderContractLink:
            return _Query(None)
        if model is MarketplaceOrder:
            return _Query(self._order)
        return _Query(None)


def test_marketplace_order_sla_access_accepts_order_without_contract_link() -> None:
    order_id = uuid4()
    client_id = uuid4()
    partner_id = uuid4()
    order = MarketplaceOrder(id=order_id, client_id=client_id, partner_id=partner_id, price_snapshot={})

    result = _assert_marketplace_order_access(_Db(order=order), order_id=str(order_id), client_id=str(client_id))

    assert result is order


def test_marketplace_order_sla_access_rejects_wrong_client_without_contract_link() -> None:
    order = MarketplaceOrder(id=uuid4(), client_id=uuid4(), partner_id=uuid4(), price_snapshot={})

    with pytest.raises(HTTPException) as exc:
        _assert_marketplace_order_access(_Db(order=order), order_id=str(order.id), client_id=str(uuid4()))

    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden"
