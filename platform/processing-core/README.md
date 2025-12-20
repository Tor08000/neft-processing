Core API service (FastAPI)

## Operational scenarios (refund / reversal / dispute)

Admin endpoints (prefixed with `/api/core/v1/admin`):

- `POST /refunds` — create refund with idempotency and settlement boundary detection.
- `POST /reversals` — request capture reversal, creating adjustment when settlement is closed.
- `POST /disputes/open` — open dispute (optionally place hold).
- `POST /disputes/{id}/review` — move dispute to review.
- `POST /disputes/{id}/accept` — accept dispute, posting refund/fee and creating adjustment if needed.
- `POST /disputes/{id}/reject` — reject dispute and release hold.
- `POST /disputes/{id}/close` — finalize accepted/rejected dispute.

Smoke tests:

```bash
pytest platform/processing-core/app/tests/test_refunds.py -q
pytest platform/processing-core/app/tests/test_reversals.py -q
pytest platform/processing-core/app/tests/test_disputes.py -q
```
