#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Dict


PROBE_QUERY = """
select json_build_object(
    'source', 'psql',
    'regclass', to_regclass('public._probe_migrations'),
    'fingerprint', json_build_object(
        'current_database', current_database(),
        'current_user', current_user,
        'inet_server_addr', inet_server_addr(),
        'inet_server_port', inet_server_port(),
        'pg_postmaster_start_time', pg_postmaster_start_time(),
        'version', version(),
        'data_directory', current_setting('data_directory')
    )
);
"""

ERROR_MESSAGE = "core-api and psql are not pointing at the same database instance"


def _run_command(args: list[str]) -> str:
    return subprocess.check_output(args, text=True).strip()


def _run_core_probe() -> Dict[str, Any]:
    output = _run_command(
        ["docker", "compose", "exec", "-T", "core-api", "python", "-m", "app.diagnostics.db_probe"]
    )
    return json.loads(output)


def _run_psql_probe() -> Dict[str, Any]:
    output = _run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "neft",
            "-d",
            "neft",
            "-tA",
            "-c",
            PROBE_QUERY,
        ]
    )
    return json.loads(output)


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    core_probe = _run_core_probe()
    psql_probe = _run_psql_probe()

    print("core-api probe:", json.dumps(core_probe, indent=2))
    print("psql probe:", json.dumps(psql_probe, indent=2))

    if core_probe.get("regclass") != psql_probe.get("regclass"):
        print("Probe table visibility differs between core-api and psql", file=sys.stderr)
        _fail(ERROR_MESSAGE)

    if core_probe.get("fingerprint") != psql_probe.get("fingerprint"):
        print("Database fingerprints differ between core-api and psql", file=sys.stderr)
        _fail(ERROR_MESSAGE)

    print("Databases are aligned and probe table is visible from both sides.")


if __name__ == "__main__":
    main()
