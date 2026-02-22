# FINAL Architecture Audit — NEFT Processing Platform (Deep Audit)

## Executive Summary

- Gateway contract is mostly consistent and explicitly enforces auth on admin/client/partner protected namespaces.
- Canonical auth namespace is implemented as `/api/v1/auth/*` with compatibility bridge `/api/auth/*`.
- Deprecated core aliases `/api/core/v1/client/*` and `/api/core/v1/partner/*` are present and marked with `X-API-Deprecated: true`.
- Verify endpoints are wired through dedicated internal gateway locations, reducing accidental policy drift.
- Request correlation is standardized with `X-Request-ID` mapping and JSON structured gateway logs.
- Core API routing strategy is complex because it keeps both legacy and canonical include trees; this increases shadow-route risk.
- Auth-host exposes both legacy and prefixed routes; this is practical but broadens route surface.
- Frontend API base normalization exists across all three portals; auth path normalization to `/api/v1/auth` is implemented.
- No direct hardcoded `/api/core/v1/client` or `/api/core/v1/partner` usage was found in client/partner frontends.
- Gateway has two mirrored config files (`gateway/nginx.conf`, `gateway/default.conf`) that can drift and must be guarded in CI.
- Compose declares healthchecks for core infra and apps, but smoke contract checks were not unified in one gateway-oriented script before this audit.
- DB migration single-head guards already exist in CI for core-api and should remain mandatory.
- Security baseline headers (CSP, XFO, nosniff) are present on gateway responses.
- Main residual risks: config drift, broad legacy compatibility surface, and insufficient automated bypass-attempt tests on encoded paths.

---

## Current Architecture Map

### Service topology (runtime compose)

| Service | Internal port | External port | Main role |
|---|---:|---:|---|
| gateway (nginx) | 80 | 80 (via container/gateway usage) | Entry routing, auth_request, SPA/static proxy |
| core-api (processing-core) | 8000 | 8000 | Core business API |
| auth-host | 8000 | 8002 | Auth issuance/verification and user bootstrap |
| admin-web | 80 | 4173 | Admin SPA |
| client-web | 80 | 4174 | Client SPA |
| partner-web | 80 | 4175 | Partner SPA |
| ai-service | 8000 | n/a | AI endpoints |
| crm-service | 8000 | n/a | CRM API |
| logistics-service | 8000 | n/a | Logistics API |
| document-service | 8000 | n/a | Documents API |
| integration-hub | 8000 | n/a | Integrations/webhooks |
| postgres | 5432 | 5432 | Primary DB |
| redis | 6379 | 6379 | Cache/queues |
| minio | 9000 | 9000/9001 | Object storage |
| clickhouse | 8123/9000 | 8123/9002 | BI analytics store |

### Critical flow (simplified)

`Browser SPA -> Gateway -> auth_request verify -> Core API -> Postgres/Redis/MinIO (+ optional downstream services)`

`Browser SPA -> Gateway -> /api/v1/auth/* -> Auth-host -> Postgres`

---

## Canonical API Contract

See dedicated artifact: `docs/audit/CANONICAL_API_CONTRACT.md`.

Highlights:
- Canonical protected paths:
  - `/api/core/v1/admin/*`
  - `/api/core/client/*`
  - `/api/core/partner/*`
- Canonical auth path:
  - `/api/v1/auth/*`
- Deprecated aliases preserved with deprecation header:
  - `/api/core/v1/client/*`
  - `/api/core/v1/partner/*`

---

## Auth & Entitlements

See detailed matrix: `docs/audit/AUTHZ_MATRIX.md`.

Findings:
- Gateway enforces role-domain separation by dedicated verify endpoints for admin/client/partner.
- Tokens are audience-separated in compose defaults (`neft-admin`, `neft-client`, `neft-partner`).
- UI gating should be interpreted against 403/401, not prefix-mismatch 404.

---

## Gateway & Routing Audit

### location policy status

| Area | Status | Notes |
|---|---|---|
| Auth-protected admin path | OK | `auth_request` + custom 401/403 JSON |
| Auth-protected client path | OK | Canonical + deprecated alias both guarded |
| Auth-protected partner path | OK | Canonical + deprecated alias both guarded |
| Deprecated alias headers | OK | `X-API-Deprecated: true` on legacy client/partner |
| Auth canonical path | OK | `/api/v1/auth/*` proxied to auth-host |
| SPA prefixes | OK | `/admin/`, `/client/`, `/partner/` isolated from `/api/*` |
| MIME mismatch observability | OK | `asset_mime_mismatch` log field present |
| Drift risk | WARNING | duplicated gateway config files can diverge |

