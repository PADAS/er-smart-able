"""The in-app help: Markdown under web/help/, one section per file in
filename order, plus docs/smart-data-quirks.md from its one source. Rendered
once per process; the page shows the sections in a drawer and deep-links to
heading ids (a finding opens `finding-<code>`)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HELP_DIR = HERE / "help"
QUIRKS = ROOT / "docs" / "smart-data-quirks.md"
DOCS_URL = "https://github.com/PADAS/er-smart-able/blob/main/docs/"
sys.path.insert(0, str(ROOT / "browse"))
import build_quirks  # noqa: E402  the doc renders here exactly as in quirks.html
QUIRKS_PREAMBLE = ("This is the reference the extraction and the browser link to. It explains what SMART stores, "
                   "what the extraction does about it, and what the warnings in a bundle's manifest mean. "
                   "It is written for whoever has to answer \"why does this patrol look like that?\".\n\n")
EXTENSIONS = build_quirks.EXTENSIONS + ["attr_list"]   # attr_list for the help pages' own heading ids
_MD_LINK = re.compile(r'href="(?!https?://|#|/)([^"]+?\.md)(#[^"]*)?"')


def _links(html: str) -> str:
    """The drawer sits over a single-page app: a relative link to another doc
    would navigate away, so it points at the doc on GitHub, and every outside
    link opens in a new tab."""
    html = _MD_LINK.sub(lambda m: f'href="{DOCS_URL}{m.group(1)}{m.group(2) or ""}"', html)
    return html.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')


def _split_title(text: str) -> tuple[str, str]:
    """(title, body): the first heading is the title and is not repeated in the body."""
    m = re.match(r"\s*#\s+(.+?)\s*\n", text)
    return (m.group(1), text[m.end():]) if m else ("", text)


def _render(text: str, extensions=EXTENSIONS) -> tuple[str, str]:
    title, body = _split_title(text)
    return title, _links(build_quirks.convert(body, extensions).body)


def _load() -> list:
    out = []
    for f in sorted(HELP_DIR.glob("*.md")):
        title, html = _render(f.read_text(encoding="utf-8"))
        out.append({"id": re.sub(r"^\d+-", "", f.stem), "title": title, "html": html})
    if QUIRKS.is_file():
        title, body = _split_title(QUIRKS.read_text(encoding="utf-8"))
        _, html = _render(QUIRKS_PREAMBLE + body, build_quirks.EXTENSIONS)
        out.append({"id": "quirks", "title": title or "SMART data quirks", "html": html})
    return out


_cache: dict = {}


def _stamp() -> tuple:
    files = sorted(HELP_DIR.glob("*.md")) + ([QUIRKS] if QUIRKS.is_file() else [])
    return tuple((str(f), f.stat().st_mtime_ns) for f in files)


def sections() -> list:
    """Rendered once, and again when a source file changes (so an edit shows
    in development without a restart)."""
    stamp = _stamp()
    if _cache.get("stamp") != stamp:
        _cache.update(stamp=stamp, sections=_load())
    return _cache["sections"]
