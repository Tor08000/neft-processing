from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

MARKER_PREFIXES = ("<<<<<<<", ">>>>>>>")
MARKER_LINE = "======="


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, capture_output=True
    )
    raw_paths = result.stdout.decode().split("\0")
    return [
        REPO_ROOT / path
        for path in raw_paths
        if path and (REPO_ROOT / path).is_file()
    ]


def _is_probably_text(path: Path, content: bytes) -> bool:
    if b"\0" in content:
        return False

    text_extensions = {
        ".cfg",
        ".conf",
        ".env",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".yml",
        ".yaml",
        ".md",
        ".txt",
        ".sh",
        ".ini",
        ".toml",
        ".sql",
        ".mako",
    }
    text_filenames = {"Dockerfile", "Makefile", ".gitignore", ".dockerignore"}

    return path.suffix in text_extensions or path.name in text_filenames or not path.suffix


def test_repository_has_no_merge_conflict_markers() -> None:
    offenders: list[str] = []

    for path in _tracked_files():
        content_bytes = path.read_bytes()
        if not _is_probably_text(path, content_bytes):
            continue

        for lineno, line in enumerate(content_bytes.decode(errors="ignore").splitlines(), 1):
            if line.startswith(MARKER_PREFIXES) or line.strip() == MARKER_LINE:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")

    assert not offenders, (
        "Found merge conflict markers in tracked files:\n" + "\n".join(sorted(offenders))
    )
