from pathlib import Path
import re


def test_no_fragile_parents_indexing() -> None:
    tests_dir = Path(__file__).resolve().parent
    offenders = []
    fragile_pattern = re.compile(r"\.parents\[(?:4|5)\]")
    for path in tests_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if fragile_pattern.search(text):
            offenders.append(str(path))
    assert not offenders, "Fragile parents indexing found: " + ", ".join(offenders)
