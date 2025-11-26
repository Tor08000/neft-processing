import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"

if SHARED_PATH.exists():
    sys.path.append(str(SHARED_PATH))
