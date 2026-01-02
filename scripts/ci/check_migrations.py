from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _git_diff(base_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    base_ref = os.getenv("CI_MERGE_BASE") or os.getenv("GITHUB_BASE_REF")
    if base_ref:
        if "/" not in base_ref and not base_ref.startswith("refs/"):
            base_ref = f"origin/{base_ref}"
    else:
        result = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            check=False,
            capture_output=True,
            text=True,
        )
        base_ref = result.stdout.strip() or "HEAD~1"

    changed_files = _git_diff(base_ref)
    if not changed_files:
        print("No changes detected.")
        return 0

    models_changed = any(
        Path(path).match("platform/processing-core/app/models/*.py") for path in changed_files
    )
    migrations_changed = any(
        Path(path).match("platform/processing-core/app/alembic/versions/*.py") for path in changed_files
    )

    if models_changed and not migrations_changed:
        print("Detected model changes without alembic migrations.")
        return 1

    print("Migration discipline check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
