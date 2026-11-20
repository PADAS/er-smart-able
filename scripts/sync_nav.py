#!/usr/bin/env python3
"""Write the app's sidebar into the data browser.

The browser (browse/index.html) is one self-contained document that also opens
from a local folder, so it cannot load web/static/nav.js and nav.css as files.
It carries a copy of each between markers; this script writes the copies, and
`--check` exits 1 when they differ (tests/test_viewer_page.py runs it).

Usage: sync_nav.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROWSER = ROOT / "browse" / "index.html"
FILES = ("nav.css", "nav.js")


def synced(html: str) -> str:
    for name in FILES:
        begin, end = f"/* {name}:begin */", f"/* {name}:end */"
        if html.count(begin) != 1 or html.count(end) != 1:
            raise SystemExit(f"{BROWSER}: expected one '{begin}' and one '{end}'")
        head, rest = html.split(begin, 1)
        _, tail = rest.split(end, 1)
        src = (ROOT / "web" / "static" / name).read_text(encoding="utf-8").strip()
        html = f"{head}{begin}\n{src}\n{end}{tail}"
    return html


def main(argv: list[str]) -> int:
    now = BROWSER.read_text(encoding="utf-8")
    want = synced(now)
    if "--check" in argv:
        if now != want:
            print(f"{BROWSER.relative_to(ROOT)} does not carry the current web/static/nav.js and nav.css: run scripts/sync_nav.py")
            return 1
        return 0
    if now != want:
        BROWSER.write_text(want, encoding="utf-8")
        print(f"updated {BROWSER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
