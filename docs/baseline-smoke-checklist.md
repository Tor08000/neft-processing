# Baseline smoke checklist

Use this checklist to validate the frozen baseline before/after client mode changes.

## Manual scenarios

- [ ] **Client login**: authenticate regular client user and open client dashboard.
- [ ] **Signup (new email)**: create a new account; confirm session is authenticated automatically.
- [ ] **Signup (existing email)**: submit existing email; confirm conflict is shown in-page and remains local.
- [ ] **Demo showcase**: login as demo client; confirm showcase dashboard renders.
- [ ] **Connect flow entry**: from authenticated client without completed onboarding, open `/connect` and continue to plan/type steps.
- [ ] **Partner login**: authenticate partner user and verify partner cabinet opens.

## Quick command checks (client portal)

Run these in addition to manual checks:

```bash
cd frontends/client-portal && npm run typecheck
cd frontends/client-portal && npm run build
```

## Suggested smoke helper usage

Use `scripts/smoke_client_portal_baseline.sh` for a consolidated command list covering:

- client login API check
- signup new email
- signup existing email
- demo showcase login
- partner login API check
