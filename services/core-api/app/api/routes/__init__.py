# services/core-api/app/api/routes/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import auth, clients, health, prices, rules, transactions, limits, admin
from . import merchants, terminals, cards, transactions_log

# Чтобы не ломать существующий main.py, объявляем оба имени.
router = APIRouter()
api_router = router  # если где-то импортируется api_router — тоже будет работать

# Общий префикс /api/v1 задаётся в app.main
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(clients.router)
router.include_router(prices.router)
router.include_router(rules.router)
router.include_router(transactions.router)
router.include_router(transactions_log.router)
router.include_router(limits.router)
router.include_router(merchants.router)
router.include_router(terminals.router)
router.include_router(cards.router)
router.include_router(admin.router)
