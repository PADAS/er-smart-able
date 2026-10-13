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
