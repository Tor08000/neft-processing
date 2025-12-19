# UPAS alignment snapshot

## Services present in the repository
- **Gateway** (nginx) routes `/api/v1/*`, `/admin/api/v1/*`, `/client/api/v1/*` plus `/health`, `/metrics`, and SPA assets.
- **Auth Host** (FastAPI, platform/auth-host): authentication, demo users, JWT issuance.
- **Core API** (FastAPI, platform/processing-core): processing pipeline, admin APIs, migrations.
- **AI Risk scorer** (platform/ai-services/risk-scorer): stubbed risk response for tests.
- **Workers/Beat** (platform/billing-clearing): Celery worker images re-used for async jobs.
- **Observability**: otel-collector, Jaeger, Prometheus, Grafana dashboards.
- **Frontends**: admin-ui and client-portal builds served via gateway.

## Gaps vs UPAS target surface
- **Billing/Clearing flows**: only partial Celery scaffolding; no end-to-end settlement clearing yet.
- **Eventing**: no dedicated event bus or audit stream outside of DB tables/logs.
- **Security hardening**: JWT/secret rotation minimal; RBAC rules limited.
- **AI service depth**: risk-scorer is static; no adaptive/feedback loop.

## MVP E2E processing next steps
1. **Authorize → capture → reverse path**
   - Keep `operations` lifecycle consistent with enums and migration 20261020_0013.
   - Expose idempotency keys for auth/capture/reverse endpoints and persist request hashes.
2. **Idempotency guards**
   - Store idempotency tokens per client/card/terminal; return prior responses on replay.
3. **Rules/pricing decisioning**
   - Minimal pricing engine: fetch tariff from billing tables; fail closed when missing.
   - Risk adapter should honour rule/action priorities and bubble reasons into responses.
4. **Transaction recording & UI surfacing**
   - Ensure posting engine writes ledger movements for commit/reverse.
   - Admin/client portals: surface latest operations with risk/limit metadata and statuses.
5. **Test coverage**
   - Extend pytest fixtures to seed tariffs/limits/rules along with realistic cards/clients.
   - Add regression tests for double reversals and partial captures/refunds.
