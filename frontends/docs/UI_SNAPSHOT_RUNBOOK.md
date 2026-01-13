# UI Snapshot Runbook

## Overview

This runbook describes how to capture automated UI screenshots for Admin, Client, and Partner frontends using Playwright. The snapshots are stored under `frontends/ui-audit/<YYYY-MM-DD_HHMM>/` and include a `REPORT.md` with routes, files, and errors.

## Prerequisites

- Gateway (or direct frontends) running locally.
- From `frontends/`, install Playwright dependencies:

```cmd
npm ci
npx playwright --version
```

## Quick Start (Windows CMD)

```cmd
cd C:\neft-processing\frontends
scripts\ui_snapshot.cmd
```

The script prints the output folder and full report path at the end, for example:

```
frontends\ui-audit\2025-01-31_1420
C:\neft-processing\frontends\ui-audit\2025-01-31_1420\REPORT.md
```

## Output Structure

```
frontends/ui-audit/<run>/
  admin/
    000_dashboard.png
    010_operations.png
    ...
  client/
    000_home.png
    010_cards.png
    ...
  partner/
    000_dashboard.png
    010_prices.png
    ...
  REPORT.md
```

## Link Crawl (Windows CMD)

```cmd
cd C:\neft-processing\frontends
scripts\ui_link_crawl.cmd
```

The script prints the full path to `LINK_REPORT.md`, for example:

```
C:\neft-processing\frontends\ui-audit\2025-01-31_1420\LINK_REPORT.md
```

## Environment Variables

### Base URLs

By default, snapshots run via the gateway:

- `E2E_BASE_URL` (default: `http://localhost`)
- Admin: `${E2E_BASE_URL}/admin/`
- Client: `${E2E_BASE_URL}/client/`
- Partner: `${E2E_BASE_URL}/partner/`

To run in direct mode, override per-app base URLs:

- `E2E_ADMIN_URL` (e.g. `http://localhost:4173/`)
- `E2E_CLIENT_URL` (e.g. `http://localhost:4174/`)
- `E2E_PARTNER_URL` (e.g. `http://localhost:4175/`)

### Credentials

Defaults are used unless overridden:

- `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- `CLIENT_EMAIL` / `CLIENT_PASSWORD`
- `PARTNER_EMAIL` / `PARTNER_PASSWORD`

### Visual Options

- `UI_SNAPSHOT_HEADLESS=0` to run headed.
- `UI_SNAPSHOT_VIEWPORT=1920x1080` to override viewport size.

## Manual Run (without script)

```cmd
cd C:\neft-processing\frontends
set UI_SNAPSHOT_RUN_ID=2025-01-31_1420
npx playwright test e2e/tests/ui_snapshot.spec.ts
```
