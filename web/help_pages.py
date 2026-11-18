"""The in-app help: Markdown under web/help/, one section per file in
filename order, plus docs/smart-data-quirks.md from its one source. Rendered
once per process; the page shows the sections in a drawer and deep-links to
heading ids (a finding opens `finding-<code>`)."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HELP_DIR = HERE / "help"
QUIRKS = ROOT / "docs" / "smart-data-quirks.md"
DOCS_URL = "https://github.com/PADAS/er-smart-able/blob/main/docs/"


def _load_module(path: Path):
    """browse/build_quirks.py, once per process, without putting browse/ on sys.path."""
    if path.stem in sys.modules:
        return sys.modules[path.stem]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


build_quirks = _load_module(ROOT / "browse" / "build_quirks.py")   # the doc renders here exactly as in quirks.html
QUIRKS_PREAMBLE = ("This is the reference the extraction and the browser link to. It explains what SMART stores, "
                   "what the extraction does about it, and what the warnings in a bundle's manifest mean. "
                   "It is written for whoever has to answer \"why does this patrol look like that?\".\n\n")
# the help pages carry their own heading ids (attr_list) and get no toc, which would slugify every
# heading into the page's single DOM ("## Import" -> id="import") beside the app's and the doc's ids
EXTENSIONS = ["attr_list", "tables", "fenced_code"]
REPO_URL = "https://github.com/PADAS/er-smart-able/blob/main/"
_MD_LINK = re.compile(r'href="(?!https?://|#|/|[a-z]+:)([^"]+?\.md)(#[^"]*)?"')
_OUTSIDE = re.compile(r'<a\b([^>]*?)href="(https?://)')
_ANCHOR = re.compile(r'href="#([^"]+)"')


def _links(html: str, src_dir: Path, id_prefix: str = "") -> str:
    """The drawer sits over a single-page app: a relative link to another doc
    would navigate away, so it points at that file in the repository on
    GitHub, resolved from the page it is written in; every outside link opens
    in a new tab; an in-page anchor follows the section's id prefix."""
    def repo(m):
        target = (src_dir / m.group(1)).resolve()
        try:
            rel = target.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            rel = m.group(1)
        return f'href="{REPO_URL}{rel}{m.group(2) or ""}"'
    html = _MD_LINK.sub(repo, html)
    if id_prefix:
        html = _ANCHOR.sub(lambda m: f'href="#{id_prefix}{m.group(1)}"', html)
    return _OUTSIDE.sub(r'<a target="_blank" rel="noopener"\1href="\2', html)


def _split_title(text: str) -> tuple[str, str]:
    """(title, body): the first heading is the title and is not repeated in the body."""
    m = re.match(r"\s*#\s+(.+?)\s*\n", text)
    return (m.group(1), text[m.end():]) if m else ("", text)


def _render(text: str, src: Path, extensions=EXTENSIONS, id_prefix: str = "") -> tuple[str, str]:
    title, body = _split_title(text)
    return title, _links(build_quirks.convert(body, extensions, id_prefix)[0], src.parent, id_prefix)


def _page_files(lang: str) -> list:
    """(id, file, language) for each help page: the lang's own file when it exists, else the English one."""
    out = []
    for f in sorted(HELP_DIR.glob("*.md")):
        own = HELP_DIR / lang / f.name
        use_own = lang != "en" and own.is_file()
        out.append((re.sub(r"^\d+-", "", f.stem), own if use_own else f, lang if use_own else "en"))
    return out


def _load(lang: str = "en") -> list:
    out = []
    for page_id, f, page_lang in _page_files(lang):
        title, html = _render(f.read_text(encoding="utf-8"), f)
        out.append({"id": page_id, "title": title, "html": html, "lang": page_lang})
    if QUIRKS.is_file():
        title, body = _split_title(QUIRKS.read_text(encoding="utf-8"))
        # the doc's heading ids are prefixed so they cannot collide with the app's own ids
        _, html = _render(QUIRKS_PREAMBLE + body, QUIRKS, build_quirks.EXTENSIONS, id_prefix="quirks-")
        out.append({"id": "quirks", "title": title or "SMART data quirks", "html": html, "lang": "en"})   # the reference is English only
    return out


_cache: dict = {}   # lang -> {"stamp", "sections"}


def _stamp(lang: str) -> tuple:
    files = [f for _, f, _ in _page_files(lang)] + ([QUIRKS] if QUIRKS.is_file() else [])
    return tuple((str(f), f.stat().st_mtime_ns) for f in files)


def sections(lang: str = "en") -> list:
    """Rendered once per language, and again when one of its source files changes (so an edit shows
    in development without a restart). `lang` must be a known language code: it names a folder."""
    stamp = _stamp(lang)
    entry = _cache.get(lang)
    if not entry or entry["stamp"] != stamp:
        entry = _cache[lang] = {"stamp": stamp, "sections": _load(lang)}
    return entry["sections"]
