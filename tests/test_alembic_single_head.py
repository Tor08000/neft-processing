from __future__ import annotations

import shutil
import subprocess

import pytest


def _run_alembic_heads() -> tuple[int, str]:
    if not shutil.which("docker"):
        pytest.skip("docker not available")

    command = [
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
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError:
        pytest.skip("docker not available")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        docker_errors = (
            "Cannot connect to the Docker daemon",
            "docker: not found",
            "compose: not found",
            "No such file or directory",
        )
        if any(error in stderr for error in docker_errors):
            pytest.skip("docker not available")
        pytest.fail(f"Failed to run alembic heads:\n{result.stdout}\n{stderr}")

    stdout = result.stdout.strip()
    return _count_heads(stdout), stdout


def _count_heads(stdout: str) -> int:
    lines = [line for line in stdout.splitlines() if line.strip()]
    head_lines = [line for line in lines if "(head)" in line]
    return len(head_lines) if head_lines else len(lines)


@pytest.mark.smoke
def test_alembic_single_head() -> None:
    heads_count, stdout = _run_alembic_heads()
    if heads_count != 1:
        pytest.fail(f"Expected exactly one alembic head, got {heads_count}:\n{stdout}")
