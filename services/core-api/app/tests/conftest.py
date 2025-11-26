import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"

if SHARED_PATH.exists():
    sys.path.append(str(SHARED_PATH))

# Use in-memory SQLite for tests to avoid coupling to external Postgres.
os.environ.setdefault("NEFT_DB_URL", "sqlite+pysqlite:///:memory:")