### Potential bypass vectors reviewed

- trailing slash variants for namespaces
- encoded path traversal attempts (recommended to add explicit test vectors in smoke)
- authorization header propagation (`proxy_set_header Authorization $http_authorization`) is present

---

## Frontend API Consumption

| Frontend | Base resolution | Admin/client/partner route use |
|---|---|---|
| admin-web | normalized `VITE_API_BASE`/`VITE_API_BASE_URL` + constants | canonical admin namespace `/api/core/v1/admin` |
| client-web | shared join/normalize base builder | canonical `/api/core/client` usage path-building |
| partner-web | shared join/normalize base builder | canonical `/api/core/partner` usage path-building |

Notes:
- Auth base normalization maps to `/api/v1/auth`.
- Guard added in CI to fail on forbidden legacy client/partner prefixes in frontend code.

---

## DB & Migrations Hygiene

| Check | Status |
|---|---|
| Core single-head guard | Present in CI |
| Protected revision checks | Present in CI |
| Upgrade head smoke | Present in CI |
| Fresh database reproducibility | Covered by migration-smoke compose flow |

Recommendation:
- Add explicit partial-apply recovery scenario in CI nightly (non-blocking) to verify repair scripts.

---

## Observability & Audit Trail

- Gateway sets `X-Request-ID` from inbound header or generated request id.
- Gateway logs are JSON and include `request_id`, `upstream_status`, and `asset_mime_mismatch` marker.
- OTEL log collection path `/var/log/nginx/otel/access.log` is reserved in config.

Gap:
- End-to-end correlation assertion (gateway → core-api response header/log body) should be contract-tested in smoke.

---

## Security Review

### Positive baseline
- CSP and anti-mime/iframe headers are set by gateway.
- Auth guard enforced at gateway boundary before business namespaces.
- Compatibility aliases include explicit rewrites and do not disable auth_request.

### Risks
- CORS in auth-host currently allows `*`; acceptable for dev, high-risk for strict prod posture.
- No explicit rate limiting in gateway for auth/login burst paths (risk to brute-force surface).
- Trust chain headers are forwarded; prod deployment must ensure trusted reverse-proxy boundary.

---

## Risk Register

| Risk | Probability | Impact | Signal | Mitigation | Owner | ETA |
|---|---|---|---|---|---|---|
| Gateway config drift between `nginx.conf` and `default.conf` | Medium | High | route mismatch after edits | CI guard compares normalized route sections | Platform | 1 day |
| Legacy frontend path regression (`/api/core/v1/client|partner`) | Medium | High | UI modules fail with 404 | CI grep-guard on frontend trees | Frontend | 1 day |
| Missing deprecation header on legacy aliases | Low | Medium | clients cannot detect migration path | contract smoke checks headers | Platform | 1 day |
| auth_request bypass via encoded path patterns | Low | High | unauthorized 200 on protected path | add encoded-path bypass smoke vectors | Platform+Sec | 1 week |
| Weak auth-host CORS/rate-limit for prod | Medium | High | auth abuse bursts | strict env-specific CORS + rate-limit policy | Security | 1 week |

---

## Action Plan

### Quick wins (1 day)
1. Add CI grep-guards for forbidden frontend legacy paths.
2. Add CI guard for gateway config twin alignment.
3. Add unified Windows CMD smoke for gateway contract checks.

### Stabilization (1 week)
1. Extend smoke suite with bypass attempt vectors (encoded slash, path normalization edge-cases).
2. Add response-header assertions for `X-Request-ID` propagation and deprecation headers.
3. Freeze canonical contract docs as single source and link from runbooks.

### Hardening (2–4 weeks)
1. Add rate limiting for auth endpoints at gateway.
2. Enforce prod-grade auth-host CORS and proxy trust boundaries.
3. Add nightly migration resilience test (partial apply + repair + re-upgrade).

---

## Repro commands

- Stand up stack:
  - `docker compose up -d --build`
- Run contract smoke (Windows CMD):
  - `scripts\smoke\smoke_gateway_contract.cmd`
- Run CI guard locally (bash):
  - `scripts/ci/gate_contract_guards.sh`
