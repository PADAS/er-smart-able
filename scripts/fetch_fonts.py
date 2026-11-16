"""Refresh the self-hosted Roboto files in web/static/fonts from Google Fonts.

Run: python scripts/fetch_fonts.py
"""
import re
import sys
import urllib.request
from pathlib import Path

FONTS = Path(__file__).resolve().parent.parent / "web" / "static" / "fonts"
CSS_URL = "https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap"
# a current Chrome, so the response names woff2 files with unicode-range
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BLOCK = re.compile(r"/\* latin \*/\s*@font-face\s*\{(?P<body>[^}]*)\}")
FACE = """@font-face {{
  font-family: Roboto;
  font-style: normal;
  font-weight: 400 700;
  font-display: optional;
  src: url(roboto.woff2) format("woff2");
  unicode-range: {unicode_range};
}}
"""


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main() -> int:
    css = fetch(CSS_URL).decode()
    match = BLOCK.search(css)
    if not match:
        print("no latin block in the response", file=sys.stderr)
        return 1
    body = match.group("body")
    url = re.search(r"url\(([^)]+)\)", body).group(1)
    unicode_range = re.search(r"unicode-range:\s*([^;]+);", body).group(1)
    FONTS.mkdir(parents=True, exist_ok=True)
    # Google serves one variable-font file for every weight, so it is stored once
    (FONTS / "roboto.woff2").write_bytes(fetch(url))
    (FONTS / "roboto.css").write_text(FACE.format(unicode_range=unicode_range))
    return 0


if __name__ == "__main__":
    sys.exit(main())
