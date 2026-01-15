import re
import sys
from pathlib import Path


def pick_asset(paths: list[str]) -> str | None:
    if not paths:
        return None
    for path in paths:
        if "assets" in path.lower():
            return path
    return paths[0]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_assets.py <html_file>", file=sys.stderr)
        return 2

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"File not found: {html_path}", file=sys.stderr)
        return 2

    content = html_path.read_text(encoding="utf-8", errors="ignore")
    css_candidates = re.findall(r'(?:href|src)=["\']([^"\']+?\.css[^"\']*)["\']', content, re.IGNORECASE)
    js_candidates = re.findall(r'(?:href|src)=["\']([^"\']+?\.js[^"\']*)["\']', content, re.IGNORECASE)

    css_asset = pick_asset(css_candidates)
    js_asset = pick_asset(js_candidates)

    if not css_asset or not js_asset:
        print("Failed to locate assets in HTML output.", file=sys.stderr)
        return 1

    print(f"css={css_asset}")
    print(f"js={js_asset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
