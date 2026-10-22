"""The in-app help: every section the drawer lists, an entry for every
finding a load can stop on, and the quirks doc included from its one
source."""
from __future__ import annotations

import importlib
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


def _finding_codes(monkeypatch):
    import re
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("findings", None)
    findings = importlib.import_module("findings")
    checklist = set(findings.BLOCKING_CHECKLIST) | set(findings.VALUE_LABEL)
    job = set(re.findall(r'finding\("(?:import|datamodel)", "([a-z_]+)"', (ROOT / "web" / "findings.py").read_text()))
    assert "patrols_failed" in job and "site_token_rejected" in job
    preflight = set(PREFLIGHT_CODES)
    try:   # the load venv has er-smart-sync: read every code its preflight can emit
        import er_smart_sync.preflight as pf
        preflight |= set(re.findall(r'Finding(?:\.of)?\(\s*"([a-z_]+)"', Path(pf.__file__).read_text()))
    except ImportError:
        pass
    return sorted(checklist | job | preflight)


def test_the_sections_come_in_order_with_ids_and_html(help_mod):
    sections = help_mod.sections()
    assert [s["id"] for s in sections] == ["overview", "sites", "loading", "statuses", "stops", "quirks"]
    assert all(s["title"] and "<p>" in s["html"] for s in sections)
    assert sections[-1]["title"] == "SMART data quirks" and 'id="timezones"' in sections[-1]["html"]


def test_every_finding_code_has_an_entry(help_mod, monkeypatch):
    stops = next(s for s in help_mod.sections() if s["id"] == "stops")["html"]
    missing = [c for c in _finding_codes(monkeypatch) if f'id="finding-{c}"' not in stops]
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
