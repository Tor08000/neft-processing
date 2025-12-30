# Load testing results v1

## Tooling
- Load tool: **k6** (single source of truth)
- Environment: staging-like (Prod configs, masked data)
- Time window: TBD

## Scenarios

### Read-heavy (dashboard / transactions / documents)
| Profile | RPS | p50 | p95 | p99 | Error rate | Saturation point | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x2 | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x5 (stress) | TBD | TBD | TBD | TBD | TBD | TBD |  |

### Write-heavy (fuel authorize / settle, document render)
| Profile | RPS | p50 | p95 | p99 | Error rate | Saturation point | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x2 | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x5 (stress) | TBD | TBD | TBD | TBD | TBD | TBD |  |

### Mixed (authorize + explain + documents)
| Profile | RPS | p50 | p95 | p99 | Error rate | Saturation point | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x2 | TBD | TBD | TBD | TBD | TBD | TBD |  |
| x5 (stress) | TBD | TBD | TBD | TBD | TBD | TBD |  |

## Summary
- p95 latency targets: see `docs/ops/slo.md`.
- Error rate target: < 0.1%.
- Saturation point = RPS, после которой наблюдается рост p95/p99 и/или error rate.
