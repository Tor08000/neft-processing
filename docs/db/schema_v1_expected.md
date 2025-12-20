# Schema v1 expected tables

Эти таблицы собирают ожидания всех сервисов репозитория (core-api/processing-core и auth-host). Источники — SQLAlchemy модели и прямые обращения к БД.

## Processing core (core-api)

| Table | Source / usage | Type |
| --- | --- | --- |
| clients | `platform/processing-core/app/models/client.py` | domain |
| cards | `platform/processing-core/app/models/card.py` | domain |
| merchants | `platform/processing-core/app/models/merchant.py` | domain |
| terminals | `platform/processing-core/app/models/terminal.py` | domain |
| operations | `platform/processing-core/app/models/operation.py` | domain |
| limits_rules | `platform/processing-core/app/models/limit_rule.py` | domain |
| client_groups | `platform/processing-core/app/models/groups.py` | ref |
| card_groups | `platform/processing-core/app/models/groups.py` | ref |
| client_group_members | `platform/processing-core/app/models/groups.py` | link |
| card_group_members | `platform/processing-core/app/models/groups.py` | link |
| billing_summary | `platform/processing-core/app/models/billing_summary.py` | domain |
| clearing | `platform/processing-core/app/models/clearing.py` | domain |
| clearing_batch | `platform/processing-core/app/models/clearing_batch.py` | domain |
| clearing_batch_operation | `platform/processing-core/app/models/clearing_batch_operation.py` | link |
| settlements | `platform/processing-core/app/models/settlement.py` | domain |
| payout_orders | `platform/processing-core/app/models/payout_order.py` | domain |
| payout_events | `platform/processing-core/app/models/payout_event.py` | audit |
| client_cards | `platform/processing-core/app/models/client_portal.py` | link |
| client_operations | `platform/processing-core/app/models/client_portal.py` | domain |
| client_limits | `platform/processing-core/app/models/client_portal.py` | domain |
| risk_rules | `platform/processing-core/app/models/risk_rule.py` | domain |
| risk_rule_versions | `platform/processing-core/app/models/risk_rule.py` | audit |
| risk_rule_audits | `platform/processing-core/app/models/risk_rule.py` | audit |
| accounts | `platform/processing-core/app/models/account.py` | domain |
| account_balances | `platform/processing-core/app/models/account.py` | domain |
| ledger_entries | `platform/processing-core/app/models/ledger_entry.py` | audit |
| tariff_plans | `platform/processing-core/app/models/contract_limits.py` | ref |
| tariff_prices | `platform/processing-core/app/models/contract_limits.py` | ref |
| limit_configs | `platform/processing-core/app/models/contract_limits.py` | domain |
| partners | `platform/processing-core/app/models/partner.py` | ref |
| external_request_logs | `platform/processing-core/app/models/external_request_log.py` | audit |
| invoices | `platform/processing-core/app/models/invoice.py` | domain |
| invoice_lines | `platform/processing-core/app/models/invoice.py` | domain |

## Auth-host

| Table | Source / usage | Type |
| --- | --- | --- |
| users | `platform/auth-host/app/db.py` (init script) | domain |
| user_roles | `platform/auth-host/app/db.py` (init script) | link |
