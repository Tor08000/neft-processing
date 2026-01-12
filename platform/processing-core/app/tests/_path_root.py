from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path) -> Path:
    # Walk upwards and look for a repo marker
    for p in (start, *start.parents):
        if (p / "pyproject.toml").exists() or (p / "docker-compose.yml").exists() or (p / ".git").exists():
            return p
    # Container fallback (our services mount code into /app)
    if Path("/app").exists():
        return Path("/app")
    return start.parents[-1]
