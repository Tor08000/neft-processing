# Client Settings & Feature Flags

CRM Core v1 управляет доступом клиента к доменам платформы через feature flags:

- `FUEL_ENABLED`
- `LOGISTICS_ENABLED`
- `DOCUMENTS_ENABLED`
- `RISK_BLOCKING_ENABLED`
- `ACCOUNTING_EXPORT_ENABLED`

## Применение

- При активации контракта флаги включаются (по тарифу или по умолчанию).
- При паузе/терминации контракта флаги отключаются.
- Флаги можно переключать вручную через admin API.

## Влияние на домены

- **Fuel**: отключение `FUEL_ENABLED` блокирует авторизацию операций.
- **Risk**: отключение `RISK_BLOCKING_ENABLED` сохраняет риск-решения, но убирает enforcement.
