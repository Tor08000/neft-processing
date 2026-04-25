from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for current in (start, *start.parents):
        if (current / "docker-compose.yml").exists():
            return current
        if (current / ".git").exists():
            return current
        if (current / "platform").is_dir() and (current / "shared").is_dir():
            return current
    return start.parent
