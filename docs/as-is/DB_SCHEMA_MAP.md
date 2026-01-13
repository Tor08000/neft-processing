# NEFT Platform — DB Schema Map (AS-IS)

> **Source of truth:** SQLAlchemy models and Alembic migrations in repo.

## 1) Schemas in use

| Schema | Used by | How configured | Notes |
|---|---|---|---|
| `processing_core` | core-api | `NEFT_DB_SCHEMA` (default `processing_core`) | Основная доменная схема. (`platform/processing-core/app/db/schema.py`) |
| `public` (default) / `AUTH_DB_SCHEMA` | auth-host | `AUTH_DB_SCHEMA` (default `public`) | Auth tables живут в указанной схеме. (`platform/auth-host/app/db.py`, `platform/auth-host/app/alembic/env.py`) |
| integration-hub DB | integration-hub | `INTEGRATION_HUB_DATABASE_URL` (fallback `DATABASE_URL` или SQLite `integration-hub.db`) | Schema не применяется при SQLite. (`platform/integration-hub/neft_integration_hub/settings.py`) |

## 2) Alembic state (AS-IS)

### processing-core
- **Head (merge revision):** `20299000_0130_merge_heads_processing_core`. (`platform/processing-core/app/alembic/versions/20299000_0130_merge_heads_processing_core.py`)
- **Merged heads:** `b1f4572ed8d3`, `76e4bcb5869e`. (см. merge revision выше)
- **Runtime current:** **NOT VERIFIED** — runtime verify не выполнялся. (`docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`)

