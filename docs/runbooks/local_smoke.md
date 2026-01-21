# Local smoke checklist (Client/Admin portals)

## Required environment

- Docker Desktop / Docker Engine running
- `curl` and Python available on PATH

## One-command smoke

Run the full smoke/regression script:

```cmd
scripts\verify_all.cmd
```

The script will:

- Build and start the stack
- Validate client/admin base paths in built `index.html`
- Verify gateway asset routing and MIME types
- Log in as admin/client and validate `/api/auth/v1/auth/me`
- Validate `/api/core/portal/me` and `/api/core/legal/required`
- Auto-accept legal docs when required

## Targeted gateway asset smoke

```cmd
scripts\smoke_gateway_assets.cmd
```

This script resolves asset filenames from `/admin/` and `/client/` index pages and checks:

- `Content-Type` is JavaScript/CSS (not `text/html`)
- Response status is `200`
- HTML is never returned for asset URLs
