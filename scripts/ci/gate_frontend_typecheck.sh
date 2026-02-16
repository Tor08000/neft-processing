#!/usr/bin/env bash
set -euo pipefail

portals=(
  "frontends/client-portal"
  "frontends/admin-ui"
  "frontends/partner-portal"
)

for portal in "${portals[@]}"; do
  echo "==> Frontend checks: ${portal}"
  pushd "$portal" >/dev/null
  npm ci
  npm run typecheck
  npm run lint
  popd >/dev/null
 done
