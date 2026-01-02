# Settlement Runbook

<a id="payout-failed"></a>
## Incident: Payout failed
**Symptoms**
- Alert: `payout_failed` (P1).
- `payouts_total{status="FAILED"} > 0`.

**Checks**
- Inspect payout provider response codes and idempotency keys.
- Verify settlement period status and approval timestamp.
- Confirm ledger postings for the payout transaction.

**Actions**
- Retry payout with idempotency guard.
- If provider confirms success but ledger missing, apply adjustment.
- Escalate to provider support if repeated failures occur.

**Recovery verification**
- Payout succeeds and status transitions to `CONFIRMED`.
- No new payout failures.

## Incident: Settlement stuck in APPROVED
**Symptoms**
- Alert: `settlement_stuck` (P3).
- Approved settlement without payout initiation for > X hours.

**Checks**
- Verify settlement job queue and worker health.
- Confirm approval event exists and is not duplicated.
- Check payout scheduling service status.

**Actions**
- Retry payout initiation job.
- Manually confirm approval (stub) if automatic signal is missing.
- If approval is invalid, revert approval and re-calculate settlement.

**Recovery verification**
- Payout initiated within 10 minutes of approval.
- Approved backlog cleared.

## Incident: Mismatch after payout
**Symptoms**
- Reconciliation mismatch tied to payout records.
- Post-payout ledger divergence.

**Checks**
- Compare payout batch totals to ledger entries.
- Review reconciliation discrepancy records for the payout period.

**Actions**
- Run reconciliation + apply adjustment for confirmed differences.
- Lock affected accounts until ledger is balanced.

**Recovery verification**
- Reconciliation returns to matched state.
- Ledger and payout totals align.

## Related alerts
- payout_failed → settlement.md#payout-failed
