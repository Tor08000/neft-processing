from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT_DIR / "infra" / "minio-init.sh"


def _write_mc_stub(tmp_path: Path, *, fail_once: bool = False) -> Path:
    log_file = tmp_path / "mc.log"
    state_file = tmp_path / "mc_state"
    script = tmp_path / "mc"
    script.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'LOG_FILE="{log_file}"',
                f'STATE_FILE="{state_file}"',
                'if [ "$1" = "alias" ] && [ "$2" = "set" ] && [ "${MC_FAIL_ONCE:-0}" = "1" ]; then',
                '  if [ ! -f "$STATE_FILE" ]; then',
                '    echo "alias set fail" >>"$LOG_FILE"',
                '    touch "$STATE_FILE"',
                "    exit 1",
                "  fi",
                "fi",
                'echo "$@" >>"$LOG_FILE"',
            ]
        )
    )
    script.chmod(0o755)
    return script


def _run_script(tmp_path: Path, env: dict[str, str]) -> tuple[str, str]:
    process = subprocess.run(
        ["/bin/sh", str(SCRIPT_PATH)],
        cwd=ROOT_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    log_file = Path(env["MC_LOG_FILE"])
    log_contents = log_file.read_text() if log_file.exists() else ""
    return log_contents, process.stdout


def test_minio_init_creates_buckets_and_policies(tmp_path: Path) -> None:
    stub = _write_mc_stub(tmp_path)
    log_file = tmp_path / "mc.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{stub.parent}:{env.get('PATH', '')}",
            "MC_LOG_FILE": str(log_file),
            "MINIO_INIT_RETRIES": "2",
            "MINIO_INIT_RETRY_DELAY": "0",
            "NEFT_S3_BUCKET": "neft",
            "NEFT_S3_BUCKET_INVOICES": "neft-invoices",
            "NEFT_S3_BUCKET_PUBLIC": "0",
            "NEFT_S3_BUCKET_INVOICES_PUBLIC": "1",
            "MINIO_ROOT_USER": "neftminio",
            "MINIO_ROOT_PASSWORD": "neftminiosecret",
        }
    )

    log_contents, stdout = _run_script(tmp_path, env)

    assert "alias set local http://minio:9000 neftminio neftminiosecret" in log_contents
    assert "mb --ignore-existing local/neft" in log_contents
    assert "mb --ignore-existing local/neft-invoices" in log_contents
    assert "version enable local/neft" in log_contents
    assert "version enable local/neft-invoices" in log_contents
    assert "anonymous set none local/neft" in log_contents
    assert "anonymous set download local/neft-invoices" in log_contents
    assert "ls local" in log_contents
    assert "admin info local" in log_contents
    assert "init complete" in stdout


def test_minio_init_retries_on_alias_failure(tmp_path: Path) -> None:
    stub = _write_mc_stub(tmp_path, fail_once=True)
    log_file = tmp_path / "mc.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{stub.parent}:{env.get('PATH', '')}",
            "MC_LOG_FILE": str(log_file),
            "MC_FAIL_ONCE": "1",
            "MINIO_INIT_RETRIES": "3",
            "MINIO_INIT_RETRY_DELAY": "0",
            "NEFT_S3_BUCKET": "neft",
        }
    )

    log_contents, stdout = _run_script(tmp_path, env)

    assert "alias set fail" in log_contents
    assert log_contents.count("alias set local http://minio:9000 neftminio neftminiosecret") >= 1
    assert "init complete" in stdout
