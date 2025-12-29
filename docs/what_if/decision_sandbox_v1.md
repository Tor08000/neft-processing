# What-If Simulator v1 (Decision Sandbox)

## Назначение

What-If Simulator v1 сравнивает 2–3 возможных действия и возвращает:

- вероятность эффекта (без исполнения действий),
- memory penalty (учёт истории решений),
- risk outlook (без вызова risk engine),
- итоговый детерминированный скор и объяснение выбора.

Данные используются исключительно для симуляции. Реальных действий, обновления лимитов,
CRM/Routes и вызовов risk v4/v5 в этом сервисе нет.

## Жёсткие ограничения

Запрещено:

- применять actions или менять CRM/limits/routes;
- вызывать risk v4/v5 decision engine;
- свободный ввод/LLM.

Разрешено:

- симуляция и сравнение вариантов;
- чтение unified explain / decision choice / decision memory;
- детерминированный вывод с основанием.

## Источники данных

Приоритет действий:

1. Fleet Control suggested actions по `insight_id` (если тип subject = `INSIGHT`).
2. Decision Choice ranked actions (top 3) по subject.
3. Fallback: фиксированный список по primary_reason.

Дополнительно используются:

- `app/services/fleet_assistant/projections.py` для probability/label,
- `app/services/decision_memory/cooldown.py` и `decay.py` для memory penalty.

## Risk outlook (soft)

Risk outlook рассчитывается без вызова risk engine:

- если действие меняет driver behaviour / station trust / route adherence → `IMPROVE`,
- если memory penalty высокий → `UNCERTAIN`,
- иначе → `NO_CHANGE`.

## Формула итогового score

```
score = (prob_improve_pct/100) * 0.6
        + outlook_bonus * 0.2
        - (memory_penalty_pct/100) * 0.2
```

`outlook_bonus`: `IMPROVE=1.0`, `NO_CHANGE=0.5`, `UNCERTAIN=0.2`.

## API (admin-only)

`POST /v1/admin/what-if/evaluate`

```
{
  "subject": { "type": "INSIGHT", "id": "..." },
  "max_candidates": 3
}
```

`subject.type` принимает: `INSIGHT`, `FUEL_TX`, `ORDER`, `INVOICE`.

## Выход

См. контракт в схемах `app/schemas/admin/what_if.py`.

Каждый кандидат содержит:

- `projection` (probability + expected effect),
- `memory` (penalty + basis),
- `risk` (outlook + notes),
- `what_if_score` и `explain`.

## Definition of Done

- симуляция сравнивает 2–3 действия и возвращает ranked list;
- показывает probability / risk outlook / memory penalty;
- не выполняет действий;
- deterministic output + тесты;
- документация описывает ограничения и источники.
