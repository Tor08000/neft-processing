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

## GUID/UUID conventions

- Use `app.db.types.GUID()` for all new primary keys and foreign keys to ensure PostgreSQL uses native UUID and SQLite stores `VARCHAR(36)`.
- Generate identifiers with `app.db.types.new_uuid_str()`; ORM values are returned as strings for easier JSON/Pydantic interop.
- SQLite tests should work without UUID extensions because GUID stores strings transparently.

## Migration and test commands

Run migration checks (for example via Docker Compose):

```bash
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c ./app/alembic.ini heads"
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c ./app/alembic.ini upgrade head"
docker compose exec postgres psql -U neft -d neft -c "select to_regclass('public.billing_periods');"
```

Run focused tests:

```bash
pytest -q platform/processing-core/app/tests/test_billing_periods.py
pytest -q tests/test_alembic_single_head.py
```
