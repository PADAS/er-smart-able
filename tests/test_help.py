"""The in-app help: every section the drawer lists, an entry for every
finding a load can stop on, and the quirks doc included from its one
source."""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# the preflight codes are er-smart-sync's (src/er_smart_sync/preflight.py, every Finding.of); the
# checklist and job codes come from web/findings.py below
PREFLIGHT_CODES = ["timezone", "language", "time_coverage", "check_failed", "feature_flag", "permissions", "patrol_types",
                   "segment_schema", "choices", "subjects", "inactive_members", "teams", "event_types", "collection_type",
                   "leg_span", "bundle_warnings"]


@pytest.fixture
def help_mod(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("help_pages", None)
    return importlib.import_module("help_pages")


def _er_smart_sync_source(name: str):
    """er-smart-sync's module source when it can be found: the installed package,
    the sibling checkout, or the load venv. The help must name every code it emits."""
    try:
        mod = importlib.import_module(f"er_smart_sync.{name}")
        return Path(mod.__file__).read_text()
    except ImportError:
        pass
    siblings = [a / "earthranger-smart-utils" / "src" / "er_smart_sync" / f"{name}.py" for a in ROOT.parents[:4]]
    for p in [*siblings, *ROOT.glob(f".venv-load/lib/python*/site-packages/er_smart_sync/{name}.py")]:
        if p.is_file():
            return p.read_text()
    return None


def _finding_codes(monkeypatch):
    """The codes smart-able itself puts on a load, plus the listed er-smart-sync ones."""
    import re
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("findings", None)
    findings = importlib.import_module("findings")
    checklist = set(findings.BLOCKING_CHECKLIST) | set(findings.VALUE_LABEL) | {"patrol_type_icons", "station_names"}
    job = set(re.findall(r'finding\("(?:import|datamodel)", "([a-z_]+)"', (ROOT / "web" / "findings.py").read_text()))
    assert "patrols_failed" in job and "site_token_rejected" in job
    return sorted(checklist | job | set(PREFLIGHT_CODES))


def _er_smart_sync_codes():
    """Every code er-smart-sync's source can emit; skips when the source is not around."""
    import re
    preflight, checklist = _er_smart_sync_source("preflight"), _er_smart_sync_source("patrol_datamodel")
    if not (preflight and checklist):
        pytest.skip("er-smart-sync's source is not available here: install it, check it out beside this repo, or build .venv-load")
    return sorted(set(re.findall(r'Finding(?:\.of)?\(\s*"([a-z_]+)"', preflight))
                  | set(re.findall(r'(?:ChecklistItem|_permission_item)\(\s*"([a-z_]+)"', checklist)))


def test_the_sections_come_in_order_with_ids_and_html(help_mod):
    sections = help_mod.sections()
    assert [s["id"] for s in sections] == ["overview", "sites", "loading", "statuses", "stops", "quirks"]
    assert all(s["title"] and "<p>" in s["html"] for s in sections)
    assert sections[-1]["title"] == "SMART data quirks" and 'id="quirks-timezones"' in sections[-1]["html"]
    assert 'id="timezones"' not in sections[-1]["html"]   # prefixed: the doc's headings cannot collide with the app's ids


def test_every_finding_code_has_an_entry(help_mod, monkeypatch):
    stops = next(s for s in help_mod.sections() if s["id"] == "stops")["html"]
    missing = [c for c in _finding_codes(monkeypatch) if f'id="finding-{c}"' not in stops]
    assert missing == []


def test_every_er_smart_sync_code_has_an_entry(help_mod):
    stops = next(s for s in help_mod.sections() if s["id"] == "stops")["html"]
    codes = _er_smart_sync_codes()
    assert len(codes) >= 20
    missing = [c for c in codes if f'id="finding-{c}"' not in stops]
    assert missing == []


def test_links_do_not_leave_the_app(help_mod):
    quirks = next(s for s in help_mod.sections() if s["id"] == "quirks")["html"]
    assert 'href="profiles-to-er-entities.md"' not in quirks
    assert 'href="https://github.com/PADAS/er-smart-able/blob/main/docs/profiles-to-er-entities.md"' in quirks
    assert '<a target="_blank" rel="noopener" href="https://github.com' in quirks


def test_every_load_status_has_an_entry(help_mod):
    statuses = next(s for s in help_mod.sections() if s["id"] == "statuses")["html"]
    for st in ["planning", "planned", "queued", "running", "continuing", "needs_attention", "done", "failed"]:
        assert f"<code>{st}</code>" in statuses, st


def test_the_api_serves_the_help_to_signed_in_users(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "help_pages"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient
    c = TestClient(app.app)
    r = c.get("/api/help")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sections"]]
    assert ids[0] == "overview" and "stops" in ids


def test_every_help_link_in_the_page_has_an_entry(help_mod):
    js = (ROOT / "web" / "static" / "app.js").read_text()
    ids = set(re.findall(r"(?:openHelp|helpBtn)\('([a-z0-9_-]+)'", js)) | set(re.findall(r'data-help="([a-z0-9_-]+)"', js))
    assert "loading-models" in ids
    html = "".join(s["html"] for s in help_mod.sections())
    sections = {"help-" + s["id"] for s in help_mod.sections()}
    missing = [i for i in ids if f'id="{i}"' not in html and i not in sections]
    assert not missing, missing
