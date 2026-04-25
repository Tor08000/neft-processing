# S3/S4 Owner Review Closeout - 2026-04-25

## Scope

This review covers:

- S3 `auth-host`
- S4 satellite/backend services: `document-service`, `integration-hub`, `logistics-service`, `crm-service`, `ai-services/risk-scorer`, and `billing-clearing`

No staging, commits, branch split, patch bundles, public API removal, money formula changes, auth semantic changes, or provider credential changes were performed.

## S3 Auth-Host

Review-visible S3 scope:

| Status | Count |
| --- | ---: |
| `M` | 25 |
| `D` | 0 |
| `??` | 3 |
| Total | 28 |

Primary owner areas:

- login portal claims and audience/issuer resolution
- seeded admin/client/partner identities
- admin-users CRUD/RBAC topology
- JWT key persistence/JWKS/public-key compatibility
- bootstrap and DB-repair tests

Finding:

- `app/tests/test_auth_me.py::test_login_token_valid_for_me` patched `from app import services; services.keys`, but the current key owner is `app.services.keys`.
- The running `auth-host` container still had stale image code, so container pytest reproduced the old failure after the workspace fix.

Fix:

- `test_auth_me.py` now imports `from app.services import keys as key_service` and resets `_KEY_ERROR` with the key cache when testing persisted-key reuse.

Checks:

| Check | Result |
| --- | --- |
| `platform/auth-host/.venv/Scripts/python.exe -m pytest app/tests/test_admin_users_audit.py app/tests/test_admin_users_schema.py app/tests/test_admin_users_topology.py app/tests/test_login_portal_claims.py app/tests/test_auth.py app/tests/test_auth_me.py app/tests/test_bootstrap_unit.py app/tests/test_rbac_contract.py app/tests/test_jwks.py app/tests/test_health.py -q` | PASS, `52 passed`, `12 warnings` |
| `platform/auth-host/.venv/Scripts/python.exe -m compileall -q app` | PASS |
| `docker compose exec -T auth-host pytest ...` before rebuild | STALE_IMAGE_FAIL, old `services.keys` test code still present in running image |

Review decision:

- S3 is reviewable from workspace/service-venv evidence.
- Auth-host image should be rebuilt before final runtime packaging evidence, but no auth-host runtime semantic blocker was found.

## S4 Satellite/Backend Services

Review-visible S4 scope:

| Status | Count |
| --- | ---: |
| `M` | 68 |
| `D` | 0 |
| `??` | 19 |
| Total | 87 |

Primary owner areas:

- document-service signing provider registry, templates, prod guardrails
- integration-hub EDO/Diadok/SBIS/OTP/email/webhook degraded/provider truth
- logistics-service provider split, OSRM preview compute, idempotency
- CRM migration/runtime guard compatibility
- AI risk-scorer reproducible contract support
- billing-clearing job evidence and task wiring

Checks:

| Check | Result |
| --- | --- |
| `platform/document-service/.venv/Scripts/python.exe -m pytest app/tests -q` | PASS, `35 passed`, `4 warnings` |
| `platform/integration-hub/.venv/Scripts/python.exe -m pytest neft_integration_hub/tests -q` | PASS, `47 passed`, `5 warnings` |
| `python -m pytest neft_logistics_service/tests/test_settings_and_provider_selection.py neft_logistics_service/tests/test_integration_hub_provider.py neft_logistics_service/tests/test_osrm_provider.py -q` | PASS, `13 passed` |
| `python -m compileall -q neft_logistics_service` | PASS |
| `python -m compileall -q app` in `platform/crm-service` | PASS |
| `python -m compileall -q app` in `platform/ai-services/risk-scorer` | PASS |
| `python -m compileall -q app` in `platform/billing-clearing` | PASS |
| Live `GET /health` on ports `8003`, `8004`, `8005`, `8006`, `8007` | PASS, all returned `200` |

Harness boundaries:

- logistics-service host full tests that import `fastapi.testclient` cannot run on the global host Python because `fastapi` is absent; pure provider/idempotency-adjacent tests plus compileall passed.
- CRM host pytest cannot collect because global host Python lacks `fastapi`; compileall and live health passed.
- AI risk-scorer host pytest cannot collect because global host Python lacks `fastapi`; compileall and live health passed.
- logistics/CRM/AI runtime images do not include `pytest`, so container pytest is not a valid test entrypoint for these services.

Live provider truth:

| Service | Health | Provider truth |
| --- | --- | --- |
| `ai-service` | `200 ok` | no external provider row required for this slice |
| `document-service` | `200 ok` | `esign_provider:DEGRADED` |
| `integration-hub` | `200 ok` | `diadok:DEGRADED`, `sbis:UNSUPPORTED`, `smtp_email:DISABLED`, `otp_sms:DEGRADED`, `notifications:DEGRADED`, webhook policy degraded |
| `logistics-service` | `200 ok` | `logistics_transport:CONFIGURED`, `osrm_route_compute:CONFIGURED` |
| `crm-service` | `200 ok` | no external provider row required for this slice |

Review decision:

- S4 is reviewable with explicit harness exceptions.
- No provider was promoted to sandbox/production readiness by this review.
- No silent fallback or mock-by-default acceptance was added.
