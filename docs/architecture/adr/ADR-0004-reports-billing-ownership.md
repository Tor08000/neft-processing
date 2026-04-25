# ADR-0004: Reports billing ownership and access split

## Status
Accepted

## Context
`processing-core` currently exposes two different billing-summary surfaces over the same `billing_summary` storage:

- `/api/v1/admin/billing/summary*` provides admin-scoped detailed reads and control actions.
- `/api/v1/reports/billing/summary`, `/api/v1/reports/billing/daily`, `/api/v1/reports/turnover`, and `/api/v1/reports/turnover/export` remain no-auth report-style reads.

Repo tests also show that:

- `POST /api/v1/reports/billing/summary/rebuild` is admin-gated.
- public report reads and admin billing reads are projections over the same underlying summary rows, not separate ownership domains.

That means the current drift is not “missing implementation”. It is an ownership/access split that was still implicit.

## Decision
- `processing-core` remains the owner of billing-summary projection generation and storage.
- `/api/v1/admin/billing/summary*` is the canonical owner for authoritative billing-summary read/control.
- `/api/v1/reports/billing/summary`, `/api/v1/reports/billing/daily`, `/api/v1/reports/turnover`, and `/api/v1/reports/turnover/export` are compatibility read/export surfaces, not canonical billing source-of-truth APIs.
- `POST /api/v1/reports/billing/summary/rebuild` remains an admin-gated compatibility trigger until an explicit admin route handoff is approved.

## Why reports != canonical billing owner
- The admin surface exposes the full scoped billing-summary model: `client_id`, `merchant_id`, `product_type`, `currency`, `total_amount`, `total_quantity`, `commission_amount`, and pagination.
- The reports surface exposes thinner aggregate/export projections and does not own reconciliation, finalization, or detailed admin controls.
- Both surfaces read the same `billing_summary` rows, so the reports family is not an independent product owner; it is a compatibility projection family over storage owned in `processing-core`.

## What stays canonical
- `app/services/reports_billing.py` owns billing-summary projection build/list/finalize logic in `processing-core`.
- `app/routers/admin/billing.py` remains the canonical API owner for authoritative billing-summary inspection and control.
- `billing_summary` storage remains shared projection truth inside `processing-core`.

## What is compatibility-only
- public/no-auth report reads under `/api/v1/reports/*`
- thin summary projection under `/api/v1/reports/billing/summary`
- report export under `/api/v1/reports/turnover/export`
- admin-gated rebuild trigger still mounted under `/api/v1/reports/billing/summary/rebuild`

## What is explicitly out of scope
- changing money semantics
- changing billing formulas or summary generation logic
- removing the current public report routes
- introducing a new external/public route family
- route handoff/removal without explicit consumer diagnosis
