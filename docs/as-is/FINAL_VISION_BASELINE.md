2) FINAL VISION BASELINE (эталон итогового проекта — вставить в файл как есть)

Это не “что будет”, а “что считается итоговой системой” для сравнения.

2.1 Домены (обязательные контуры)

Identity & Access (RBAC/ABAC, tenants, service identities)

Processing & Transactions lifecycle (authorize/capture/reverse/refund, idempotency)

Pricing (versions, schedules, client/partner pricing)

Rules/Limits (DSL, priorities, sandbox, audits)

Billing (invoices, payments, refunds, state machine)

Clearing/Settlement/Payouts

Reconciliation (runs, discrepancies, exports)

Documents (templates, render PDF, sign, verify, closing packages)

EDO (integration реально, не stub)

Audit / Trust layer (hash-chain, signing, retention)

Integrations hub (webhooks: intake/delivery/retry/replay, connectors)

Fleet/Fuel (cards, transactions ingestion, anomalies, policies)

Marketplace (catalog, orders, SLA, promotions, sponsored/recommendations)

Logistics (routes, tracking, deviation, ETA, explain)

CRM (clients, deals, tickets/tasks, contracts linkage)

Analytics/BI (exports, dashboards, optional ClickHouse)

Notifications (channels, outbox, delivery logs)

Frontends: Admin / Client / Partner (UX flows end-to-end)

Observability (metrics/logs/traces dashboards/targets)

2.2 Сквозные сценарии “итоговой системы”

Onboarding: клиент → роли → подписки/лимиты → карты → первые операции

Partner onboarding: партнёр/АЗС → цены → POS/терминалы → операции

Processing E2E: authorize → capture → reverse/refund + логирование + аудит

Billing cycle: период → инвойсы/акты → PDF → хранение → выдача клиенту

Settlement: расчёт → payout batches → exports

Reconciliation: импорт/сверка → discrepancies → отчёт

Documents: генерация/подпись/верификация + связи с периодом/инвойсом

Webhooks: intake → delivery → retry/replay + SLA/alerts

Fleet: ingest топлива → anomalies → policies → notifications

Marketplace: product → order → SLA evaluation → billing coupling

Logistics: trip → tracking events → deviation → explain

BI: отчёты/экспорт, витрины, (опционально ClickHouse)
