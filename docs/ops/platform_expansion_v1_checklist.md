# Platform Expansion v1 Checklist

## Product contours (AS-IS verification)
- [ ] Webhooks v1.1 (integration-hub API + partner portal UI).
- [ ] BI exports v1.1 (BI API + CSV/JSONL + manifest + ClickHouse sync).
- [ ] Portals MAX (client + partner portals in `frontends/`).
- [ ] Marketplace events registry (`docs/contracts/events/marketplace`).
- [ ] Support Inbox v1 (support requests API + portal UIs).
- [ ] Client Controls v1 (limits/users/services/features tabs + role gating).
- [ ] PWA v1 (manifest + service worker + routing + push wiring).
- [ ] OSRM provider (logistics-service, `LOGISTICS_PROVIDER=osrm`).
- [ ] Diadok prod-mode flags (integration-hub `DIADOK_MODE`, `DIADOK_API_TOKEN`).

## Runtime / infra checks
- [ ] Postgres/Redis/MinIO/ClickHouse up (compose).
- [ ] core-api/auth-host/ai-service health checks.
- [ ] document-service/logistics-service health checks (internal).
- [ ] gateway proxy and /metrics.

## Contract discipline
- [ ] Event registry in `docs/contracts/events/**` актуален.
- [ ] Marketplace namespace schemas есть и валидны.

## CI / quality gates (по факту workflows)
- [ ] Enum policy: `python scripts/check_enum_policy.py`.
- [ ] Contracts: `pytest -m contracts`.
- [ ] Smoke: alembic upgrade head (x2) + `pytest -m smoke -q`.
- [ ] Migration smoke: protected revisions + revision uniqueness.
- [ ] Packaging/installation (editable installs + tests for integration-hub/logistics-service).

## Commands
```bash
python -m pip install -U pip setuptools wheel

pip install -e platform/logistics-service
pip install -e platform/integration-hub

pytest platform/logistics-service -q
pytest platform/integration-hub -q
pytest -m contracts

python scripts/check_enum_policy.py

# Smoke / migrations (CI uses docker compose)
docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke up -d postgres

docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke run --rm --entrypoint "" \
  core-api python -m app.alembic.check_protected_revisions

docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke run --rm --entrypoint "" \
  core-api python -m app.alembic.check_revision_uniqueness

docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke run --rm --entrypoint "" \
  core-api alembic -c app/alembic.ini upgrade head
```
