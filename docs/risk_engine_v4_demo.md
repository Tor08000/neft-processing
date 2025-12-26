# Risk Engine v4 — Enterprise Demo Script

## Scenario
**Payment → Risk BLOCK → Explain → Audit → Override**

**Goal:** demonstrate that NEFT is not billing, but a governed financial risk control system.

**Scope:** 1 client, 1 invoice, 1 payout attempt, Risk Engine v4 (reference).

## 1. Opening (30 seconds)
> “We have a payment. It looks correct. But the system considers it dangerous — and can prove it.”

**Context:**
- Client: new / no history
- Invoice: status **ISSUED**, amount is **large**

**Key phrase:**
> “From an accountant’s perspective — everything looks fine.”

## 2. Payment / Payout attempt (1 minute)
**Action:** Admin or system initiates payout.
- UI / API: `POST /payouts`

**Result:**
- ❌ **BLOCK**
- HTTP **403** / domain error
- Message: **“Operation blocked by risk policy.”**

## 3. Explain — Why BLOCK (2 minutes)
Open the **explain payload** (show meaning, not code):

```json
{
  "decision": "BLOCK",
  "score": 87,
  "thresholds": {
    "allow": 40,
    "review": 60,
    "block": 80
  },
  "policy": {
    "id": "HIGH_RISK_PAYOUT",
    "scope": "CLIENT"
  },
  "factors": [
    "client_age < 30d",
    "amount > P95",
    "velocity_spike"
  ],
  "model": {
    "name": "risk_v4",
    "version": "2025.01"
  },
  "decision_hash": "abc123..."
}
```

**Narration:**
- ❌ Not a black-box ML decision
- ❌ Not “the system decided”
- ✅ Reproducible rule
- ✅ Clear thresholds
- ✅ Factors explicitly listed

**Key phrase:**
> “We can explain this to an auditor, a regulator, or a court.”

## 4. Audit trail (2 minutes)
Open the **audit log**:

Show:
- timestamp
- actor
- entity (payout)
- decision
- hash
- link to explain

**Highlight:**
- Explain payload is persisted
- Immutable
- Bound to the operation

**Key phrase:**
> “This decision cannot be rewritten after the fact.”

## 5. Override (2 minutes)
Show that override is restricted to specific roles.

**Requires:**
- reason
- actor
- timestamp

**Action:**
- Admin → Override → **CONFIRM**

**Result:**
- payout proceeds
- audit captures:
  - override action
  - who approved
  - why

**Key phrase:**
> “A human makes the decision — the system protects it.”

## 6. Closing (1 minute)
**Summary:**
- ❌ Risk is not hidden
- ❌ No manual chaos
- ❌ No gray zones
- ✅ Risk is governed
- ✅ Decisions are explainable
- ✅ Accountability is transparent

**Closing phrase:**
> “NEFT is not a payment system. It is a system for controlling financial decisions.”

## Why this sells (enterprise)
**For enterprise:**
- ✔️ Lower operational risk
- ✔️ Protection for management
- ✔️ Regulator-grade rationale
- ✔️ Control instead of blanket bans

**For business:**
- ✔️ Less manual work
- ✔️ Fewer incidents
- ✔️ Faster scale

## Optional additions
- PDF **“Risk Decision Report”**
- Button **“Download explain”**
- SLA metric: **% blocked payouts**

## Delivery formats
This demo can be delivered in:
- Postman
- Swagger
- Admin UI
- Logs + JSON

**Main focus:** narrative, not interface.
