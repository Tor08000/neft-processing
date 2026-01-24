# Client domain map (as-is)

This map aligns canonical client-portal domain entities with current code and database artifacts. Paths are relative to repo root.

## User
- **Model:** auth-host user model in `platform/auth-host/app/models/user.py`.【F:platform/auth-host/app/models/user.py†L1-L26】
- **DB table:** `auth.users` (auth-host schema).
- **Migrations:** `platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py` and `20251002_0001_create_auth_tables.py` create `users`.【F:platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py†L1-L69】【F:platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py†L1-L99】
- **Routes:** auth login/token endpoints (auth-host service, see auth-host API docs).

## Organization (Client org)
- **Model:** `platform/processing-core/app/models/client.py` (`clients` table) and CRM org mirror `platform/processing-core/app/models/crm.py` (`crm_clients`).【F:platform/processing-core/app/models/client.py†L1-L33】【F:platform/processing-core/app/models/crm.py†L178-L214】
- **DB tables:** `clients`, `crm_clients`.
- **Migrations:** `platform/processing-core/app/alembic/versions/20251208_0004a_bootstrap_clients_cards_partners.py` (clients) and `20291401_0065_crm_core_v1.py` (crm_clients).【F:platform/processing-core/app/alembic/versions/20251208_0004a_bootstrap_clients_cards_partners.py†L1-L110】【F:platform/processing-core/app/alembic/versions/20291401_0065_crm_core_v1.py†L1-L88】
- **Routes:** `platform/processing-core/app/routers/client_onboarding.py` (create onboarding org) and `client_me.py` / `portal_me.py` (bootstrap read).【F:platform/processing-core/app/routers/client_onboarding.py†L1-L120】【F:platform/processing-core/app/routers/portal_me.py†L1-L22】

## Membership (org ↔ user)
- **Model:** `ClientEmployee` and `ClientUserRole` in `platform/processing-core/app/models/fleet.py` and `platform/processing-core/app/models/client_portal.py`.【F:platform/processing-core/app/models/fleet.py†L74-L121】【F:platform/processing-core/app/models/client_portal.py†L92-L108】
- **DB tables:** `client_employees`, `client_user_roles`.
- **Migrations:** `platform/processing-core/app/alembic/versions/20250220_0103_fuel_fleet_v1.py` (client_employees) and `client_user_roles` (no explicit migration found in alembic/versions; verify).【F:platform/processing-core/app/alembic/versions/20250220_0103_fuel_fleet_v1.py†L1-L176】
- **Routes:** user/employee endpoints in `platform/processing-core/app/routers/client_fleet.py` and `client_portal_v1.py` (`/employees`, `/users`).【F:platform/processing-core/app/routers/client_fleet.py†L1370-L1436】【F:platform/processing-core/app/routers/client_portal_v1.py†L5465-L5599】

## Subscription
- **Model:** `ClientSubscription`, `SubscriptionPlan`, `SubscriptionPlanModule` in `platform/processing-core/app/models/subscriptions_v1.py`.【F:platform/processing-core/app/models/subscriptions_v1.py†L40-L170】
- **DB tables:** `client_subscriptions`, `subscription_plans`, `subscription_plan_modules`.
- **Migrations:** `platform/processing-core/app/alembic/versions/20291740_0091_subscription_system_v1.py` (creates subscription tables).【F:platform/processing-core/app/alembic/versions/20291740_0091_subscription_system_v1.py†L1-L189】
- **Routes:** subscription selection/assignment in onboarding (`client_onboarding.py`) and entitlements snapshot recompute in admin commercial endpoints (`admin/commercial.py`).【F:platform/processing-core/app/routers/client_onboarding.py†L1-L120】【F:platform/processing-core/app/routers/admin/commercial.py†L690-L750】

## EntitlementsSnapshot
- **Model/service:** computed by `get_org_entitlements_snapshot` in `platform/processing-core/app/services/entitlements_v2_service.py`, which reads/writes `org_entitlements_snapshot`.【F:platform/processing-core/app/services/entitlements_v2_service.py†L276-L366】
- **DB table:** `org_entitlements_snapshot`.
- **Migrations:** no explicit alembic migration found for `org_entitlements_snapshot` in `platform/processing-core/app/alembic/versions` (verify/restore if missing).
- **Routes:** `GET /api/core/portal/me` and admin commercial snapshot endpoints (`admin/commercial.py`).【F:platform/processing-core/app/services/portal_me.py†L171-L274】【F:platform/processing-core/app/routers/admin/commercial.py†L690-L750】

## Cards + CardAccess
- **Models:** `Card` in `platform/processing-core/app/models/card.py` and `CardAccess` in `platform/processing-core/app/models/client_portal.py`.【F:platform/processing-core/app/models/card.py†L1-L16】【F:platform/processing-core/app/models/client_portal.py†L64-L90】
- **DB tables:** `cards`, `card_access`, plus client-scoped `client_cards`.
- **Migrations:** `platform/processing-core/app/alembic/versions/20251208_0004a_bootstrap_clients_cards_partners.py` (cards/client_cards). No explicit migration found for `card_access` (verify/restore).【F:platform/processing-core/app/alembic/versions/20251208_0004a_bootstrap_clients_cards_partners.py†L1-L110】
- **Routes:** `platform/processing-core/app/routers/client_portal_v1.py` (cards list, issue, access grant/revoke).【F:platform/processing-core/app/routers/client_portal_v1.py†L3820-L4199】

## Documents (contracts/invoices/acts)
- **Models:** `CRMContract` (`crm_contracts`) in `platform/processing-core/app/models/crm.py` and invoices in `platform/processing-core/app/models/invoice.py`.【F:platform/processing-core/app/models/crm.py†L202-L229】【F:platform/processing-core/app/models/invoice.py†L38-L124】
- **DB tables:** `crm_contracts`, `invoices` (acts/other docs derived from CRM/document services).
- **Migrations:** `platform/processing-core/app/alembic/versions/20291401_0065_crm_core_v1.py` (crm_contracts) and invoice migrations in `platform/processing-core/app/alembic/versions` (verify exact revision for invoices).
- **Routes:** `platform/processing-core/app/routers/client_documents.py` (list/download/ack).【F:platform/processing-core/app/routers/client_documents.py†L1-L228】

## Export Jobs
- **Model:** `ExportJob` in `platform/processing-core/app/models/export_jobs.py`.【F:platform/processing-core/app/models/export_jobs.py†L11-L71】
- **DB table:** `export_jobs`.
- **Migrations:** `platform/processing-core/app/alembic/versions/20299060_0136_export_jobs.py` and follow‑ups for progress/format fields.【F:platform/processing-core/app/alembic/versions/20299060_0136_export_jobs.py†L1-L85】【F:platform/processing-core/app/alembic/versions/20299100_0140_export_job_progress.py†L1-L58】
- **Routes:** export endpoints in `platform/processing-core/app/routers/client_portal_v1.py` (exports list/create/download).【F:platform/processing-core/app/routers/client_portal_v1.py†L4602-L4759】
