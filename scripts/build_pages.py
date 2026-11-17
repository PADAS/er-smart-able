#!/usr/bin/env python3
"""Build the getting-started site that GitHub Pages serves.

    python scripts/build_pages.py [--out _site]

The pages are web/guide/*.md (the getting-started guide) followed by web/help/*.md (the app's help
drawer, from the same files, so the two cannot drift). Each becomes one HTML page, rendered with the
app's Markdown configuration, in the shell web/site/page.html with web/site/site.css and the app's
tokens, font and lockup. Every link is relative, so the site works under any path and from disk.

The site is built once per language in web/static/locales/languages.json. English is the source and
keeps its addresses; each other language is a folder with the same page names. A translation sits
beside its English page in a folder named for the language (web/guide/fr/02-get-your-inputs.md); a
page with no translation is built from the English one. Stylesheets, fonts and pictures are
published once and shared.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE_DIR = ROOT / "web" / "guide"
HELP_DIR = ROOT / "web" / "help"
SITE_DIR = ROOT / "web" / "site"
STATIC_DIR = ROOT / "web" / "static"
LOCALES_DIR = STATIC_DIR / "locales"   # languages.json: the languages, in the order they are offered
WORDS_DIR = SITE_DIR / "locales"       # <code>.json: the words of the page shell in one language
SOURCE = "en"                          # the language the pages are written in; every other is a translation of it
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
    lang: str = SOURCE
    translated: bool = True   # False: no translation yet, so this is the English page in another language's shell


@dataclass
class Lang:
    code: str
    name: str        # in the language itself, as the switcher shows it
    reviewed: bool   # False: a machine wrote the translation and no fluent speaker has read it; the pages say so


def languages() -> list[Lang]:
    f = LOCALES_DIR / "languages.json"
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BuildError(f"{f}: the list of languages cannot be read ({e})")
    if not rows or rows[0].get("code") != SOURCE:
        raise BuildError(f"{f}: the first language must be {SOURCE}, the one the pages are written in")
    return [Lang(r["code"], r["name"], bool(r.get("reviewed"))) for r in rows]


_PLACE = re.compile(r"\{\{\w+\}\}")


def _read_words(code: str) -> dict:
    f = WORDS_DIR / f"{code}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BuildError(f"{f}: the page shell's words for {code} cannot be read ({e})")


def words(code: str) -> dict:
    """The page shell's words in one language: every key English has, with the same placeholders."""
    en = _read_words(SOURCE)
    if code == SOURCE:
        return en
    w, f = _read_words(code), WORDS_DIR / f"{code}.json"
    for k, v in en.items():
        if not str(w.get(k, "")).strip():
            raise BuildError(f"{f}: no words for '{k}'")
        if sorted(_PLACE.findall(w[k])) != sorted(_PLACE.findall(v)):
            raise BuildError(f"{f}: '{k}' must keep {' '.join(_PLACE.findall(v))}")
    return {k: w[k] for k in en}


def _check_translations(codes: list):
    """A folder beside the English pages is a language's translations: it must be a language the site
    has, and each file in it must translate an English page of the same name."""
    for folder in (GUIDE_DIR, HELP_DIR):
        for d in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != "img" and p.name[0] not in "._"):
            if d.name == SOURCE or d.name not in codes:
                raise BuildError(f"{d}: {d.name} is not a language in {LOCALES_DIR / 'languages.json'}")
            for f in sorted(d.glob("*.md")):
                if not (folder / f.name).is_file():
                    raise BuildError(f"{f}: no English page of the same name ({folder / f.name})")


def _sources(code: str = SOURCE) -> list[tuple[Path, str, str, bool]]:
    """(file, slug, group, translated) in page order; the first guide page is the site's index. The
    English files set the pages, their order and their names; another language supplies the file
    where it has one."""
    out = []
    for folder, group in ((GUIDE_DIR, "group_guide"), (HELP_DIR, "group_reference")):
        for f in sorted(folder.glob("*.md")):
            out.append((f, re.sub(r"^\d+-", "", f.stem), group))
    if out and out[0][2] == "group_guide":
        out[0] = (out[0][0], "index", out[0][2])
    seen = {}
    for f, slug, _ in out:   # one page per name: a second would overwrite the first
        if slug in seen:
            raise BuildError(f"{f} and {seen[slug]} would both be {slug}.html; rename one")
        seen[slug] = f
    full = []
    for f, slug, group in out:
        own = f.parent / code / f.name
        full.append((own, slug, group, True) if code != SOURCE and own.is_file() else (f, slug, group, code == SOURCE))
    return full


def _english(path: Path, code: str) -> Path:
    """The English source that a path under a language's folder stands for; any other path is itself."""
    for folder in (GUIDE_DIR, HELP_DIR):
        try:
            rel = path.relative_to(folder.resolve())
        except ValueError:
            continue
        if len(rel.parts) > 1 and rel.parts[0] == code:
            return folder.resolve().joinpath(*rel.parts[1:])
    return path


