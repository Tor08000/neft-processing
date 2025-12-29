# CI merge gate requirements

## Required checks for `main`

Enable branch protection rules for `main` with the following required status checks:

- `db-smoke` (workflow: **CI Smoke**)
- `smoke-scenarios` (workflow: **CI Smoke**)

These checks guarantee:

- Alembic migrations are idempotent (repeat `upgrade head`).
- End-to-end smoke scenarios for fuel and billing flows pass on a clean database.

## GitHub settings checklist

1. Go to **Settings → Branches → Branch protection rules**.
2. Edit (or create) the rule for `main`.
3. Under **Require status checks to pass before merging**:
   - Add `db-smoke`
   - Add `smoke-scenarios`
4. Save the rule.
