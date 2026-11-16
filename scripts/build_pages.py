#!/usr/bin/env python3
"""Build the getting-started site that GitHub Pages serves.

    python scripts/build_pages.py [--out _site]

The pages are web/guide/*.md (the getting-started guide) followed by web/help/*.md (the app's help
drawer, from the same files, so the two cannot drift). Each becomes one HTML page, rendered with the
app's Markdown configuration, in the shell web/site/page.html with web/site/site.css and the app's
tokens, font and lockup. Every link is relative, so the site works under any path and from disk.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE_DIR = ROOT / "web" / "guide"
HELP_DIR = ROOT / "web" / "help"
SITE_DIR = ROOT / "web" / "site"
STATIC_DIR = ROOT / "web" / "static"
REPO_URL = "https://github.com/PADAS/er-smart-able/blob/main/"

sys.path.insert(0, str(ROOT / "web"))
import help_pages  # noqa: E402  the app's renderer and Markdown configuration; not changed here

_TITLE = re.compile(r"\s*#\s+(.+?)\s*(?:\n|$)")
_LOCAL = re.compile(r'href="(?!https?://|#|/|[a-z]+:)([^"#]+)(#[^"]*)?"')
_OUTSIDE = re.compile(r'<a\b([^>]*?)href="(https?://)')


class BuildError(Exception):
    """A source the site cannot be built from; the message names the file."""


@dataclass
class Page:
    src: Path
    slug: str
    title: str
    group: str
    html: str


def _sources() -> list[tuple[Path, str, str]]:
    """(file, slug, group) in page order; the first guide page is the site's index."""
    out = []
    for folder, group in ((GUIDE_DIR, "Get started"), (HELP_DIR, "Reference")):
        for f in sorted(folder.glob("*.md")):
            out.append((f, re.sub(r"^\d+-", "", f.stem), group))
    if out and out[0][2] == "Get started":
        out[0] = (out[0][0], "index", out[0][2])
    return out


def _links(body: str, src: Path, slugs: dict) -> str:
    """A link to another page's source becomes that page; a link to any other file in the
    repository goes to GitHub; one that leads nowhere fails the build. Outside links open a new tab."""
    def local(m):
        target = (src.parent / m.group(1)).resolve()
        anchor = m.group(2) or ""
        if target in slugs:
            return f'href="{slugs[target]}.html{anchor}"'
        try:
            rel = target.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            rel = None
        if rel is None or not target.exists():
            raise BuildError(f"{src}: the link to {m.group(1)} leads nowhere")
        return f'href="{REPO_URL}{rel}{anchor}"'
    body = _LOCAL.sub(local, body)
    return _OUTSIDE.sub(r'<a target="_blank" rel="noopener"\1href="\2', body)


def pages() -> list[Page]:
    sources = _sources()
    slugs = {f.resolve(): slug for f, slug, _ in sources}
    out = []
    for f, slug, group in sources:
        text = f.read_text(encoding="utf-8")
        m = _TITLE.match(text)
        if not m:
            raise BuildError(f"{f}: no title; a page starts with a '# ' heading")
        body = help_pages.build_quirks.convert(text[m.end():], help_pages.EXTENSIONS)[0]
        out.append(Page(f, slug, m.group(1), group, _links(body, f, slugs)))
    return out


def _nav(all_pages: list[Page], current: Page) -> str:
    parts, group = [], None
    for p in all_pages:
        if p.group != group:
            if group is not None:
                parts.append("      </ul>")
            group = p.group
            parts.append(f"      <h2>{html.escape(group)}</h2>\n      <ul>")
        here = ' aria-current="page"' if p is current else ""
        parts.append(f'        <li><a href="{p.slug}.html"{here}>{html.escape(p.title)}</a></li>')
    if group is not None:
        parts.append("      </ul>")
    return "\n".join(parts)


def _prev_next(all_pages: list[Page], i: int) -> str:
    out = ""
    if i > 0:
        p = all_pages[i - 1]
        out += f'<a class="prev" href="{p.slug}.html"><small>Previous</small>{html.escape(p.title)}</a>'
    if i < len(all_pages) - 1:
        p = all_pages[i + 1]
        out += f'<a class="next" href="{p.slug}.html"><small>Next</small>{html.escape(p.title)}</a>'
    return out


def build(out: Path) -> list[Path]:
    all_pages = pages()   # before anything is removed: a source that cannot build leaves the last site alone
    template = (SITE_DIR / "page.html").read_text(encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    static = out / "static"
    static.mkdir(parents=True)
    shutil.copy(STATIC_DIR / "er-tokens.css", static)
    shutil.copy(SITE_DIR / "site.css", static)
    shutil.copytree(STATIC_DIR / "fonts", static / "fonts")
    shutil.copytree(STATIC_DIR / "img", static / "img")
    written = []
    for i, p in enumerate(all_pages):
        fill = {"title": html.escape(p.title), "nav": _nav(all_pages, p), "body": p.html, "prev_next": _prev_next(all_pages, i)}
        page = re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)
        path = out / f"{p.slug}.html"
        path.write_text(page, encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="_site", help="the folder to write (emptied first); default _site")
    args = ap.parse_args()
    try:
        written = build(Path(args.out))
    except BuildError as e:
        print(f"build_pages: {e}", file=sys.stderr)
        return 1
    print(f"{len(written)} pages in {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
