# Docs

## Tests

### Docker (full processing-core suite)

Run inside the core-api container to ensure full dependencies are available:

```bash
docker compose exec -T core-api pytest -q -x
```

Targeted selections:

```bash
docker compose exec -T core-api pytest -q -m "integration or smoke"
docker compose exec -T core-api pytest -q -m "contracts"
```

Container smoke checks:

```bash
docker compose exec -T core-api ls -la /app/docs/contracts/events
docker compose exec -T core-api alembic -c /app/app/alembic.ini current
```

### Host (Windows, light-weight)

Run only the host-safe tests from the repo root:

```bash
pytest -q -x
```

This defaults to `tests_host/` via root `pytest.ini`.

If you intentionally want to run a subset of processing-core tests on host and have the
necessary deps installed, you can explicitly target them:

```bash
pytest -q -m unit platform/processing-core/app/tests
```
