from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_API_ROOT = REPO_ROOT / "platform" / "processing-core"
ALEMBIC_CONFIG = CORE_API_ROOT / "app" / "alembic.ini"
DEFAULT_DB_URL = "postgresql+psycopg://neft:neft@postgres:5432/neft"


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", DEFAULT_DB_URL)

    pythonpath_parts = [str(CORE_API_ROOT), str(REPO_ROOT / "shared" / "python")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _collect_head_lines(output: str) -> list[str]:
    heads: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "(head)" not in line:
            continue
        heads.append(line)
    return heads


def _run_local_heads() -> subprocess.CompletedProcess[str] | None:
    env = _build_env()
    try:
        return subprocess.run(
            ["alembic", "-c", str(ALEMBIC_CONFIG), "heads"],
            cwd=CORE_API_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None


def _run_docker_compose_heads() -> subprocess.CompletedProcess[str] | None:
    if not shutil.which("docker"):
        return None

    try:
        return subprocess.run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--entrypoint",
                "",
                "core-api",
                "sh",
                "-lc",
                "alembic -c app/alembic.ini heads",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None


@pytest.mark.smoke
def test_core_api_alembic_has_single_head() -> None:
    if not ALEMBIC_CONFIG.exists():
        pytest.skip("core-api Alembic config is missing")

    result = _run_local_heads()
    if result is None:
        result = _run_docker_compose_heads()

    if result is None:
        pytest.skip("Alembic CLI is unavailable and Docker is not installed")

    if result.returncode != 0:
        pytest.fail(
            "alembic heads failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    head_lines = _collect_head_lines(result.stdout)
    assert head_lines, f"No Alembic heads detected in output:\n{result.stdout}"

    if len(head_lines) != 1:
        pytest.fail(
            "Expected a single Alembic head for core-api, "
            f"but found {len(head_lines)}:\n" + "\n".join(head_lines)
        )
