from __future__ import annotations

import ast
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parent / "versions"


def _load_revision(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "revision":
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def main() -> None:
    revisions: dict[str, list[Path]] = {}
    missing: list[Path] = []

    for path in sorted(VERSIONS_DIR.glob("*.py")):
        revision = _load_revision(path)
        if revision is None:
            missing.append(path)
            continue
        revisions.setdefault(revision, []).append(path)

    errors: list[str] = []
    if missing:
        errors.append("Missing revision identifiers:")
        errors.extend(f"  - {path}" for path in missing)

    duplicates = {revision: paths for revision, paths in revisions.items() if len(paths) > 1}
    if duplicates:
        errors.append("Duplicate revision identifiers detected:")
        for revision, paths in sorted(duplicates.items()):
            joined = ", ".join(str(path) for path in paths)
            errors.append(f"  - {revision}: {joined}")

    if errors:
        raise SystemExit("\n".join(errors))

    print("Alembic revisions are unique.")


if __name__ == "__main__":
    main()
