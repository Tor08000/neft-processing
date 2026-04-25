from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.tests._path_helpers import find_repo_root


def test_legal_integrations_task_import_survives_client_documents_preimport() -> None:
    repo_root = find_repo_root(Path(__file__).resolve())
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(repo_root / "platform" / "processing-core"),
            str(repo_root / "shared" / "python"),
        ]
    )
    env["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

    script = """
import app.routers.client_documents
import app.routers.client_documents_v1
import app.tasks.legal_integrations
import app.main
print("bootstrap-ok")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "bootstrap-ok" in result.stdout
