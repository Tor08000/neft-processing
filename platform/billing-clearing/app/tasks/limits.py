# services/workers/app/tasks/limits.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from celery import shared_task

logger = logging.getLogger(__name__)

# Базовые настройки лимитов из окружения (можно потом крутить в .env)
BASE_DAILY_LIMIT_RUB = int(os.getenv("LIMITS_BASE_DAILY_RUB", "200000"))   # базовый дневной лимит
MAX_DAILY_LIMIT_RUB = int(os.getenv("LIMITS_MAX_DAILY_RUB", "1000000"))    # жёсткий потолок
MAX_PER_TX_LIMIT_RUB = int(os.getenv("LIMITS_MAX_PER_TX_RUB", "50000"))    # максимум на одну операцию


def _clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(value, max_value))


def _calc_daily_limit(profile: Dict[str, Any]) -> int:
    """
    Простая модель расчёта дневного лимита по профилю клиента.

    profile:
      - risk_score: 0.0 .. 1.0 (0 — минимальный риск, 1 — максимальный)
      - avg_monthly_turnover: средний месячный оборот в рублях
      - has_overdue: есть ли просрочки (bool)
    """
    risk_score = float(profile.get("risk_score", 0.0))
    avg_turnover = int(profile.get("avg_monthly_turnover", BASE_DAILY_LIMIT_RUB * 10))
    has_overdue = bool(profile.get("has_overdue", False))

    # базовый лимит — 5 % от среднемесячного оборота
    base = int(avg_turnover * 0.05)
    if base < BASE_DAILY_LIMIT_RUB:
        base = BASE_DAILY_LIMIT_RUB

    # чем выше риск — тем ниже лимит
    # risk_score 0.0 => множитель 1.0
    # risk_score 1.0 => множитель 0.3
    risk_factor = 1.0 - 0.7 * _clamp(int(risk_score * 10), 0, 10) / 10.0

    limit = int(base * risk_factor)

    # за просрочку ещё режем лимит на 30 %
    if has_overdue:
        limit = int(limit * 0.7)

    return _clamp(limit, BASE_DAILY_LIMIT_RUB, MAX_DAILY_LIMIT_RUB)


