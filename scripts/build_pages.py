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

_TITLE = re.compile(r"\s*#[ \t]+(\S.*?)[ \t]*(?:\n|$)")   # one line: a bare "#" does not take the next line
_LOCAL = re.compile(r'href="(?!https?://|#|/|[a-z]+:)([^"#]+)(#[^"]*)?"')
_OUTSIDE = re.compile(r'<a\b([^>]*?)href="(https?://)')
_IMG = re.compile(r'<img\b[^>]*>')
_ATTR = re.compile(r'\b(src|alt)="([^"]*)"')
_TAB = re.compile(r'<h3 class="tab">(.*?)</h3>(.*?)(?=<h[1-3]\b|\Z)', re.S)   # a tab's section ends at the next heading


class BuildError(Exception):
    """A source the site cannot be built from; the message names the file."""


@dataclass
class Page:
    src: Path
    slug: str
    title: str
    group: str
    html: str
    images: dict   # published name -> source file, for every picture the page shows


def _sources() -> list[tuple[Path, str, str]]:
    """(file, slug, group) in page order; the first guide page is the site's index."""
    out = []
    for folder, group in ((GUIDE_DIR, "Get started"), (HELP_DIR, "Reference")):
        for f in sorted(folder.glob("*.md")):
            out.append((f, re.sub(r"^\d+-", "", f.stem), group))
    if out and out[0][2] == "Get started":
        out[0] = (out[0][0], "index", out[0][2])
    seen = {}
    for f, slug, _ in out:   # one page per name: a second would overwrite the first
        if slug in seen:
            raise BuildError(f"{f} and {seen[slug]} would both be {slug}.html; rename one")
        seen[slug] = f
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


def _images(body: str, src: Path) -> tuple[str, dict]:
    """A picture beside its page's source (a screenshot under img/) is published as img/<name>: the
    file must exist, and must say what it shows (alt text), for a reader who cannot see it."""
    found = {}

    def one(m):
        attrs = dict(_ATTR.findall(m.group(0)))
        ref = attrs.get("src", "")
        if re.match(r"https?://|data:|/", ref):
            raise BuildError(f"{src}: the image {ref} is not a file beside the page; the site loads nothing from elsewhere")
        target = (src.parent / ref).resolve()
        if not target.is_file():
            raise BuildError(f"{src}: the image {ref} does not exist")
        if not attrs.get("alt", "").strip():
            raise BuildError(f"{src}: the image {ref} has no alt text; write what it shows in the square brackets")
        found[target.name] = target
        return m.group(0).replace(f'src="{ref}"', f'src="img/{target.name}"')
    return _IMG.sub(one, body), found


def _tabs(body: str, src: Path) -> str:
    """Headings marked as tabs ('### Name {: .tab }'), one after another, are alternatives: the reader
    picks one and sees only its section, which runs to the next heading. The tabs are radio buttons
    and their labels, so they work from the keyboard and without a script; site.css shows the panel
    of the checked one. Each panel keeps its heading for a reader with no stylesheet, or on paper."""
    found = list(_TAB.finditer(body))
    out, at, n = [], 0, 0
    while found:
        group = [found.pop(0)]
        while found and found[0].start() == group[-1].end():
            group.append(found.pop(0))
        if len(group) < 2:
            raise BuildError(f"{src}: the tab '{group[0].group(1)}' stands alone; tabs are a choice of two or more")
        n += 1
        picks = "".join(
            f'<input type="radio" name="tabs-{n}" id="tabs-{n}-{i}"{" checked" if i == 1 else ""}>'
            f'<label for="tabs-{n}-{i}">{m.group(1)}</label>\n' for i, m in enumerate(group, 1))
        panels = "".join(f'<section class="tab-panel">\n<h3>{m.group(1)}</h3>{m.group(2)}</section>\n' for m in group)
        out.append(body[at:group[0].start()] + f'<div class="tabs">\n{picks}{panels}</div>\n')
        at = group[-1].end()
    return "".join(out) + body[at:]


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
        body, images = _images(_links(_tabs(body, f), f, slugs), f)
        out.append(Page(f, slug, m.group(1), group, body, images))
    names = {}
    for p in out:   # one folder of pictures for the whole site: a name means one file
        for name, target in p.images.items():
            if names.setdefault(name, target) != target:
                raise BuildError(f"{target} and {names[name]} would both be img/{name}; rename one")
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


MARK = ".build_pages"   # in every folder this script writes, so a rebuild may empty it and nothing else


def _check_out(out: Path):
    """The output folder is emptied before each build, so refuse any folder this script did not write:
    the repository, a folder that holds the sources, or one with anything in it and no MARK."""
    o = out.resolve()
    for keep in (ROOT, GUIDE_DIR, HELP_DIR, SITE_DIR, STATIC_DIR):
        k = keep.resolve()
        if o == k or o in k.parents:
            raise BuildError(f"{out}: refusing to empty it; it holds {keep}. Choose another --out, such as _site")
    if o.exists() and any(o.iterdir()) and not (o / MARK).exists():
        raise BuildError(f"{out}: refusing to empty it; it is not empty and was not written by this script")


def build(out: Path) -> list[Path]:
    all_pages = pages()   # before anything is removed: a source that cannot build leaves the last site alone
    template = (SITE_DIR / "page.html").read_text(encoding="utf-8")
    _check_out(out)
    if out.exists():
        shutil.rmtree(out)
    static = out / "static"
    static.mkdir(parents=True)
    (out / MARK).write_text("Written by scripts/build_pages.py; a rebuild empties this folder.\n")
    shutil.copy(STATIC_DIR / "er-tokens.css", static)
    shutil.copy(SITE_DIR / "site.css", static)
    shutil.copytree(STATIC_DIR / "fonts", static / "fonts")
    shutil.copytree(STATIC_DIR / "img", static / "img")
    for p in all_pages:
        for name, target in p.images.items():
            (out / "img").mkdir(exist_ok=True)
            shutil.copy(target, out / "img" / name)
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
