# Runbook: Reports compatibility routes usage readout

## Purpose
- Collect a bounded usage snapshot for:
  - `/api/v1/reports/billing/daily`
  - `/api/v1/reports/billing/summary`
  - `/api/v1/reports/turnover`
  - `/api/v1/reports/turnover/export`
  - `POST /api/v1/reports/billing/summary/rebuild`
- Separate traffic into:
  - `external`
  - `synthetic`
  - `internal_admin`
- Decide only one of:
  - `final compatibility freeze`
  - `guarded handoff plan`

## Inputs
- Best path: read-only kube access.
- Alternative path: direct Prometheus/Loki URLs.
- Fallback path: bounded gateway/core log files plus Prometheus snapshot.

## Local setup
1. Put kubeconfig at `C:\neft-processing\.ops\kubeconfig.yaml`.
2. Copy `C:\neft-processing\.ops\access.example.ps1` to `C:\neft-processing\.ops\access.ps1`.
3. Fill:
   - `NEFT_STAGE_CONTEXT`
   - `NEFT_STAGE_NAMESPACE`
   - `NEFT_PROD_CONTEXT`
   - `NEFT_PROD_NAMESPACE`
4. Load local access variables:

```powershell
. C:\neft-processing\.ops\access.ps1
```

## Plan-only sanity
```powershell
powershell -ExecutionPolicy Bypass -File C:\neft-processing\scripts\ops\collect_reports_compat_snapshot.ps1 -Environment stage -PlanOnly
```

## Collect stage snapshot
```powershell
powershell -ExecutionPolicy Bypass -File C:\neft-processing\scripts\ops\collect_reports_compat_snapshot.ps1 -Environment stage
```

## Collect prod snapshot
```powershell
powershell -ExecutionPolicy Bypass -File C:\neft-processing\scripts\ops\collect_reports_compat_snapshot.ps1 -Environment prod
```

## Outputs
- `.ops/snapshots/stage/<timestamp>/summary.md`
- `.ops/snapshots/stage/<timestamp>/summary.json`
- `.ops/snapshots/prod/<timestamp>/summary.md`
- `.ops/snapshots/prod/<timestamp>/summary.json`

## Decision rule
- Any route with `external` traffic => do not remove/handoff blindly; design guarded handoff plan.
- No `external` traffic and only `synthetic` / `internal_admin` => keep final compatibility freeze.
- If logs are missing and only metrics exist => insufficient evidence; do not decide yet.
