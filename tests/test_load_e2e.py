"""The whole plan path for real: a synthetic SMART database is extracted and
exported, the dataset is loaded in plan mode through er-smart-sync's dry-run
client against a fake EarthRanger, and the plan has the expected counts."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("er_smart_sync")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}


class FakeER:
    """An empty EarthRanger site behind erclient's ERClient interface, reads
    only. Every answer has the shape the real client returns for a site with
    nothing on it. Writes never reach it (DryRunERClient intercepts them; it
    only looks the attribute up), so each write method fails if called."""

    # erclient's wrapped reads: lists, with the "data" envelope already stripped
    def get_event_categories(self, *a, **k):
        return []

    def get_event_types(self, *a, **k):
        return []

    def get_subjects(self, *a, **k):
        return []

    def get_subjectgroups(self, *a, **k):
        return []

    def _get(self, path, params=None, max_retries=None, **k):
        """The raw GETs er_smart_sync makes (ERPatrolAPI, choices). Patrol
        types, the segment form and the patrol configuration 404 on an empty
        site; ERPatrolAPI reads 404 as "not there"."""
        from erclient.er_errors import ERClientNotFound

        if path == "status":
            return {"version": "2.130.0", "preview_features": {"patrol_schemas": True}}
        if path == "user/me":
            return {"username": "ops", "is_superuser": True}
        if path == "choices":
            return {"count": 0, "next": None, "previous": None, "results": []}
        raise ERClientNotFound(f"404 from ER: {path}")

    def _fail(self, *a, **k):
        raise AssertionError("a write reached the fake site: DryRunERClient should have caught it")

    _post = _patch = post_subject = post_event_file = post_event_category = post_event_type = patch_event_type = _fail


def _plan(smart_parquet, tmp_path, monkeypatch, **options):
    """Extract, export and plan a load of the synthetic dataset with these options."""
    from export.__main__ import main as export_main

    work = smart_parquet.parent
    site_data = work / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert export_main(["--work", str(work), "--site-data", str(site_data), "--source-kind", "backup", "--source-file", "x.zip"]) == 0
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "job", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    store = importlib.import_module("store").get_store()
    job = importlib.import_module("job")
    load_job = importlib.import_module("load_job")
    ds = store.create({"name": "alpha", "source_name": "x.zip", "status": "ready", "created_at": "2026-10-21T00:00:00+00:00",
                       "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    store.put_export(ds, work / "export")
    store.update(ds, export=job.describe_export(work / "export"))
    site = store.create_site({"name": "fake", "url": "fake.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    load_id = store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": "planning", "stage": None,
                                 "options": {"language": "en", "configurable_model": None, "roster_group": None, **options},
                                 "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                                 "continuations": 0, "findings": [], **OWNER})
    rc = load_job.Runner(store, load_id, "plan", work=tmp_path / "work",
                         migration_factory=lambda **kw: load_job.ErSmartSyncMigration(er_client=FakeER(), **kw),
                         check_token=lambda h, t: "ops", env={}).run()
    load = store.get_load(load_id)
    assert rc == 0 and load["status"] == "planned", load.get("error")
    return load


def test_a_windowed_plan_counts_only_the_patrols_in_it(smart_parquet, tmp_path, monkeypatch):
    load = _plan(smart_parquet, tmp_path, monkeypatch, since="2019-04-01")
    p = load["plan"]["patrols"]
    assert p["total"] == 1 and p["first"] == p["last"] and p["first"] >= "2019-04-01"
    # the second patrol has no waypoints and no track: nothing of the first one's is counted
    assert p["events"] == 0 and p["track_points"] == 0


def test_a_data_model_plan_end_to_end(smart_parquet, tmp_path, monkeypatch):
    load = _plan(smart_parquet, tmp_path, monkeypatch, scope="datamodel")
    assert "patrols" not in load["plan"] and load["stage"] == "patrol_datamodel"
    assert load["plan"]["event_types"]["create"] and load["plan"]["patrol_types"]["create"]
    assert "preflight" not in load["stages"]


def test_plan_mode_end_to_end(smart_parquet, tmp_path, monkeypatch):
    from export.__main__ import main as export_main

    work = smart_parquet.parent
    site_data = work / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert export_main(["--work", str(work), "--site-data", str(site_data), "--source-kind", "backup", "--source-file", "x.zip"]) == 0

    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "job", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    store = importlib.import_module("store").get_store()
    job = importlib.import_module("job")
    load_job = importlib.import_module("load_job")

    ds = store.create({"name": "alpha", "source_name": "x.zip", "status": "ready", "created_at": "2026-10-21T00:00:00+00:00",
                       "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    store.put_export(ds, work / "export")
    export = job.describe_export(work / "export")
    store.update(ds, export=export)
    assert [e["dir"] for e in export] == ["ALPHA"] and export[0]["patrols"] == 2

    site = store.create_site({"name": "fake", "url": "fake.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    load_id = store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": "planning", "stage": None,
                                 "options": {"language": "en", "configurable_model": None, "roster_group": None},
                                 "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                                 "continuations": 0, "findings": [], **OWNER})

    def factory(**kw):
        return load_job.ErSmartSyncMigration(er_client=FakeER(), **kw)

    rc = load_job.Runner(store, load_id, "plan", work=tmp_path / "work", migration_factory=factory,
                         check_token=lambda h, t: "ops", env={}).run()
    load = store.get_load(load_id)
    assert rc == 0 and load["status"] == "planned", load.get("error")
    plan = load["plan"]
    assert plan["patrols"]["total"] == 2 and plan["patrols"]["already_done"] == 0
    assert plan["event_types"]["create"], "the dry run should plan event types for the synthetic data model"
    assert any(e["value"] == "patrol_foot" for e in plan["patrol_types"]["create"])
    # both rangers patrol, so both become subjects, named; a plan has no id for them (er-smart-sync's
    # placeholder must not surface as a value)
    assert sorted(e["label"] for e in plan["subjects"]["create"]) == ["Ana Cruz", "Ben Reyes"]
    assert all(e["value"] is None for e in plan["subjects"]["create"])
    codes = {f["code"] for f in load["findings"]}
    assert "team" in codes   # Team One is not on the fake site
    # the empty site lacks the data model the run will write, so those preflight findings are info;
    # only the missing team blocks (nothing a load creates)
    blocking_preflight = {f["code"] for f in load["findings"] if f["stage"] == "preflight" and f["severity"] == "blocking"}
    assert blocking_preflight <= {"teams"}, blocking_preflight
    created = {f["code"] for f in load["findings"] if f["title"].startswith("Will be created by this load: ")}
    assert {"patrol_types", "segment_schema", "subjects", "event_types"} <= created
    team = [f for f in load["findings"] if f["code"] == "team"]
    assert team and all(f["severity"] == "blocking" for f in team)
    assert store.get_load_file(ds, load_id, "plan.json") and store.get_load_file(ds, load_id, "checklist.md")
