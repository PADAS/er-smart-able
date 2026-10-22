"""The in-app help: every section the drawer lists, an entry for every
finding a load can stop on, and the quirks doc included from its one
source."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

# every code web/findings.py and the load job can put on a load
CHECKLIST_CODES = ["enable_patrol_schemas", "permission_patrol_types", "permission_segment_schema", "permission_subjects",
                   "permission_patrol_config", "permission_subject_group", "team", "roster_group", "patrol_type_icons",
                   "station_names"]
PREFLIGHT_CODES = ["feature_flag", "permissions", "patrol_types", "segment_schema", "choices", "subjects", "inactive_members",
                   "teams", "event_types", "collection_type", "leg_span", "bundle_warnings"]
JOB_CODES = ["patrols_failed", "site_token_rejected"]


@pytest.fixture
def help_mod(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("help_pages", None)
    return importlib.import_module("help_pages")


def test_the_sections_come_in_order_with_ids_and_html(help_mod):
    sections = help_mod.sections()
    assert [s["id"] for s in sections] == ["overview", "sites", "loading", "statuses", "stops", "quirks"]
    assert all(s["title"] and "<p>" in s["html"] for s in sections)
    assert sections[-1]["title"] == "SMART data quirks" and 'id="timezones"' in sections[-1]["html"]


def test_every_finding_code_has_an_entry(help_mod):
    stops = next(s for s in help_mod.sections() if s["id"] == "stops")["html"]
    missing = [c for c in CHECKLIST_CODES + PREFLIGHT_CODES + JOB_CODES if f'id="finding-{c}"' not in stops]
    assert missing == []


def test_every_load_status_has_an_entry(help_mod):
    statuses = next(s for s in help_mod.sections() if s["id"] == "statuses")["html"]
    for st in ["planning", "planned", "queued", "running", "continuing", "needs_attention", "done", "failed"]:
        assert f"<code>{st}</code>" in statuses, st


def test_the_api_serves_the_help_to_signed_in_users(tmp_path, monkeypatch):
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