def _links(body: str, src: Path, slugs: dict, code: str = SOURCE) -> str:
    """A link to another page's source becomes that page; a link to any other file in the
    repository goes to GitHub; one that leads nowhere fails the build. Outside links open a new tab.
    In a translation, a link to a page's source in the same language leads to that page whether or
    not it is translated yet: every page exists in every language."""
    def local(m):
        target = _english((src.parent / m.group(1)).resolve(), code)
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


def _images(body: str, src: Path, root: str = "") -> tuple[str, dict]:
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
        return m.group(0).replace(f'src="{ref}"', f'src="{root}img/{target.name}"')
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


class _Shape(HTMLParser):
    """What a translation must keep of its English page: see _shape."""

    def __init__(self):
        super().__init__()
        self.lists, self.steps, self.notes, self.code, self.links = [], 0, 0, set(), []
        self._pre, self._code = 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("ol", "ul"):
            self.lists.append(tag)
        elif tag == "li" and self.lists and self.lists[-1] == "ol":
            self.steps += 1
        elif tag == "pre":
            self._pre += 1
        elif tag == "code" and not self._pre:
            self._code = ""
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].split("#")[0])
        if {"important", "unverified"} & set((a.get("class") or "").split()):
            self.notes += 1

    def handle_endtag(self, tag):
        if tag in ("ol", "ul") and self.lists:
            self.lists.pop()
        elif tag == "pre" and self._pre:
            self._pre -= 1
        elif tag == "code" and self._code is not None:
            self.code.add(self._code.strip())
            self._code = None

    def handle_data(self, data):
        if self._code is not None:
            self._code += data


def _shape(body: str, images: dict = None) -> dict:
    """The parts of a page a translation carries over unchanged: its tabs, pictures, numbered steps,
    set-apart notes, the text in code (file names, hosts, values) and where its links lead."""
    p = _Shape()
    p.feed(body)
    return {"tabs": body.count('<section class="tab-panel">'), "images": sorted(images or {}), "steps": p.steps,
            "notes": p.notes, "code": p.code, "links": sorted(h for h in p.links if h)}


def _same_shape(page: "Page", en: "Page"):
    """A translation that lost something its English page has fails the build, naming what."""
    mine, theirs = _shape(page.html, page.images), _shape(en.html, en.images)
    for key, name in (("tabs", "tabs"), ("steps", "numbered steps"), ("notes", "set-apart notes")):
        if mine[key] != theirs[key]:
            raise BuildError(f"{page.src}: {mine[key]} {name}, where the English page ({en.src.name}) has {theirs[key]}")
    if mine["images"] != theirs["images"]:
        raise BuildError(f"{page.src}: its pictures are {', '.join(mine['images']) or 'none'}, where the English page has {', '.join(theirs['images']) or 'none'}")
    lost = sorted(theirs["code"] - mine["code"])
    if lost:
        raise BuildError(f"{page.src}: the English page has `{lost[0]}` in code and the translation does not; names, hosts and code are carried over as they are")
    if mine["links"] != theirs["links"]:
        raise BuildError(f"{page.src}: its links lead to {', '.join(mine['links']) or 'nowhere'}, where the English page's lead to {', '.join(theirs['links']) or 'nowhere'}")


def _render(code: str) -> list[Page]:
    sources = _sources(code)
    slugs = {f.resolve(): slug for f, slug, _, _ in _sources(SOURCE)}
    root = "" if code == SOURCE else "../"   # another language's pages sit one folder down from the shared files
    out = []
    for f, slug, group, translated in sources:
        text = f.read_text(encoding="utf-8")
        m = _TITLE.match(text)
        if not m:
            raise BuildError(f"{f}: no title; a page starts with a '# ' heading")
        body = help_pages.build_quirks.convert(text[m.end():], help_pages.EXTENSIONS)[0]
        body, images = _images(_links(_tabs(body, f), f, slugs, code), f, root)
        out.append(Page(f, slug, m.group(1), group, body, images, code, translated))
    names = {}
    for p in out:   # one folder of pictures for the whole site: a name means one file
        for name, target in p.images.items():
            if names.setdefault(name, target) != target:
                raise BuildError(f"{target} and {names[name]} would both be img/{name}; rename one")
    return out


def pages(code: str = SOURCE) -> list[Page]:
    """The site's pages in one language, in order. Every English page is there: translated where the
    language has the file, and the English page otherwise."""
    _check_translations([l.code for l in languages()])
    en = _render(SOURCE)
    if code == SOURCE:
        return en
    out = _render(code)
    for p, e in zip(out, en):
        if p.translated:
            _same_shape(p, e)
    return out


def _text(s: str) -> str:
    return html.escape(s, quote=False)


