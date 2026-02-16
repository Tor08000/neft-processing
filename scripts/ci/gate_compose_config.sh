#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.yml -f docker-compose.dev.yml config >/dev/null
