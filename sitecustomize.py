"""Container import-path bootstrap for NEFT services.

Python imports this module automatically when it is present on ``sys.path``.
The service Dockerfiles copy it into ``/app`` so containers keep a consistent
path layout for application code and the shared ``neft_shared`` package.
"""

from __future__ import annotations

import os
import sys


def _prepend(path: str) -> None:
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


for _path in (
    os.environ.get("NEFT_APP_PATH", "/app"),
    os.environ.get("NEFT_SHARED_PATH", "/opt/python"),
    os.environ.get("NEFT_WORKER_PATH", "/app/services/workers"),
):
    _prepend(_path)
