# ADR-0002: Contract testing (Schemathesis + event schemas)

## Status
Accepted

## Context
UPAS требует contract testing как часть контроля изменений. Проект содержит сложные контуры и интеграции между доменами (Fuel / Risk / Explain / Money Flow / CRM / Logistics / Ops / Billing), которые нельзя ломать при сервис-экстракции.

## Decision
1. Использовать **Schemathesis** для provider verification по OpenAPI (HTTP).
2. Вести реестр контрактов событий в `docs/contracts/events/` (JSON Schema).
3. Контрактные тесты должны быть merge-gate в CI (`pytest -m contracts`).

## Consequences
- Любое breaking изменение требует версии (`/v2`, `schema_version`, `X-CRM-Version`).
- Контракты API и событий проверяются детерминированными тестами без внешних сервисов.
- CI блокирует merge при нарушении контрактов.

## References
- docs/ops/contract_testing.md
- docs/contracts/events/README.md
