# Proration v2

## Segment generation

- Segments cover the full billing period without overlaps.
- Each segment is assigned a tariff and status (`ACTIVE`, `PAUSED`).
- Segment `reason` is derived from the triggering change (`START`, `UPGRADE`, `DOWNGRADE`, `PAUSE`, `RESUME`, `CANCEL`).

## Base fee

```text
base_fee_segment = floor(base_fee_month_minor * segment_days / period_days)
```

## Included metrics

- `DAILY`: `floor(included_month * segment_days / period_days)`
- `LINEAR`: `floor(included_month * segment_days / period_days)`

All values are computed in minor units and rounded down.