def _nav(all_pages: list[Page], current: Page, w: dict) -> str:
    parts, group = [], None
    for p in all_pages:
        if p.group != group:
            if group is not None:
                parts.append("      </ul>")
            group = p.group
            parts.append(f"      <h2>{_text(w[group])}</h2>\n      <ul>")
        here = ' aria-current="page"' if p is current else ""
        parts.append(f'        <li><a href="{p.slug}.html"{here}>{html.escape(p.title)}</a></li>')
    if group is not None:
        parts.append("      </ul>")
    return "\n".join(parts)


def _prev_next(all_pages: list[Page], i: int, w: dict) -> str:
    out = ""
    if i > 0:
        p = all_pages[i - 1]
        out += f'<a class="prev" href="{p.slug}.html"><small>{_text(w["previous"])}</small>{html.escape(p.title)}</a>'
    if i < len(all_pages) - 1:
        p = all_pages[i + 1]
        out += f'<a class="next" href="{p.slug}.html"><small>{_text(w["next"])}</small>{html.escape(p.title)}</a>'
    return out


def _across(here: str, there: str, slug: str) -> str:
    """The relative address of a page in another language: English is at the top, the others one folder down."""
    if here == there:
        return f"{slug}.html"
    up = "" if here == SOURCE else "../"
    return f"{up}{slug}.html" if there == SOURCE else f"{up}{there}/{slug}.html"


def _switcher(langs: list[Lang], here: str, slug: str) -> str:
    return "".join(
        f'<a href="{_across(here, l.code, slug)}" lang="{l.code}" hreflang="{l.code}" data-lang="{l.code}"'
        f'{" aria-current=" + chr(34) + "true" + chr(34) if l.code == here else ""}>{_text(l.name)}</a>' for l in langs)


def _alternates(langs: list[Lang], here: str, slug: str) -> str:
    return "\n  ".join(f'<link rel="alternate" hreflang="{l.code}" href="{_across(here, l.code, slug)}">' for l in langs)


def _machine_note(lang: Lang, slug: str, w: dict) -> str:
    """Shown on every page of a language no fluent speaker has read through yet."""
    if lang.reviewed:
        return ""
    before, after = w["machine_translated"].split("{{english}}")
    link = f'<a href="{_across(lang.code, SOURCE, slug)}" hreflang="{SOURCE}">{_text(w["english_page"])}</a>'
    return f'<p class="note machine">{_text(before)}{link}{_text(after)}</p>'


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
    langs = languages()
    # before anything is removed: a source that cannot build, in any language, leaves the last site alone
    site = [(l, pages(l.code), words(l.code)) for l in langs]
    template = (SITE_DIR / "page.html").read_text(encoding="utf-8")
    _check_out(out)
    if out.exists():
        shutil.rmtree(out)
    static = out / "static"
    static.mkdir(parents=True)
    (out / MARK).write_text("Written by scripts/build_pages.py; a rebuild empties this folder.\n")
    shutil.copy(STATIC_DIR / "er-tokens.css", static)
    shutil.copy(SITE_DIR / "site.css", static)
    shutil.copy(SITE_DIR / "lang.js", static)
    shutil.copytree(STATIC_DIR / "fonts", static / "fonts")
    shutil.copytree(STATIC_DIR / "img", static / "img")
    for _, all_pages, _ in site:
        for p in all_pages:
            for name, target in p.images.items():
                (out / "img").mkdir(exist_ok=True)
                shutil.copy(target, out / "img" / name)
    github = '<a href="https://github.com/PADAS/er-smart-able">GitHub</a>'
    written = []
    for lang, all_pages, w in site:
        folder = out if lang.code == SOURCE else out / lang.code
        folder.mkdir(exist_ok=True)
        for i, p in enumerate(all_pages):
            body = p.html
            if not p.translated:   # the English page, in this language's shell, said to be English
                body = f'<p class="note">{_text(w["not_translated"])}</p>\n<div lang="{SOURCE}">\n{body}\n</div>'
            fill = {
                "lang": lang.code, "langs": " ".join(l.code for l in langs), "root": "" if lang.code == SOURCE else "../",
                "title": html.escape(p.title), "site_name": _text(w["site_name"]), "subtitle": _text(w["subtitle"]),
                "pages_label": html.escape(w["pages_label"]), "language_label": html.escape(w["language_label"]),
                "nav": _nav(all_pages, p, w), "alternates": _alternates(langs, lang.code, p.slug),
                "switcher": _switcher(langs, lang.code, p.slug), "note": _machine_note(lang, p.slug, w),
                "body": body, "prev_next": _prev_next(all_pages, i, w),
                "footer": _text(w["footer"]).replace("{{github}}", github),
            }
            page = re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)
            path = folder / f"{p.slug}.html"
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
    print(f"{len(written)} pages in {args.out}/, in {len(languages())} languages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
