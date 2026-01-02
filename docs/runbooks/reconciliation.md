# Reconciliation Runbook

<a id="mismatch"></a>
## Incident: Growing mismatches
**Symptoms**
- Alert: `reconciliation_mismatch` (P2).
- Increasing `reconciliation_links_total{status="mismatched"}`.

**Checks**
- Identify scope (internal vs external) and mismatch type.
- Review last successful reconciliation run and compare input sources.
- Inspect discrepancy records for repeated root cause patterns.

**Actions**
- Re-run reconciliation for the affected scope/time window.
- For known false positives, mark discrepancy as ignored with explicit reason.
- If mismatch is real, create the appropriate ledger adjustment and re-link.

**Recovery verification**
- `reconciliation_open_discrepancies` trends down.
- Mismatched links return to baseline.
- Latest run reports success with expected counts.

## Incident: External statements missing
**Symptoms**
- External reconciliation delay exceeds 24h.
- `reconciliation_runs_total{scope="external",status="failed"}` increases.

**Checks**
- Confirm statement ingestion job status and object storage availability.
- Verify provider SFTP/API delivery window.
- Inspect ingestion logs for parsing or schema errors.

**Actions**
- Trigger manual re-fetch or backfill for missing statements.
- Pause reconciliation for the missing date range to avoid noise.
- Once statements arrive, rerun reconciliation for the impacted window.

**Recovery verification**
- External delay returns within SLO.
- No backlog of missing statements.
- Reconciliation run completes successfully.

## Incident: Failed reconciliation run
**Symptoms**
- Alert: `reconciliation_backlog` (P2).
- Failed run status or repeated retries.

**Checks**
- Inspect run logs and error codes (timeouts, parsing, DB constraints).
- Confirm database health and job queue depth.
- Validate input data snapshots are available.

**Actions**
- Restart the failed run with a narrower scope if needed.
- Increase worker capacity temporarily to drain backlog.
- Mark known-bad inputs as ignored with a documented reason.

**Recovery verification**
- Backlog clears and pending links decrease.
- Successful run status for the latest window.

## Related alerts
- reconciliation_mismatch → reconciliation.md#mismatch
