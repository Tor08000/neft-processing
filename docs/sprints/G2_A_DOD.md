# Sprint G2-A — Definition of Done (DoD)

Sprint G2-A считается DONE, если выполнены ВСЕ условия:

## Runtime
- 14 календарных дней.
- 0 ручных правок БД.
- 0 payout rollback.
- 0 partner disputes без self-resolution.

## Money invariants
- No payout before finalized snapshot.
- No unlock without PAID.
- No recalculation after finalize.

## Ops
- Любой инцидент закрывается ≤ 30 минут.
- Все действия через UI/API.
- Все override → audit.
