# Fleet Assistant v1.1 — Outcome Projection (No-ML)

## Overview
Outcome Projection provides a deterministic, non-ML estimate of what is likely to happen if a Fleet Assistant action is applied or ignored. The projection is an **assessment**, not a guarantee.

The projection uses existing sources only:
- action confidence (decay-weighted) and sample size within the 90-day window
- trend label from fleet trends
- SLA remaining minutes and insight aging escalation rules

## Payload (Assistant response)
```
projection: {
  if_applied: {
    probability_improved_pct,
    expected_effect_label,
    expected_time_window_days,
    expected_kpis: [{ kpi, direction, estimate }],
    basis: { confidence, sample_size, half_life_days, trend_label }
  },
  if_ignored: {
    probability_worse_pct,
    expected_effect_label,
    escalation_risk: { likely, eta_minutes, reason },
    expected_kpis: [{ kpi, direction, estimate }],
    basis: { trend_label, aging_days, sla_remaining_minutes }
  }
}
```

## Rules (deterministic, no ML)
### If applied
- `probability_improved_pct = round(100 * confidence)`
- effect label:
  - `confidence >= 0.6` → `IMPROVED`
  - `0.35–0.59` → `NO_CHANGE`
  - `< 0.35` → `WORSE`
- KPI ranges (static mapping):
  - `IMPROVED` → `5–12 points` for driver/station scores, `5–12%` for vehicle efficiency delta
  - `NO_CHANGE` → `0–3 points` / `0–3%`
  - `WORSE` → `0–8 points up` / `0–8% up`

### If ignored
- trend baseline:
  - `DEGRADING` → 40
  - `STABLE` → 20
  - `IMPROVING` → 10
- `+10` if `sla_remaining_minutes < 12h`
- `+10` if `aging_days >= 10`
- escalation risk:
  - likely when SLA exists and remaining ≤ 24h
  - likely when insight aging ≥ 14d and status is `OPEN`
  - if no SLA, `likely = false` with reason `no SLA`

## UI messaging
Fleet Assistant answers include a compact “What happens if…” section with 2–3 short lines and an expandable JSON payload.

## Limitations
Outcome Projection is based on historical confidence and trend labels only. It does not introduce new risk, fuel, or logistics signals and should not be treated as a precise prediction.
