from __future__ import annotations

from dataclasses import dataclass

from app.models.unified_explain import PrimaryReason


@dataclass(frozen=True)
class InsightScenario:
    primary_reason: PrimaryReason
    insight: str
    why_problem: str
    if_ignore: str
    first_action: str
    trend: str


SCENARIOS: dict[PrimaryReason, InsightScenario] = {
    PrimaryReason.LOGISTICS: InsightScenario(
        primary_reason=PrimaryReason.LOGISTICS,
        insight="Сбой в логистике увеличивает риск задержек и отмен.",
        why_problem="Система видит отклонения в маршруте или перегрузку, что влияет на SLA доставки.",
        if_ignore="Вероятность просрочек растёт, а эскалация уйдёт в OPS.",
        first_action="Проверьте проблемные станции и исключите их из маршрута.",
        trend="Если логистика связана с активным рейсом, тенденция обычно ухудшается до вмешательства.",
    ),
    PrimaryReason.RISK: InsightScenario(
        primary_reason=PrimaryReason.RISK,
        insight="Риск-оценка сигнализирует о потенциальном нарушении комплаенса.",
        why_problem="Факторы риска выше нормы, поэтому транзакции ограничены до проверки.",
        if_ignore="Блокировки сохранятся, и инцидент эскалируется в Compliance.",
        first_action="Начните с ручной проверки клиента и подтверждения допустимости операции.",
        trend="Без проверки риск остаётся нестабильным и может ухудшиться.",
    ),
    PrimaryReason.LIMIT: InsightScenario(
        primary_reason=PrimaryReason.LIMIT,
        insight="Лимиты клиента достигнуты и блокируют операции.",
        why_problem="Порог по лимитам исчерпан, поэтому система отклоняет новые операции.",
        if_ignore="Операции будут продолжать отклоняться, эскалация уйдёт в CRM.",
        first_action="Уточните, требуется ли увеличение лимита или смена профиля.",
        trend="Состояние стабильно до изменения лимита.",
    ),
    PrimaryReason.MONEY: InsightScenario(
        primary_reason=PrimaryReason.MONEY,
        insight="Денежный поток в расхождении с ожиданиями биллинга.",
        why_problem="Обнаружены несоответствия оплат и начислений, поэтому операции блокируются.",
        if_ignore="Сумма долга растёт, эскалация уйдёт в Finance.",
        first_action="Сверьте начисления и оплату, запросите корректировку при необходимости.",
        trend="При активных начислениях расхождение ухудшается.",
    ),
    PrimaryReason.POLICY: InsightScenario(
        primary_reason=PrimaryReason.POLICY,
        insight="Операция не соответствует политике клиента.",
        why_problem="Сработало правило политики, блокирующее действие.",
        if_ignore="Блокировка сохранится, пока политика не будет обновлена.",
        first_action="Проверьте правила политики и согласуйте исключение при необходимости.",
        trend="Состояние стабильно до изменения правил.",
    ),
    PrimaryReason.UNKNOWN: InsightScenario(
        primary_reason=PrimaryReason.UNKNOWN,
        insight="Недостаточно данных для точной классификации причины.",
        why_problem="Снимок не содержит деталей для уверенного объяснения.",
        if_ignore="Риск сохраняется, но без явной эскалации.",
        first_action="Соберите дополнительные данные или обновите snapshot.",
        trend="Тренд неизвестен без новых данных.",
    ),
}

__all__ = ["InsightScenario", "SCENARIOS"]
