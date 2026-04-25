# S13 Root Misc / Generated / Risky Deletions Review - 2026-04-25

## Scope

This review covers S13 from `docs/diag/RELEASE_PATCH_SLICES_20260425.md`, excluding files already owned by S1:

- root-level files not covered by gateway/compose-wrapper S1
- `shared/python/**`
- `sitecustomize.py`
- generated root scratch that remains outside `docs/diag`

No staging, commits, branch split, patch bundle generation, public API changes, money semantic changes, auth semantic changes, route-family removals, or broad deletion acceptance were performed.

## S13 Current State

Review-visible S13 scope after restoring root project-entrypoint files and ignoring the generated root `accept` scratch file:

| Status | Count |
| --- | ---: |
| `M` | 3 |
| `D` | 15 |
| `??` | 0 |
| Total | 18 |

Modified root/shared files:

- `shared/python/neft_shared/logging_setup.py`
- `shared/python/neft_shared/settings.py`
- `sitecustomize.py`

Deleted root files:

- `admin_login.json`
- `admin_tests.cmd`
- `ai_tests.cmd`
- `auth_tests.cmd`
- `curl`
- `diag_v021.txt`
- `docs_client_logistics_not_found_report.md`
- `find_auth_endpoints.py`
- `index.html`
- `inspect_neft_repo.py`
- `req.json`
- `run_tests.cmd`
- `selftest.cmd`
- `structure.txt`
- `tree_to_file.cmd`

Restored root project-entrypoint files:

- `.pre-commit-config.yaml`
- `AGENTS.md`
- `CHANGELOG.md`
- `Makefile`
- `README.md`
- `conftest.py`
- `pytest.ini`
- `docker-compose.dev.yml`
- `docker-compose.smoke.yml`
- `docker-compose.test.yml`

These files now match `HEAD` and are no longer S13 deletion candidates.

## Modified File Review

| File | Classification | Evidence |
| --- | --- | --- |
| `shared/python/neft_shared/logging_setup.py` | runtime bug fix | JSON logging now serializes UUID and other non-JSON extras with `default=str`; container targeted test passed. |
| `shared/python/neft_shared/settings.py` | provider truth bug fix | SMS/voice providers default to explicit `disabled` instead of local stub-by-default; stub providers remain opt-in through env. |
| `sitecustomize.py` | harness/runtime bootstrap change | Container path bootstrap compiles and works in core-api targeted tests; root `pytest.ini`/`conftest.py` have been restored so host pytest owns shared-path setup instead of direct Python import magic. |

## Deleted File Classification

The reference scan found no current repo references to the remaining deleted root helper filenames. The project-entrypoint docs/config/test harness files were restored from `HEAD` instead of accepted as deletions.

Reviewable scratch/helper deletion candidates:

- `admin_login.json`
- `diag_v021.txt`
- `req.json`
- `structure.txt`
- `index.html`
- `curl`

Reason: these classify as generated/local scratch residue. They have no current references and are not launch evidence.

Reviewable retired helper deletion candidates with replacement entrypoints:

- `admin_tests.cmd` -> replaced by `scripts/smoke_admin_v1.cmd`, `scripts/smoke_admin_shell.cmd`, and admin-ui Vitest/build evidence
- `ai_tests.cmd` -> replaced by AI/risk targeted pytest and ai-service tests referenced from `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md`
- `auth_tests.cmd` -> replaced by `scripts/test_auth_host.cmd` plus S3 auth-host suite evidence
- `run_tests.cmd` and `selftest.cmd` -> replaced by `scripts/verify_all.cmd` and the owner-slice checks in `docs/diag/RELEASE_PATCH_SLICES_20260425.md`
- `find_auth_endpoints.py`, `inspect_neft_repo.py`, `tree_to_file.cmd`, `docs_client_logistics_not_found_report.md` -> retired local diagnostics; no current references

These helper deletions are reviewable only inside S13 and only with the replacement/freeze notes above. They must not be mixed with generated scratch.

## Generated Scratch Policy

The root `accept` file is ignored as local smoke scratch and is not launch evidence. Generated root smoke JSON/TXT outputs remain ignored by the repo hygiene policy.

## Checks

| Check | Result |
| --- | --- |
| S13 status after root entrypoint restore and generated-scratch ignore | PASS; `M 3`, `D 15`, `?? 0` |
| restored root entrypoint status | PASS; no diff for `.pre-commit-config.yaml`, `AGENTS.md`, `CHANGELOG.md`, `Makefile`, `README.md`, `conftest.py`, `pytest.ini`, `docker-compose.dev.yml`, `docker-compose.smoke.yml`, `docker-compose.test.yml` |
| deleted root reference scan | PASS; no current references found for the remaining deleted helper filenames |
| `python -m py_compile sitecustomize.py shared/python/neft_shared/logging_setup.py shared/python/neft_shared/settings.py` | PASS |
| root host pytest sanity: `python -m pytest tests_host/test_sanity.py -q` | PASS; root `pytest.ini`/`conftest.py` are restored and loaded |
| full root host collect-only: `python -m pytest --collect-only -q` | PASS_WITH_SKIP; `tests_host/test_fuel_provider_replay_batch.py` import-skips when processing-core deps are absent in the host Python env |
| host targeted pytest with `PYTHONPATH=shared/python` for logging formatter | PASS; 1 test |
| core-api container targeted pytest for notification stub providers and shared logging | PASS; 6 tests |
| `git diff --check` scoped to S13 restored/modified files | PASS |

## Review Decision

S13 is reviewable as a root misc/generated owner slice.

Reviewable in S13:

- the three modified shared/bootstrap files, with the checks above
- generated/local scratch cleanup
- retired helper deletion candidates with explicit replacement entrypoints

No root project-entrypoint deletion remains to block final packaging. Final PR packaging still must stage S13 by explicit pathspecs and must not include ignored root scratch such as `accept`.
