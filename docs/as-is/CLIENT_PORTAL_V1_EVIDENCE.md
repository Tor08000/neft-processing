# Client Portal v1.0 Evidence

## Commands

### Local run (example)

```bash
docker compose up -d
```

### Smoke (Windows)

```cmd
scripts\smoke_client_portal.cmd
```

### Pytest (API)

```bash
pytest platform/processing-core/app/tests -k "client"
```

## Results

### Smoke

Attempted (failed in this environment: permission denied running Windows `.cmd` on Linux).

Command:

```bash
./scripts/smoke_client_portal.cmd
```

Result:

```
/bin/bash: line 1: ./scripts/smoke_client_portal.cmd: Permission denied
```

### Pytest

Attempted (failed because postgres is required by test harness).

Command:

```bash
DATABASE_URL=sqlite:///./test_client_portal_v1.db NEFT_AUTO_CREATE_SCHEMA=true pytest platform/processing-core/app/tests/test_client_portal_v1_cards.py
```

Result:

```
Failed: postgres not available; start docker compose postgres
```

### E2E (Playwright)

Not run in this change set.
