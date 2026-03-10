# Current working baseline (client portal)

This document freezes the expected **working baseline** for `frontends/client-portal` before introducing additional product logic.

## Expected working behavior

1. **Demo client login works**
   - Login with demo client credentials enters client portal successfully.
2. **Demo showcase dashboard works**
   - Demo user reaches dashboard showcase content and can navigate core showcase routes.
3. **New signup works**
   - Signup with a fresh email completes and lands user in authenticated flow.
4. **Signup conflict stays local**
   - Signup with an existing email returns a local validation/conflict error in UI (no fatal app crash/redirect loop).
5. **Signup auto-authenticates**
   - Successful signup creates authenticated session without manual re-login.
6. **Connect flow entry works**
   - New authenticated client can enter `/connect` flow and proceed to next onboarding steps.
7. **Partner login works**
   - Partner credentials can authenticate and open partner portal flow.

## Scope of this baseline freeze

- Client portal shell and onboarding entry behavior.
- Login/signup happy-path and known local conflict behavior.
- Demo showcase access and partner authentication regression checks.

This baseline should be validated before and after mode-related changes.
