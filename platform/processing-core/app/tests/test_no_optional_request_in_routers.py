from __future__ import annotations

from pathlib import Path


ROUTERS_DIR = Path(__file__).resolve().parents[1] / "routers"
FORBIDDEN_PATTERNS = (
    "Request | None",
    "Optional[Request]",
    "Request = None",
)


def test_routers_do_not_use_optional_request_annotations() -> None:
    offenders: list[str] = []
    for file_path in sorted(ROUTERS_DIR.rglob("*.py")):
        text = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                offenders.append(f"{file_path.relative_to(ROUTERS_DIR)}: {pattern}")

    assert not offenders, "Forbidden Request optional patterns found:\n" + "\n".join(offenders)


def test_documents_routers_import_cleanly() -> None:
    __import__("app.routers.client_documents_v1")
    __import__("app.routers.admin_documents_v1")
