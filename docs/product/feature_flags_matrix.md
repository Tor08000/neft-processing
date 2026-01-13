# Feature Flags Matrix

This matrix captures feature flags and related toggles discovered in the repo, across backend env, frontend `VITE_*` flags, and database-driven flags.

## Environment feature flags (backend + shared)

| Flag | Domain | Default | Where configured | Effect | Notes |
| --- | --- | --- | --- | --- | --- |
| `NEFT_BOOTSTRAP_ENABLED` | auth/bootstrap | `1` (true) | env (`.env.example`) | Enables initial admin bootstrap flow for auth-host. | **Backend.** Safe for prod if bootstrap flow is desired; disable after initial provisioning to prevent re-seeding. Depends on auth-host startup. |
| `AI_RISK_ENABLED` | ai/risk | `true` | env (`shared/python/neft_shared/settings.py`) | Enables AI risk scoring integration. | **Backend.** Requires `ai-service` reachable; safe if service available. |
| `LOGISTICS_NAVIGATOR_ENABLED` | logistics/navigator | `true` | env (`shared/python/neft_shared/settings.py`) | Enables logistics navigator features. | **Backend.** Requires navigator provider configuration (`LOGISTICS_NAVIGATOR_PROVIDER`). |
| `LOGISTICS_SERVICE_ENABLED` | logistics | `false` | env (`shared/python/neft_shared/settings.py`) | Enables calls to `logistics-service`. | **Backend.** Requires `logistics-service` running. |
| `NEFT_BILLING_DAILY_ENABLED` | billing | `true` | env (`shared/python/neft_shared/settings.py`) | Enables daily billing runs. | **Backend.** Operational toggle for scheduler/worker; safe but affects billing cadence. |
| `NEFT_CLEARING_DAILY_ENABLED` | clearing | `true` | env (`shared/python/neft_shared/settings.py`) | Enables daily clearing runs. | **Backend.** Operational toggle for scheduler/worker; safe but affects clearing cadence. |
| `NEFT_INVOICE_MONTHLY_ENABLED` | invoicing | `false` | env (`shared/python/neft_shared/settings.py`, `.env.example`) | Enables monthly invoice generation. | **Backend.** Requires invoice pipeline + storage. |
| `NEFT_PDF_AUTO_GENERATE` | invoicing/pdf | `false` | env (`shared/python/neft_shared/settings.py`, `.env.example`) | Enables automatic PDF generation for invoices. | **Backend.** Requires S3 buckets configured. |
| `ACCOUNTING_EXPORT_ALERTING_ENABLED` | accounting/exports | `false` | env (`shared/python/neft_shared/settings.py`) | Enables alerting for export SLA breaches. | **Backend.** Requires alerting targets configured. |
| `DOCUMENT_SERVICE_ENABLED` | documents | `false` | env (`shared/python/neft_shared/settings.py`) | Enables document-service integration. | **Backend.** Requires `document-service` running. |
| `S3_OBJECT_LOCK_ENABLED` | trust/storage | `false` | env (`shared/python/neft_shared/settings.py`, `.env.example`) | Enables S3 object lock/WORM on exports. | **Backend.** Requires bucket/object-lock support and permissions. |
| `LEGAL_GOST_VERIFY_ENABLED` | compliance/legal | `false` | env (`shared/python/neft_shared/settings.py`) | Enables GOST verification flow. | **Backend.** Requires GOST verification integration. |
| `BI_CLICKHOUSE_ENABLED` | analytics | `false` | env (`shared/python/neft_shared/settings.py`) | Enables ClickHouse BI sync. | **Backend.** Requires ClickHouse running and reachable. |

## Frontend flags (Vite env)

