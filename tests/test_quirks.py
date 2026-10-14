from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
ANCHORS = {"timezones", "patrol-times", "tracks", "waypoints-and-legs", "labels-and-languages", "observation-values",
           "data-model-export", "configurable-models", "patrol-metadata", "staff-and-credentials", "attachments",
           "backups-versus-exports", "profiles"}


def test_render_has_every_anchor():
    from browse.build_quirks import render
    html = render((ROOT / "docs" / "smart-data-quirks.md").read_text())
    for a in ANCHORS:
        assert f'id="{a}"' in html, a
    assert "<nav" in html and "quirks" in html.lower()


def test_links_in_app_and_runbook_resolve():
    linked = set()
    for f in (ROOT / "browse" / "index.html", ROOT / "RUNBOOK.md", ROOT / "README.md", ROOT / "export" / "__main__.py"):
        linked |= set(re.findall(r"quirks\.html#([a-z0-9-]+)", f.read_text()))
    assert linked <= ANCHORS, linked - ANCHORS
    assert {"timezones", "patrol-times", "tracks", "labels-and-languages", "data-model-export"} <= linked


def test_quirks_page_wears_the_app_theme():
    """The docs page reuses the browser's design tokens (read from
    browse/index.html at build time, so the two cannot drift), its fonts,
    its dark mode and its teal header with the acorn mark."""
    from browse.build_quirks import render
    app = (ROOT / "browse" / "index.html").read_text()
    html = render("# Title\n\n## Section\n\ntext")
    brand = re.search(r"--brand:\s*(#[0-9a-f]+)", app).group(1)
    assert f"--brand: {brand}" in html
    assert "prefers-color-scheme: dark" in html
    assert "fonts.googleapis.com/css2?family=Roboto" in html
    assert 'class="acorn"' in html and "<header" in html


def test_docs_links_in_the_browser_are_marked():
    """Every link to the docs page gets the info-icon treatment from one CSS
    rule keyed on the href, and the icon font loads the filled variant."""
    app = (ROOT / "browse" / "index.html").read_text()
    assert re.search(r'a\[href\^="quirks\.html"\]::before\s*\{[^}]*content:\s*"info"', app)
    assert "FILL,GRAD@20..24,400,0..1,0" in app
    # the old icon-only link would now show two icons
    assert '<span class="mi" aria-hidden="true">info</span></a>' not in app