### auth-host
- **Head:** `20251002_0001_create_auth_tables`. (`platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py`)
- **Bootstrap:** `20251001_0001_auth_bootstrap`. (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`)
- **Runtime current:** **NOT VERIFIED** — runtime verify не выполнялся. (`docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`)

### integration-hub
- Alembic отсутствует; schema создаётся моделями SQLAlchemy на старте. (`platform/integration-hub/neft_integration_hub/db.py`)

---

## 3) processing_core — ключевые таблицы по доменам

> **Не полный список.** Фокус на таблицах, которые задают границы доменов.

### Audit & immutability
- `audit_log`, `audit_signing_keys`, `audit_legal_holds`, `audit_purge_log`, `external_request_logs`. (`platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/models/audit_signing_keys.py`, `platform/processing-core/app/models/audit_retention.py`, `platform/processing-core/app/models/external_request_log.py`)

### Cases & decision memory
- `cases`, `case_events`, `case_comments`, `case_snapshots`. (`platform/processing-core/app/models/cases.py`)
- `decision_memory`, `decision_outcomes`, `decision_action_stats_daily`, `decision_results`. (`platform/processing-core/app/models/decision_memory.py`, `platform/processing-core/app/models/decision_result.py`)
- `risk_*` (rules/decisions/thresholds). (`platform/processing-core/app/models/risk_*.py`)

### Billing & finance
- Billing flows: `billing_invoices`, `billing_payments`, `billing_refunds`, `billing_job_runs`, `billing_periods`, `billing_summary`. (`platform/processing-core/app/models/billing_flow.py`, `platform/processing-core/app/models/billing_job_run.py`, `platform/processing-core/app/models/billing_period.py`)
- Invoices & adjustments: `invoices`, `invoice_lines`, `invoice_transition_logs`, `refund_requests`, `financial_adjustments`, `credit_notes`. (`platform/processing-core/app/models/invoice.py`, `platform/processing-core/app/models/refund_request.py`, `platform/processing-core/app/models/financial_adjustment.py`, `platform/processing-core/app/models/finance.py`)
- Ledger: `accounts`, `account_balances`, `ledger_entries`, `internal_ledger_accounts`, `internal_ledger_transactions`, `internal_ledger_entries`, `posting_batches`. (`platform/processing-core/app/models/account.py`, `platform/processing-core/app/models/ledger_entry.py`, `platform/processing-core/app/models/internal_ledger.py`, `platform/processing-core/app/models/posting_batch.py`)
- Clearing & settlement: `clearing`, `clearing_batch`, `clearing_batch_operation`, `settlements`, `settlement_accounts`, `settlement_periods`, `settlement_items`, `payouts`. (`platform/processing-core/app/models/clearing.py`, `platform/processing-core/app/models/settlement.py`, `platform/processing-core/app/models/settlement_v1.py`)
- Payouts: `payout_orders`, `payout_events`, `payout_batches`, `payout_items`, `payout_export_files`. (`platform/processing-core/app/models/payout_order.py`, `platform/processing-core/app/models/payout_event.py`, `platform/processing-core/app/models/payout_batch.py`, `platform/processing-core/app/models/payout_export_file.py`)
- Reconciliation: `reconciliation_runs`, `reconciliation_discrepancies`, `external_statements`, `reconciliation_links`, `billing_reconciliation_runs`, `billing_reconciliation_items`. (`platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/models/billing_reconciliation.py`)
- Money flow: `money_flow_events`, `money_flow_links`, `money_invariant_snapshots`. (`platform/processing-core/app/models/money_flow.py`, `platform/processing-core/app/models/money_flow_v3.py`)

### Fleet & fuel
- Cards & groups: `fuel_cards`, `fuel_card_groups`, `fuel_card_status_events`, `cards`, `client_groups`, `card_groups`, `client_group_members`, `card_group_members`. (`platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/models/card.py`, `platform/processing-core/app/models/groups.py`)
- Fleet directory: `fleet_vehicles`, `fleet_drivers`, `client_employees`, `fuel_group_access`, `fuel_card_group_members`. (`platform/processing-core/app/models/fleet.py`)
- Transactions & ingestion: `fuel_transactions`, `fuel_ingest_jobs`, `fuel_limit_breaches`, `fuel_anomalies`, `fuel_anomaly_events`, `fuel_risk_shadow_events`, `fuel_analytics_events`. (`platform/processing-core/app/models/fuel.py`)
- Notifications & policy: `fleet_notification_channels`, `fleet_notification_policies`, `fleet_action_policies`, `fleet_policy_executions`, `fleet_notification_outbox`, `notification_delivery_logs`, `fleet_push_subscriptions`. (`platform/processing-core/app/models/fuel.py`)

### Marketplace & partner services
- Catalog & partner profiles: `partner_profiles`, `marketplace_products`. (`platform/processing-core/app/models/marketplace_catalog.py`)
- Orders & events: `marketplace_orders`, `marketplace_order_events`. (`platform/processing-core/app/models/marketplace_orders.py`)
- SLA & contracts: `marketplace_order_contract_links`, `order_sla_evaluations`, `order_sla_consequences`, `marketplace_sla_notification_outbox`, `contracts`, `contract_versions`, `contract_obligations`, `contract_events`, `sla_results`. (`platform/processing-core/app/models/marketplace_order_sla.py`, `platform/processing-core/app/models/marketplace_contracts.py`)
- Promotions & coupons: `promotions`, `marketplace_promotions`, `coupons`, `marketplace_coupons`, `promotion_applications`, `marketplace_promotion_applications`, `promo_budgets`. (`platform/processing-core/app/models/marketplace_promotions.py`)
- Sponsored & recommendations: `sponsored_campaigns`, `sponsored_events`, `sponsored_spend_ledger`, `marketplace_events`, `product_taxonomy`, `offer_candidates`. (`platform/processing-core/app/models/marketplace_sponsored.py`, `platform/processing-core/app/models/marketplace_recommendations.py`)
- Services/booking: `partner_services`, `partner_service_calendars`, `partner_resources`, `service_availability_rules`, `booking_slot_locks`, `service_bookings`, `service_booking_events`. (`platform/processing-core/app/models/service_bookings.py`)
- Service proofs: `service_completion_proofs`, `service_proof_attachments`, `service_proof_confirmations`, `service_proof_events`. (`platform/processing-core/app/models/service_completion_proofs.py`)

### Documents & exports
- `documents`, `document_files`, `closing_packages`, `document_edo_status`. (`platform/processing-core/app/models/documents.py`)
- Exports: `accounting_export_batches`, `erp_export_profiles`, `erp_mappings`, `erp_mapping_rules`, `erp_reconciliation_runs`, `erp_reconciliation_items`, `case_exports`. (`platform/processing-core/app/models/accounting_export_batch.py`, `platform/processing-core/app/models/erp_exports.py`, `platform/processing-core/app/models/case_exports.py`)

### Logistics
- `logistics_orders`, `logistics_routes`, `logistics_stops`, `logistics_tracking_events`, `logistics_deviation_events`. (`platform/processing-core/app/models/logistics.py`)

### CRM / support / ops
- `crm_clients`, `crm_contracts`, `crm_tariff_plans`, `crm_subscriptions`, `crm_feature_flags`. (`platform/processing-core/app/models/crm.py`)
- `support_requests`. (`platform/processing-core/app/models/support_request.py`)
- `ops_escalations`. (`platform/processing-core/app/models/ops.py`)

---

## 4) integration-hub — tables

| Table | Purpose | File |
|---|---|---|
| `webhook_endpoints` | Registered webhook endpoints | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `webhook_subscriptions` | Event subscriptions per endpoint | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `webhook_deliveries` | Delivery attempts & status | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `webhook_replays` | Replay requests | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `webhook_alerts` | SLA/alert state | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `webhook_intake_events` | Intake log | `platform/integration-hub/neft_integration_hub/models/webhook_intake.py` |
| `edo_documents` | EDO document tracking | `platform/integration-hub/neft_integration_hub/models/edo.py` |
| `edo_stub_messages` | EDO stub simulation | `platform/integration-hub/neft_integration_hub/models/edo_stub.py` |

## 5) auth-host — tables

| Table | Purpose | File |
|---|---|---|
| `users` | Auth users | `platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py` |
| `user_roles` | User roles map | `platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py` |

---

## 6) Key enum types (examples)

> **Not exhaustive.** Only enums that define module behavior.

| Enum | Purpose | File |
|---|---|---|
| `CaseEventType` / `CaseStatus` / `CasePriority` / `CaseQueue` | Case workflow | `platform/processing-core/app/models/cases.py` |
| `audit_actor_type` | Audit actor typing | `platform/processing-core/app/alembic/versions/0042_audit_log.py` |
| `MoneyFlowEventType` | Money flow state transitions | `platform/processing-core/app/services/money_flow/events.py` |
| `MarketplaceOrderEventType` | Marketplace order transitions | `platform/processing-core/app/models/marketplace_orders.py` |
| `ServiceBookingEventType` | Booking transitions | `platform/processing-core/app/models/service_bookings.py` |
| `ServiceProofEventType` | Proof lifecycle | `platform/processing-core/app/models/service_completion_proofs.py` |
| `FleetNotificationEventType` | Fleet notification routing | `platform/processing-core/app/models/fuel.py` |
| `LogisticsTrackingEventType` / `LogisticsDeviationEventType` | Logistics telemetry | `platform/processing-core/app/models/logistics.py` |
| `WebhookOwnerType` / `WebhookDeliveryStatus` | Integration Hub webhook status | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `EdoStubStatus` | EDO stub state | `platform/integration-hub/neft_integration_hub/models/edo_stub.py` |
