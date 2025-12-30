# Platform Expansion v1 Checklist

## Webhooks
- [ ] webhooks ok

## OSRM
- [ ] OSRM ok

## Diadok prod
- [ ] Diadok prod ok

## Multi-tenant isolation
- [ ] multi-tenant isolation ok

## Load tests
- [ ] load tests ok

## Audit
- [ ] audit intact

## Packaging checks
- [ ] tests run from repo root without PYTHONPATH

Commands:
- `pip install -e platform/integration-hub`
- `pip install -e platform/logistics-service`
- `pytest platform/integration-hub -q`
- `pytest platform/logistics-service -q`

Build tools:
- `pip install --upgrade setuptools wheel`
