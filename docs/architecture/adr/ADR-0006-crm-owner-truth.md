# ADR-0006 — CRM Owner Truth

## Status

Accepted

## Decision

- Canonical CRM control plane owner is `processing-core` admin CRM under `/api/core/v1/admin/crm/*`.
- Canonical CRM read/write services live in:
  - `platform/processing-core/app/routers/admin/crm.py`
  - `platform/processing-core/app/services/crm/*`
  - `platform/processing-core/app/models/crm.py`
- Canonical repo-visible UI consumer is `frontends/admin-ui`.
- `platform/crm-service` is not the canonical CRM owner. It remains a compatibility/shadow CRM service behind `/api/v1/crm/*`.

## Why

- Repo-visible admin CRM business semantics, control-plane versioning (`X-CRM-Version`), contracts, subscriptions, profiles, onboarding, billing preview, and CFO explain are owned by `processing-core`.
- `crm-service` still exposes runtime CRUD for contacts/pipelines/deals/tasks/comments/audit, but no repo-visible frontend uses it as the primary CRM surface.
- Removing `/api/v1/crm/*` or flipping it to another owner without external consumer evidence would be speculative.

## Route Topology

- Canonical north star:
  - `/api/core/v1/admin/crm/*`
- Compatibility/shadow family:
  - `/api/v1/crm/*`
  - gateway alias `/api/crm/*`
- No handoff/removal for `/api/v1/crm/*` without external consumer diagnosis.

## Boundary Rules

- `support/cases` remain their own owner surface; CRM may link to them but does not own the case model.
- `admin commercial` remains owner for commercial entitlements/support/SLO/addons state; CRM may reference client/commercial state but does not replace that contour.
- `portal me/org/account` remains outside CRM ownership.
- `documents` remain document-service + processing-core orchestration ownership; CRM can require documents but does not own the document domain.

## Current Readiness

- `processing-core` admin CRM: contract-ready and actively owned, but still underpowered in some product surfaces.
- `admin-ui` CRM: now mounted and aligned to current backend truth, but still admin-only and not a full cross-portal CRM product.
- `crm-service`: compatibility-only shadow surface, not frozen for removal yet.
