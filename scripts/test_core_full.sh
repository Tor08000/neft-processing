#!/usr/bin/env bash
set -euo pipefail

DOCKER_COMPOSE=${DOCKER_COMPOSE:-"docker compose"}

${DOCKER_COMPOSE} up -d postgres redis minio minio-health minio-init
${DOCKER_COMPOSE} run --rm core-api pytest -q app/tests/system app/tests/smoke app/tests/contracts app/tests/integration -vv -s
