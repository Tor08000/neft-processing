import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
paths = [
    ROOT / "services" / "auth-host",
    ROOT / "shared" / "python",
]
for path in paths:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
