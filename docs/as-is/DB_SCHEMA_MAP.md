# NEFT Platform — DB Schema Map (AS-IS)

> **Source of truth:** SQLAlchemy models and Alembic migrations in `platform/processing-core/app/models`, `platform/processing-core/app/alembic/versions`, `platform/auth-host/app/alembic/versions`, `platform/integration-hub/neft_integration_hub/models`.

## 1) Database schemas in use

| Schema | Used by | How configured | Notes |
|---|---|---|---|
| `processing_core` | Core API (`core-api`) | `NEFT_DB_SCHEMA` env (default `processing_core`) | Main schema for domain data. (`platform/processing-core/app/db/schema.py`, `docker-compose.yml`) |
| `public` (default) | auth-host | `AUTH_DB_SCHEMA` env (default `public`) | Auth tables live in configured schema. (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`) |
| integration-hub (SQLite by default) | integration-hub | `INTEGRATION_HUB_DATABASE_URL` env (fallback `DATABASE_URL` or SQLite) | Not schema-based if SQLite; uses SQLAlchemy Base metadata. (`platform/integration-hub/neft_integration_hub/settings.py`, `platform/integration-hub/neft_integration_hub/db.py`) |

## 2) Alembic state (AS-IS)

### processing-core
- **Head (merge revision):** `20299000_0130_merge_heads_processing_core`. (`platform/processing-core/app/alembic/versions/20299000_0130_merge_heads_processing_core.py`)
- **Merged heads:** `b1f4572ed8d3` and `76e4bcb5869e` (merged by the head revision above). (`platform/processing-core/app/alembic/versions/20299000_0130_merge_heads_processing_core.py`)
- **Current (DB runtime):** **NOT VERIFIED** — runtime snapshot shows `verify_all` was not executed. (`docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`)

### auth-host
- **Head:** `20251002_0001_create_auth_tables`. (`platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py`)
- **Bootstrap migration:** `20251001_0001_auth_bootstrap` sets up roles and initial admin. (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`)
- **Current (DB runtime):** **NOT VERIFIED** — runtime snapshot shows `verify_all` was not executed. (`docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`)

### integration-hub
- No Alembic migrations are present. Schema is created via SQLAlchemy models on startup. (`platform/integration-hub/neft_integration_hub/db.py`)

## 2.1) Enforced invariants (examples)

> Примеры реально заданных ограничений (unique/index) в моделях и миграциях.

- `invoice`/`billing` уникальные ключи по scope (invoice number, period, tenant). (`platform/processing-core/app/models/invoice.py`)
- `internal_ledger_accounts` уникальные ключи по account scope. (`platform/processing-core/app/models/internal_ledger.py`)
- Legal graph: уникальность узлов и рёбер по tenant + scope. (`platform/processing-core/app/models/legal_graph.py`)
- `case_events` уникальное упорядочивание `case_id + seq`. (`platform/processing-core/app/models/cases.py`)
- `audit_log` индексированные поля для неизменяемого аудита. (`platform/processing-core/app/models/audit_log.py`)

## 3) processing_core — key tables by domain

> **Note:** This list focuses on tables that define domain boundaries. For a full list, see `platform/processing-core/app/models/`.

### Audit & immutability
- `audit_log` (hash-chain audit log). (`platform/processing-core/app/models/audit_log.py`)
- `audit_signing_keys` (public key registry). (`platform/processing-core/app/models/audit_signing_keys.py`)
- `audit_legal_holds`, `audit_purge_log` (retention). (`platform/processing-core/app/models/audit_retention.py`)
- `external_request_logs` (external call audit). (`platform/processing-core/app/models/external_request_log.py`)

**Key indexes/constraints**
- `audit_log` indexes: `ix_audit_log_ts_desc`, `ix_audit_log_entity`, `ix_audit_log_event_ts`, `ix_audit_log_tenant_ts`, `ix_audit_log_external_refs_gin`. (`platform/processing-core/app/models/audit_log.py`)

### Cases & decision memory
- `cases`, `case_events`, `case_comments`, `case_snapshots`. (`platform/processing-core/app/models/cases.py`)
- `decision_memory`, `decision_outcomes`, `decision_action_stats_daily`, `decision_results`. (`platform/processing-core/app/models/decision_memory.py`, `platform/processing-core/app/models/decision_result.py`)
- Risk tables: `risk_decisions`, `risk_scores`, `risk_rules`, `risk_rule_versions`, `risk_rule_audits`, `risk_policies`, `risk_thresholds`, `risk_threshold_sets`, `risk_v5_*`. (`platform/processing-core/app/models/risk_*.py`)

**Key indexes/constraints**
- `case_events` unique constraint `ux_case_events_case_seq` for sequencing. (`platform/processing-core/app/models/cases.py`)

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

## 6) Key enum types (purpose + usage)

> **Not exhaustive.** Only enums that define module behavior.

| Enum | Purpose | File |
|---|---|---|
| `CaseEventType` | Case lifecycle + domain events | `platform/processing-core/app/models/cases.py` |
| `CaseStatus` / `CasePriority` / `CaseQueue` | Case workflow | `platform/processing-core/app/models/cases.py` |
| `audit_actor_type` | Audit actor typing | `platform/processing-core/app/alembic/versions/0042_audit_log.py` |
| `MoneyFlowEventType` | Money flow state transitions | `platform/processing-core/app/services/money_flow/events.py` |
| `MarketplaceOrderEventType` | Marketplace order transitions | `platform/processing-core/app/models/marketplace_orders.py` |
| `ServiceBookingEventType` | Booking transitions | `platform/processing-core/app/models/service_bookings.py` |
| `ServiceProofEventType` | Proof lifecycle | `platform/processing-core/app/models/service_completion_proofs.py` |
| `FleetNotificationEventType` | Fleet notification routing | `platform/processing-core/app/models/fuel.py` |
| `LogisticsTrackingEventType` / `LogisticsDeviationEventType` | Logistics telemetry | `platform/processing-core/app/models/logistics.py` |
| `WebhookOwnerType` / `WebhookDeliveryStatus` | Integration Hub webhook status | `platform/integration-hub/neft_integration_hub/models/webhooks.py` |
| `EdoStubStatus` | EDO stub state | `platform/integration-hub/neft_integration_hub/models/edo_stub.py` |
