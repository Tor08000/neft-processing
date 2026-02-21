#!/usr/bin/env bash
set -euo pipefail

export AUTH_DB_RECOVERY=reset
export AUTH_ALEMBIC_AUTO_REPAIR=1

python -m app.scripts.db_repair