@shared_task(name="limits.recalc_for_client")
def recalc_limits_for_client(
    client_id: str,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Пересчитать рекомендованные лимиты для конкретного клиента.

    Сейчас задача работает как чистый "движок расчёта":
      - На вход можно передать профиль клиента (risk_score, обороты, флаги).
      - На выходе — структура с рекомендованными лимитами.
    Хранение/запись в БД делает core-api — здесь только логика.
    """
    if profile is None:
        profile = {}

    logger.info("Limits: recalc_limits_for_client(client_id=%s, profile=%s)", client_id, profile)

    daily_limit = _calc_daily_limit(profile)
    per_tx_limit = _clamp(int(daily_limit * 0.3), 1000, MAX_PER_TX_LIMIT_RUB)  # не больше глобального per-tx

    result = {
        "client_id": client_id,
        "currency": "RUB",
        "limits": {
            "daily_limit": daily_limit,
            "per_transaction_limit": per_tx_limit,
        },
        "profile_used": profile,
    }

    logger.info("Limits: new limits for client %s -> %s", client_id, result["limits"])
    return result


@shared_task(name="limits.recalc_all")
def recalc_limits_for_all(
    clients: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Массовый пересчёт лимитов.

    Вариант 1 (простой, текущий):
      - На вход можно передать список клиентов с профилями.
      - Функция синхронно пробегается по ним и пересчитывает лимиты.

    Вариант 2 (позже):
      - core-api дергает эту задачу без аргументов,
      - внутри мы ходим в БД/внутренний API за профилями,
      - запускаем подзадачи group() по recalc_limits_for_client.
    """
    logger.info(
        "Limits: global recalculation started, clients count: %s",
        0 if clients is None else len(clients),
    )

    if not clients:
        # ничего не передали — честно говорим, что просто нечего считать
        return {
            "status": "ok",
            "processed": 0,
            "updated": 0,
            "details": [],
        }

    results: List[Dict[str, Any]] = []
    for item in clients:
        cid = str(item.get("client_id"))
        profile = item.get("profile") or {}
        # вызываем как обычную функцию, не сабтаску
        res = recalc_limits_for_client(cid, profile)
        results.append(res)

    return {
        "status": "ok",
        "processed": len(results),
        "updated": len(results),
        "details": results,
    }


@shared_task(name="limits.apply_daily_limits")
def apply_daily_limits() -> Dict[str, Any]:
    """Заглушка для применения дневных лимитов (периодическая задача)."""

    logger.info("Limits: apply_daily_limits triggered")
    summary = recalc_limits_for_all([])
    summary["task"] = "limits.apply_daily_limits"
    return summary


@shared_task(name="limits.check_and_reserve")
def check_and_reserve_limit(
    # ВАЖНО: все аргументы с default, чтобы Celery спокойно принимал kwargs
    client_id: Optional[str] = None,
    card_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    amount: int = 0,
    currency: str = "RUB",
    product_category: Optional[str] = None,
    mcc: Optional[str] = None,
    tx_type: Optional[str] = None,
    phase: str = "AUTH",
    client_group_id: Optional[str] = None,
    card_group_id: Optional[str] = None,
    used_today: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Проверка и "резерв" лимита под операцию.

    Здесь мы принимаем уже подготовленные данные:
      - client_id       — идентификатор клиента (для логов/расширения логики)
      - card_id         — карта/связка клиент–карта
      - amount          — сумма операции в рублях
      - used_today      — сколько уже потрачено сегодня по лимиту (в рублях)

    Задача возвращает только решение и "новое" значение использованного лимита.
    Фактическую запись в БД/холд делает core-api (чтобы не плодить гонки).
    """
    if card_id is None:
        # Защитное поведение: если почему-то не пришёл card_id — сразу отказ.
        logger.error(
            "Limits: check_and_reserve called without card_id (client_id=%s, amount=%s)",
            client_id,
            amount,
        )
        return {
            "client_id": client_id,
            "card_id": card_id,
            "allowed": False,
            "reason": "no_card_id",
            "used_today": used_today or 0,
            "new_used_today": used_today or 0,
        }

    logger.info(
        "Limits: check_and_reserve(client_id=%s, card_id=%s, amount=%s, currency=%s, used_today=%s)",
        client_id,
        card_id,
        amount,
        currency,
        used_today,
    )

    if amount <= 0:
        return {
            "client_id": client_id,
            "card_id": card_id,
            "allowed": False,
            "reason": "non_positive_amount",
            "used_today": used_today or 0,
            "new_used_today": used_today or 0,
        }

    if currency != "RUB":
        # На v1 не заморачиваемся курсами: считаем, что всё уже приведено к рублям.
        logger.warning(
            "Limits: non-RUB currency passed (currency=%s), assuming pre-converted to RUB",
            currency,
        )

    used = int(used_today or 0)

    # Проверка лимита на одну операцию
    if amount > MAX_PER_TX_LIMIT_RUB:
        return {
            "client_id": client_id,
            "card_id": card_id,
            "allowed": False,
            "reason": "per_tx_limit_exceeded",
            "limit_per_tx": MAX_PER_TX_LIMIT_RUB,
            "used_today": used,
            "new_used_today": used,
        }

    # Проверка дневного лимита
    if used + amount > MAX_DAILY_LIMIT_RUB:
        return {
            "client_id": client_id,
            "card_id": card_id,
            "allowed": False,
            "reason": "daily_limit_exceeded",
            "daily_limit": MAX_DAILY_LIMIT_RUB,
            "used_today": used,
            "new_used_today": used,
        }

    new_used = used + amount
    return {
        "client_id": client_id,
        "card_id": card_id,
        "allowed": True,
        "reason": "ok",
        "daily_limit": MAX_DAILY_LIMIT_RUB,
        "limit_per_tx": MAX_PER_TX_LIMIT_RUB,
        "used_today": used,
        "new_used_today": new_used,
    }

