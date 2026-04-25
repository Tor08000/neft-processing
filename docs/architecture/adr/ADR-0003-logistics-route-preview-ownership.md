# ADR-0003: Logistics route preview ownership

## Status
Accepted

## Context
`processing-core` navigator is intentionally frozen as a local snapshot/evidence/explain contour. The unresolved question was whether `logistics-service` should become the owner of a new route capability, and if so, whether that capability should mean route preview compute or full snapshot ownership.

Current repo truth shows two different responsibilities:

- `logistics-service` is the natural owner for external routing compute.
- `processing-core` already owns persisted route snapshot/evidence used by admin, unified explain, and risk-adjacent readers.

This ADR fixes that ownership split explicitly before adding any new capability.

## Decision
- `logistics-service` is the owner only for **stateless route preview compute**.
- `processing-core` keeps ownership over **persisted route snapshot/evidence**.
- If v1 preview is implemented, it must be:
  - sync
  - stateless
  - internal-only
  - fail clearly by default

## Client write expansion proof
Client trip creation is mounted in `processing-core` as the persisted owner of the order/route/stop lifecycle. During creation, route points are passed to the logistics preview contour only for stateless compute; the returned provider geometry, distance, ETA, and assumptions are persisted back in `processing-core` as route snapshot and navigator explain evidence.

This keeps the owner split intact:

- `POST /api/core/client/logistics/trips` creates the durable trip, route, stops, audit entries, and legal graph links in `processing-core`.
- `logistics-service /api/int/v1/routes/preview` remains the external compute owner.
- if preview compute is unavailable, processing-core stores an explicit local fallback assumption (`preview_fallback=...`) instead of silently pretending the external provider succeeded.
- fuel-consumption analytics are read-only over persisted fuel links; provider-backed fuel-consumption writes remain frozen until external fuel proof exists.

Live evidence captured on 2026-04-25 is recorded in `docs/diag/client-logistics-write-expansion-live-smoke-20260425.json`: `POST /api/core/client/logistics/trips` returned `201`, direct logistics preview compute returned explicit `502 provider_error`, and the persisted route snapshot/explain stored provider `noop` with `preview_fallback=logistics_service_error`.

## Why preview != snapshot ownership
- A route preview is ephemeral compute: given ordered route points, return the current computed route shape and timing.
- A persisted snapshot is evidence: a stored artifact with local lifecycle, admin visibility, explain linkage, and risk-adjacent reuse.
- `processing-core` already reads persisted snapshot/evidence for:
  - admin route snapshot inspection
  - unified explain navigator section
  - risk-adjacent `route_deviation_score` and `eta_overrun_pct`
- Moving preview compute into `logistics-service` does not justify moving snapshot history, explain history, or evidence ownership out of `processing-core`.
- Therefore preview ownership and snapshot ownership stay intentionally split.

## v1 contract shape
v1 route preview, if added, should be an internal synchronous compute contract.

Response fields:
- `provider`
- `geometry`
- `distance_km`
- `eta_minutes`
- `confidence`
- `computed_at`
- `degraded`
- `degradation_reason`

Default semantics:
- truthful provider identity
- no silent mock fallback
- explicit degraded state only when intentionally supported
- otherwise fail clearly

## What stays in processing-core
- persisted route snapshot storage
- local `route_snapshot_id`
- local explain/evidence history
- admin read surface for latest route snapshot and navigator explains
- risk/explain consumption of stored snapshot/evidence

## What is explicitly out of scope
- persisted snapshot storage in `logistics-service`
- external `snapshot_id`
- external explain history
- async preview jobs
- provider-backed fuel-consumption writes
