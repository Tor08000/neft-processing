from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROCESSING_CORE_DIR = APP_DIR.parent
REPO_ROOT_DIR = PROCESSING_CORE_DIR.parent.parent
SHARED_PYTHON_DIR = REPO_ROOT_DIR / "shared" / "python"


if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

for path in (PROCESSING_CORE_DIR, SHARED_PYTHON_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.alembic.helpers import *  # noqa: F401,F403
from app.alembic.utils import *  # noqa: F401,F403
from app.alembic.utils import SCHEMA  # noqa: F401
