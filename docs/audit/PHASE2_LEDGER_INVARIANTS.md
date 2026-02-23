# Audit Phase 2 — Ledger Invariants

## 1) Inventory pass before tests

### 1.1 Money-changing commands and idempotency coverage

| Command | Endpoint / Service | Idempotency mechanism | Status |
|---|---|---|---|
| Internal ledger posting | `POST /internal/ledger/transactions` (`InternalLedgerService.post_transaction`) | `internal_ledger_transactions.idempotency_key` unique + replay branch | Covered |
| Refund create | `POST /admin/refunds` (`RefundService.request_refund`) | `refund_requests.idempotency_key` unique + replay branch | Covered |
| Reversal create | `POST /admin/reversals` (`ReversalService.reverse_capture`) | `reversals.idempotency_key` unique + replay branch | Covered |
| Dispute accept/reject/open | `POST /admin/disputes/*` (`DisputeService`) | suffix-based keys in posting engine (`:refund`, `:fee`, `:release`) + posting batch unique idempotency | Partially covered |
| Posting batch write (core ledger) | `PostingEngine.apply_posting` | `posting_batches.idempotency_key` unique + replay branch | Covered |
| Event outbox publish | `publish_event` | `event_outbox.idempotency_key` unique index | Covered |

### 1.2 Command → posting map

- Refund (`SAME_PERIOD`): `PARTNER_PAYABLE (DEBIT)` + `CLIENT_MAIN (CREDIT)`.
- Refund (`ADJUSTMENT_REQUIRED`): `PLATFORM_ADJUSTMENT (DEBIT)` + `CLIENT_MAIN (CREDIT)`.
- Reversal (`SAME_PERIOD`): `PARTNER_PAYABLE (DEBIT)` + `CLIENT_MAIN (CREDIT)`.
- Reversal (`ADJUSTMENT_REQUIRED`): `PLATFORM_ADJUSTMENT (DEBIT)` + `CLIENT_MAIN (CREDIT)`.
- Dispute hold/release and refund/fee use dedicated reserve/revenue accounts.

### 1.3 Settlement period storage and status

- `settlement_periods.status` currently has lifecycle values: `OPEN`, `CALCULATED`, `APPROVED`, `PAID`.
- For refund/reversal/dispute scenario services, closed-period behavior is represented by explicit command flag `settlement_closed=True` and mapped to `SettlementPolicy.ADJUSTMENT_REQUIRED`.

---

## 2) Explicit invariant list

1. **Double-entry**: sum(debit) == sum(credit) per posting batch, per currency.
2. **No mixed currency within posting batch**.
3. **Account currency must match line currency**.
4. **No orphan posting lines**: posting belongs to batch/transaction and references operation or external reference.
5. **Immutability**: ledger entries are append-only.
6. **Deterministic minor-unit handling**: `Decimal` / integer minor units only, no float in ledger posting code paths.
7. **Idempotency** for refund/reversal/internal ledger postings: repeated key returns same object and no extra postings.
8. **Settlement boundaries**: for closed settlement, refunds/reversals write `ADJUSTMENT` postings and adjustment records.

---

## 3) Invariant → enforcement map

| Invariant | Code / DB enforcement | Tests |
|---|---|---|
| Double-entry | `FinancialInvariantChecker.validate_ledger_lines`, `PostingEngine.apply_posting` | `test_ledger_double_entry_and_balances` |
| Mixed currency forbidden | `InternalLedgerService._post_entries` + posting invariant checker | `test_currency_mismatch_rejected`, existing `test_custom_transaction_currency_isolation` |
| Currency match account | `FinancialInvariantChecker.check_ledger_lines` compares line/account currency | `test_currency_mismatch_rejected` |
| Append-only ledger entries | ORM hooks on `LedgerEntry` (`before_update`, `before_delete`) | `test_ledger_entries_are_append_only` |
| Idempotency replay | unique idempotency fields + replay branches | `test_same_idempotency_key_same_result_and_no_duplicate_entries` |
| Concurrency idempotency | unique constraint + `IntegrityError` recovery in `_get_or_create_transaction` | `test_concurrent_retries_create_exactly_one_transaction` |
| Closed-period adjustment-only behavior | `SettlementPolicy.ADJUSTMENT_REQUIRED`, posting type switch to `ADJUSTMENT` | `test_closed_settlement_refund_creates_adjustment_only` |
| Over-refund blocked | refund cap check against captured minus refunded | `test_refund_cannot_exceed_captured_amount` |
| Repeated reversal blocked | posted reversal existence check on operation | `test_repeated_reversal_of_same_operation_is_rejected` |

---

## 4) Ledger sample (before/after settlement-close)

- **Before close** (`settlement_closed=False`, refund=60 RUB):
  - DEBIT `PARTNER_PAYABLE` 60
  - CREDIT `CLIENT_MAIN` 60
  - Posting type: `REFUND`
- **After close** (`settlement_closed=True`, refund=60 RUB):
  - DEBIT `PLATFORM_ADJUSTMENT` 60
  - CREDIT `CLIENT_MAIN` 60
  - Posting type: `ADJUSTMENT` + financial adjustment record in next period

---

## 5) Extension points

- Payouts/clearing/FX should reuse `PostingEngine.apply_posting` as the invariant gate.
- Add scoped idempotency key model (`(scope, key)`), where scope includes tenant + operation family.
- For FX: enforce per-currency balanced legs + explicit revaluation postings.
