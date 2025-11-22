from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
shared_path = root / "shared" / "python"
if shared_path.exists():
    sys.path.insert(0, str(shared_path))
