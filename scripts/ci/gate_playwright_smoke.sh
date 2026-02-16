#!/usr/bin/env bash
set -euo pipefail

pushd frontends/e2e >/dev/null
npm ci
npx playwright install --with-deps
npx playwright test --config playwright.e2e.config.ts --grep '@smoke'
popd >/dev/null