| Flag | Domain | Default | Where configured | Effect | Notes |
| --- | --- | --- | --- | --- | --- |
| `FEATURE_FLAGS` (string) | frontend/global | `ai_scorer:on,ai_anomaly:off` | env (`.env.example`) | String of UI feature toggles parsed by clients. | **Frontend.** Parsing rules are UI-specific; safe to toggle without DB migrations. |
| `VITE_API_BASE_URL` | frontend/network | `http://gateway` | env (`.env.example`) | Base URL for API gateway access in UIs. | **Frontend.** Set to gateway host; required for local dev. |
| `VITE_CORE_API_BASE` | frontend/network | `/api/core` | env (`.env.example`) | Overrides core API base path. | **Frontend.** Use when gateway paths differ. |
| `VITE_AUTH_API_BASE` | frontend/network | `/api/auth` | env (`.env.example`) | Overrides auth API base path. | **Frontend.** Use when gateway paths differ. |
| `VITE_AI_API_BASE` | frontend/network | `/api/ai` | env (`.env.example`) | Overrides AI API base path. | **Frontend.** Use when gateway paths differ. |
| `VITE_LOCALE` | frontend/i18n | `ru` (fallback `en`) | env (`frontends/*/src/i18n/index.tsx`) | Selects UI locale. | **Frontend.** Safe to toggle; `ru` default when unset. |
| `VITE_PWA_MODE` | frontend/pwa | `off` | env (`frontends/client-portal/src/pwa/mode.ts`) | Enables PWA UI mode. | **Frontend.** Requires PWA assets/manifest. |
| `VITE_PUSH_PUBLIC_KEY` | frontend/push | unset | env (`frontends/client-portal/src/pages/FleetNotificationChannelsPage.tsx`) | Enables Web Push setup with VAPID key. | **Frontend.** Requires push service/VAPID keys. |
| `VITE_MARKETPLACE_ORDERING` | frontend/marketplace | `off` | env (`frontends/client-portal/src/pages/MarketplaceProductDetailsPage.tsx`) | Enables marketplace ordering UI. | **Frontend.** Requires marketplace/order APIs. |
| `VITE_ADMIN_REDACTION` | frontend/admin | `on` | env (`frontends/admin-ui/src/redaction/apply.ts`) | Enables admin UI redaction; `off` disables masking. | **Frontend.** Safe to toggle; no migrations. |
| `VITE_OBSERVABILITY_TRACE_URL_TEMPLATE` | frontend/admin/observability | unset | env (`frontends/admin-ui/src/pages/cases/CaseDetailsPage.tsx`) | Enables link-out to tracing system. | **Frontend.** Requires trace backend URL template. |

## Database-driven feature flags

| Flag | Domain | Default | Where configured | Effect | Notes |
| --- | --- | --- | --- | --- | --- |
| `CRMFeatureFlagType.*` (`FUEL_ENABLED`, `LOGISTICS_ENABLED`, `DOCUMENTS_ENABLED`, `RISK_BLOCKING_ENABLED`, `ACCOUNTING_EXPORT_ENABLED`, `SUBSCRIPTION_METER_FUEL_ENABLED`, `CASES_ENABLED`) | crm/features | disabled unless set | `crm_feature_flags` table (`platform/processing-core/app/models/crm.py`) | Per-tenant/client feature gating in CRM, decision context, billing, and UI. | **Backend + frontend.** Controlled via admin API (`/crm/clients/{client_id}/features/*`). Safe to toggle without DB migrations; depends on underlying services (e.g., documents/logistics). |
| `SubscriptionPlanModule.module_code` (`FUEL_CORE`, `AI_ASSISTANT`, `EXPLAIN`, `PENALTIES`, `MARKETPLACE`, `ANALYTICS`, `SLA`, `BONUSES`) | subscriptions/modules | `enabled=true` per plan module | `subscription_plan_modules` table (`platform/processing-core/app/models/subscriptions_v1.py`) | Controls entitlements per subscription plan. | **Backend + frontend.** Managed via subscription plan APIs; safe to toggle but affects entitlements and pricing logic. |

## Notes

- Defaults reflect code defaults and `.env.example` where applicable; production values may differ.
- For backend flags that enable integrations, ensure the required service endpoints, buckets, or credentials exist before enabling in production.
