# E2E Scenarios (Cross-Cutting Playbooks)

This directory contains baseline end-to-end interaction playbooks for client, partner, and ops workflows.
Each scenario file follows a uniform template and explicitly marks missing functionality as **NOT IMPLEMENTED**.

## Conventions

- **API prefixes**:
  - Auth-host: `/v1/auth` (service `platform/auth-host`).
  - Core/Processing API: canonical owners usually live under `/api/core/*`; compatibility/public families may remain under `/api/*` or `/api/v1/*` in `platform/processing-core`.
  - Client portal compatibility families: `/api/v1/client/*`; canonical client owners are scenario-specific and may live under `/api/core/client/*` or `/api/core/v1/client/*`.
  - Client fleet: `/api/client/fleet` in `platform/processing-core`.
  - Integration hub: `/v1/webhooks` in `platform/integration-hub`.
- **Event catalog**: `docs/as-is/EVENT_CATALOG.md`.
- **Verification**: each scenario lists concrete pytest files and a `.cmd` smoke script (see `scripts/`).

## Files

- `SCENARIO_MATRIX.md` — matrix of scenario ↔ UI ↔ API ↔ DB ↔ events ↔ verified.
- `VERIFIED_MATRIX.md` — matrix of scenario ↔ pytest ↔ smoke ↔ prerequisites.
- Individual scenario playbooks: `CLIENT_*`, `PARTNER_*`, `OPS_*`.
