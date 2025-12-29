# Fleet Intelligence v1 (No-ML)

## Overview

Fleet Intelligence v1 delivers deterministic, read-only scoring for driver behavior, vehicle efficiency, and station trust.
Scores are exposed via CRM/Unified Explain and are available as enrich-only factors in risk contexts. No blocking is performed.

## Data model

### Daily aggregates

Source-of-truth daily tables (yesterday in client timezone):

* `fi_driver_daily` (driver_id, day)
* `fi_vehicle_daily` (vehicle_id, day)
* `fi_station_daily` (station_id, day)

### Score tables

* `fi_driver_score` (window_days 7/30)
* `fi_vehicle_efficiency_score` (window_days 7/30)
* `fi_station_trust_score` (window_days 7/30)

## Scores

### Driver behavior score (0..100, 100 = worse)

Formula is deterministic with fixed weights and normalization thresholds (see
`platform/processing-core/app/services/fleet_intelligence/defaults.py`).

Levels:

* 0–25 LOW
* 26–50 MEDIUM
* 51–75 HIGH
* 76–100 VERY_HIGH

### Vehicle efficiency score (0..100, 100 = best)

* Baseline: rolling 30d median ml/100km.
* Actual: window average (7d or 30d) of ml/100km.
* `delta_pct = (actual - baseline) / baseline`

If no distance data is available, `efficiency_score = null` with explain reason.

### Station trust score (0..100, 100 = best)

Base 100 with penalties:

* −30 for high risk block rate.
* −20 for burst patterns.
* −0.3 × outlier score.
* Additional penalties for decline rate and network volume deviation.

Levels:

* 80–100 TRUSTED
* 50–79 WATCHLIST
* 0–49 BLACKLIST

## Integrations

### Risk enrichment

Risk contexts are enriched (no blocking):

* `driver_score_level`
* `station_trust_level`
* `vehicle_efficiency_delta_pct`

### CRM reports

Read-only admin endpoints:

* `GET /admin/fleet-intelligence/drivers?client_id=&window_days=`
* `GET /admin/fleet-intelligence/vehicles?client_id=&window_days=`
* `GET /admin/fleet-intelligence/stations?tenant_id=&window_days=`

Actionable insights (v1.1, no new signals):

* `GET /admin/fleet-intelligence/insights/drivers?client_id=&window_days=`
* `GET /admin/fleet-intelligence/insights/vehicles?client_id=&window_days=`
* `GET /admin/fleet-intelligence/insights/stations?tenant_id=&window_days=`
* `GET /admin/fleet-intelligence/insights/subject?fuel_tx_id=`

### Unified Explain

Unified Explain includes a `fleet_intelligence` section for fuel transactions:

* driver behavior score/level
* station trust score/level
* vehicle efficiency score/delta

Unified Explain also includes `fleet_insight` (v1.1) when driver/vehicle/station
ids are present (or when insights are available for the client):

* `primary_insight` (exactly one)
* `secondary_insights` (no duplicates)

Thresholds are defined in `platform/processing-core/app/services/fleet_intelligence/defaults.py`
under `FI_THRESHOLDS` and only apply to existing scores.

## Jobs

* Daily aggregates (yesterday): `fleet_intelligence.compute_daily_aggregates`
* Score computation (7d/30d): `fleet_intelligence.compute_scores`

Cron schedule is configured in `platform/processing-core/app/celery_client.py`.
