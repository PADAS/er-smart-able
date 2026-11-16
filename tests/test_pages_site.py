"""The getting-started site (GitHub Pages): scripts/build_pages.py renders web/guide and the in-app
help to static pages. The build's structure and links, then the guide's content, then the workflow."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def site(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "build_pages", mod)   # the dataclass looks its module up while it is defined
    spec.loader.exec_module(mod)
    return mod


def tree(tmp_path, monkeypatch, mod, guide: dict, help: dict):
    """A stand-in repository under tmp_path: web/guide and web/help with the given files, and the
    two repository files the link tests point at."""
    root = tmp_path / "repo"
    for folder, files in (("guide", guide), ("help", help)):
        d = root / "web" / folder
        d.mkdir(parents=True)
        for name, text in files.items():
            (d / name).write_text(text, encoding="utf-8")
    (root / "docs").mkdir()
    (root / "README.md").write_text("# readme")
    (root / "docs" / "smart-data-quirks.md").write_text("# quirks")
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "GUIDE_DIR", root / "web" / "guide")
    monkeypatch.setattr(mod, "HELP_DIR", root / "web" / "help")


def test_the_real_site_builds_a_page_per_source_with_index_first(site, tmp_path):
    out = tmp_path / "_site"
    written = site.build(out)
    names = [p.name for p in written]
    assert names[0] == "index.html"
    assert {"overview.html", "sites.html", "loading.html", "statuses.html", "stops.html"} <= set(names)
    assert len(names) == len(list(site.GUIDE_DIR.glob("*.md"))) + len(list(site.HELP_DIR.glob("*.md")))
    for f in ("static/er-tokens.css", "static/site.css", "static/fonts/roboto.css", "static/fonts/roboto.woff2", "static/img/er-lockup-white-h-short.svg"):
        assert (out / f).is_file(), f


def test_each_page_has_its_title_nav_groups_current_mark_and_neighbours(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# Alpha\n\nx", "02-b.md": "# Beta\n\ny"}, {"01-c.md": "# Gamma\n\nz"})
    out = tmp_path / "o"; site.build(out)
    b = (out / "b.html").read_text()
    assert "<title>Beta · SMART migration</title>" in b and "<h1>Beta</h1>" in b
    assert "Get started" in b and "Reference" in b
    assert re.search(r'<a[^>]*href="b\.html"[^>]*aria-current="page"', b)
    assert not re.search(r'<a[^>]*href="index\.html"[^>]*aria-current', b)
    assert re.search(r'class="prev"[^>]*href="index\.html"|href="index\.html"[^>]*class="prev"', b)
    assert re.search(r'class="next"[^>]*href="c\.html"|href="c\.html"[^>]*class="next"', b)
    assert 'class="prev"' not in (out / "index.html").read_text() and 'class="next"' not in (out / "c.html").read_text()


def test_links_between_sources_become_pages_and_keep_their_anchor(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[s](../help/02-sites.md#which-user) [b](02-b.md) [h](#here)", "02-b.md": "# B\n\n[a](01-a.md)"},
         {"02-sites.md": "# Sites\n\nx"})
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    assert 'href="sites.html#which-user"' in a and 'href="b.html"' in a and 'href="#here"' in a
    assert 'href="index.html"' in (out / "b.html").read_text()


def test_a_link_to_another_repository_file_goes_to_github_and_outside_links_open_a_new_tab(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[r](../../README.md) [q](../../docs/smart-data-quirks.md#patrol-times) [e](https://earthranger.com)"}, {})
    out = tmp_path / "o"; site.build(out)
    a = (out / "index.html").read_text()
    assert 'href="https://github.com/PADAS/er-smart-able/blob/main/README.md"' in a
    assert 'href="https://github.com/PADAS/er-smart-able/blob/main/docs/smart-data-quirks.md#patrol-times"' in a
    assert re.search(r'<a target="_blank" rel="noopener"[^>]*href="https://earthranger\.com"', a)


def test_a_broken_relative_link_fails_the_build_naming_file_and_link(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A\n\n[x](nope.md)"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md.*nope\.md"):
        site.build(tmp_path / "o")


def test_a_source_without_a_title_fails_the_build_naming_the_file(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "no heading here"}, {})
    with pytest.raises(site.BuildError, match=r"01-a\.md"):
        site.build(tmp_path / "o")


def test_titles_are_escaped_everywhere(site, tmp_path, monkeypatch):
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A", "02-b.md": '# R&D <fast> "now"\n\nx'}, {})
    out = tmp_path / "o"; site.build(out)
    for name in ("index.html", "b.html"):
        h = (out / name).read_text()
        assert "<fast>" not in h and "R&amp;D &lt;fast&gt;" in h


def test_no_link_or_asset_is_root_relative_or_from_a_cdn(site, tmp_path):
    out = tmp_path / "_site"; site.build(out)
    for p in out.glob("*.html"):
        h = p.read_text()
        assert not re.search(r'(?:href|src)="/', h), p.name
        assert "fonts.googleapis.com" not in h and "gstatic.com" not in h and "cdn" not in h.lower(), p.name
        assert 'href="static/er-tokens.css"' in h and 'href="static/fonts/roboto.css"' in h and 'href="static/site.css"' in h
        assert "prefers-color-scheme" in h and "dataset.theme" in h, "the theme is set in the head"


def test_a_rebuild_leaves_no_stale_page(site, tmp_path, monkeypatch):
    out = tmp_path / "o"; out.mkdir(); (out / "gone.html").write_text("old")
    tree(tmp_path, monkeypatch, site, {"01-a.md": "# A"}, {})
    site.build(out)
    assert not (out / "gone.html").exists()


def test_the_reference_pages_carry_the_apps_own_rendering(site, tmp_path):
    import help_pages
    out = tmp_path / "_site"; site.build(out)
    bare = lambda h: re.sub(r"<a\b[^>]*>", "<a>", h)
    for s in help_pages.sections():
        if s["id"] == "quirks":
            continue
        assert bare(s["html"]).strip() in bare((out / f'{s["id"]}.html').read_text()), s["id"]


def test_the_site_stylesheet_takes_its_colours_from_tokens():
    css = (ROOT / "web" / "site" / "site.css").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert "var(--er-ui-" in css and ".unverified" in css and "max-width: 700px" in css
