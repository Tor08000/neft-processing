from pathlib import Path


def test_no_fragile_parents_indexing() -> None:
    tests_dir = Path(__file__).resolve().parent
    offenders = []
    for path in tests_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ".parents[4]" in text or ".parents[5]" in text:
            offenders.append(str(path))
    assert not offenders, "Fragile parents indexing found: " + ", ".join(offenders)
