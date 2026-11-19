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


def _plan(smart_parquet, tmp_path, monkeypatch, prepare=None, **options):
    """Extract, export and plan a load of the synthetic dataset with these options.
    prepare(export dir) may change the export before it is stored."""
    from export.__main__ import main as export_main

    work = smart_parquet.parent
    site_data = work / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert export_main(["--work", str(work), "--site-data", str(site_data), "--source-kind", "backup", "--source-file", "x.zip"]) == 0
    if prepare:
        prepare(work / "export")
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


def test_readiness_checks_only_the_patrols_in_the_window(smart_parquet, tmp_path, monkeypatch):
    # only the first patrol uses Team One, which the fake site lacks; a window holding just the
    # second must not stop on it (the patrol setup still covers the whole data model)
    load = _plan(smart_parquet, tmp_path, monkeypatch, since="2019-04-01")
    pre = [f for f in load["findings"] if f["stage"] == "preflight" and f["severity"] == "blocking"]
    assert pre == [], [f["code"] for f in pre]


def test_a_data_model_plan_end_to_end(smart_parquet, tmp_path, monkeypatch):
    load = _plan(smart_parquet, tmp_path, monkeypatch, scope="datamodel")
    assert "patrols" not in load["plan"] and load["stage"] == "patrol_datamodel"
    assert load["plan"]["event_types"]["create"] and load["plan"]["patrol_types"]["create"]
    assert "preflight" not in load["stages"]
    # the rangers are listed, with no patrols from this load (it imports none) but their whole history
    assert {r["name"]: (r["patrols"], r["patrols_total"]) for r in load["rangers"]} == {"Ana Cruz": (0, 2), "Ben Reyes": (0, 1)}


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
    # the rangers list names the same people, with how many patrols each appears on, for their accounts
    # Ana is on both patrols, Ben on one; a plan creates no subjects
    assert {r["name"]: (r["patrols"], r["patrols_total"]) for r in load["rangers"]} == {"Ana Cruz": (2, 2), "Ben Reyes": (1, 1)}
    assert all(r["subject_id"] is None and not r["deleted"] for r in load["rangers"])
    codes = {f["code"] for f in load["findings"]}
    assert "team" in codes   # Team One is not on the fake site
    # the empty site lacks the data model the run will write, so those preflight findings are info;
    # only the missing team blocks (nothing a load creates)
    blocking_preflight = {f["code"] for f in load["findings"] if f["stage"] == "preflight" and f["severity"] == "blocking"}
    assert blocking_preflight == {"teams"}, blocking_preflight   # the first patrol's team
    # every observation's reporter resolves through the subjects the run creates: no observers warning in the plan
    assert "observers" not in {f["code"] for f in load["findings"]}
    created = {f["code"] for f in load["findings"] if f["title"].startswith("Will be created by this load: ")}
    assert {"patrol_types", "segment_schema", "subjects", "event_types"} <= created
    team = [f for f in load["findings"] if f["code"] == "team"]
    assert team and all(f["severity"] == "blocking" for f in team)
    assert store.get_load_file(ds, load_id, "plan.json") and store.get_load_file(ds, load_id, "checklist.md")


def test_a_plan_keeps_only_the_observers_setup_cannot_resolve(smart_parquet, tmp_path, monkeypatch):
    """The plan's observers check runs against the subjects setup plans: an
    observation whose observer is unknown on a leg with no members survives as
    a warning; a failure of the check is a check_failed finding, not a crash."""
    _plan(smart_parquet, tmp_path, monkeypatch)
    load_job = importlib.import_module("load_job")
    m = load_job.ErSmartSyncMigration(bundle_dir=smart_parquet.parent / "export" / "ALPHA" / "bundle", load_dir=tmp_path / "ld",
                                      host="fake.pamdas.org", token="t", options={"language": "en"}, dry_run=True,
                                      ca_identifier="smart-050500", er_client=FakeER())
    leg = m.bundle.patrols[0]["legs"][0]
    leg["members"] = []
    n = 0
    for w in leg["waypoints"]:
        for g in w["observation_groups"]:
            for o in g["observations"]:
                o["employee_uuid"] = "0" * 32   # nobody SMART knows
                n += 1
    assert n > 0
    (f,) = m._observers_after_setup()
    assert f["code"] == "observers" and f["level"] == "warning" and f["count"] == n
    assert m.bundle.patrols[0]["uuid"] in f["affected_patrols"]
    # the whole plan's preflight carries it, through the dry-mode path
    report = m.preflight()
    assert [f["code"] for f in report["warnings"] if f["code"] == "observers"] == ["observers"]
    # a site read that fails inside the extra check is a finding the operator can act on
    m.api.list_subjects = lambda: (_ for _ in ()).throw(RuntimeError("502 from ER"))
    (f,) = m._observers_after_setup()
    assert f["code"] == "check_failed" and "502 from ER" in f["message"]


# ---- the bundle's tracks are read a patrol at a time (bundle version 2), never all at once
@pytest.fixture
def track_reads(monkeypatch):
    """What the load asked the bundle's tracks for: ("patrol", uuid) for one patrol's, ("all",) for every track."""
    from er_smart_sync.bundle import TrackStore

    asked = []
    for_patrol, iterate = TrackStore.for_patrol, TrackStore.__iter__
    monkeypatch.setattr(TrackStore, "for_patrol", lambda self, u: asked.append(("patrol", u)) or for_patrol(self, u))
    monkeypatch.setattr(TrackStore, "__iter__", lambda self: asked.append(("all",)) or iterate(self))
    return asked


def test_a_plan_never_reads_every_track(smart_parquet, tmp_path, monkeypatch, track_reads):
    load = _plan(smart_parquet, tmp_path, monkeypatch)
    assert load["plan"]["patrols"]["total"] == 2 and load["plan"]["patrols"]["track_points"] == 2
    assert ("all",) not in track_reads


def test_a_windowed_plan_reads_no_track_of_a_patrol_outside_it(smart_parquet, tmp_path, monkeypatch, track_reads):
    load = _plan(smart_parquet, tmp_path, monkeypatch, since="2019-04-01")   # only the second patrol, which has no track
    assert load["plan"]["patrols"]["total"] == 1 and load["plan"]["patrols"]["track_points"] == 0
    assert track_reads == []   # a plan counts from the index and reads no track at all


def test_a_windowed_plan_counts_its_patrols_points_from_the_index(smart_parquet, tmp_path, monkeypatch, track_reads):
    load = _plan(smart_parquet, tmp_path, monkeypatch, until="2019-03-31")   # only the first patrol, whose track has two points
    assert load["plan"]["patrols"]["total"] == 1 and load["plan"]["patrols"]["track_points"] == 2
    assert ("all",) not in track_reads


def _as_version_1(export_dir: Path):
    """Rewrite the exported bundle the way smart-able wrote it before version 2."""
    b = export_dir / "ALPHA" / "bundle"
    tracks = [json.loads(l) for l in (b / "tracks.jsonl").read_text().splitlines()]
    (b / "tracks.jsonl").unlink()
    (b / "tracks.index.json").unlink()
    (b / "tracks.json").write_text(json.dumps({"tracks": tracks}, indent=1))
    m = json.loads((b / "manifest.json").read_text())
    m["bundle_schema_version"] = 1
    (b / "manifest.json").write_text(json.dumps(m, indent=1))


@pytest.mark.parametrize("options", [{}, {"until": "2019-03-31"}, {"since": "2019-04-01"}])
def test_a_dataset_extracted_before_version_2_still_plans_the_same(smart_parquet, tmp_path, monkeypatch, options):
    import shutil

    new = _plan(smart_parquet, tmp_path / "new", monkeypatch, **options)
    shutil.rmtree(smart_parquet.parent / "export")
    shutil.rmtree(smart_parquet.parent / "site")
    old = _plan(smart_parquet, tmp_path / "old", monkeypatch, prepare=_as_version_1, **options)
    assert old["plan"]["patrols"] == new["plan"]["patrols"]
    assert [(f["stage"], f["code"]) for f in old["findings"]] == [(f["stage"], f["code"]) for f in new["findings"]]


# ---- the contract between this repository's exporter and er-smart-sync's reader: the bytes one
# writes are the bytes the other reads. Each side's own tests write the tracks with its own code.
def test_what_the_exporter_writes_is_what_er_smart_sync_reads(tmp_path):
    from er_smart_sync.bundle import load_bundle
    from export.bundle import validate_bundle_dir, write_tracks

    import er_smart_sync
    fixture = Path(er_smart_sync.__file__).parents[2] / "tests" / "fixtures" / "smart_demo_bundle"
    if not fixture.is_dir():
        pytest.skip("er-smart-sync is installed without its tests (not an editable checkout)")
    import shutil
    b = tmp_path / "bundle"
    shutil.copytree(fixture, b)
    tracks = json.loads((b / "tracks.json").read_text())["tracks"]
    assert len({t["patrol_uuid"] for t in tracks}) > 1
    tracks[0]["note"] = "é—ñ \u2028 line\nbreak 🐘"   # bytes are not characters, and a line holds no raw newline
    (b / "tracks.json").unlink()
    m = json.loads((b / "manifest.json").read_text())
    m["bundle_schema_version"] = 2
    (b / "manifest.json").write_text(json.dumps(m))
    index = write_tracks(tracks, b)["patrols"]
    assert validate_bundle_dir(b) == []
    got = load_bundle(b)
    key = lambda t: t["uuid"]   # noqa: E731
    for u in {t["patrol_uuid"] for t in tracks}:
        mine = [t for t in tracks if t["patrol_uuid"] == u]
        assert sorted(got.tracks.for_patrol(u), key=key) == sorted(mine, key=key)
        assert got.tracks.points(u) == index[u]["points"] == sum(len(p["coordinates"]) for t in mine for p in t["parts"])
    assert len(got.tracks) == len(tracks) == m["counts"]["tracks"]
    write_tracks([], b)
    assert validate_bundle_dir(b) == [] and list(load_bundle(b).tracks) == []


def test_an_exported_bundle_imports_its_tracks(smart_parquet, tmp_path):
    """The exporter's bundle through er-smart-sync's by-day lookup, as an import builds it for a patrol."""
    from er_smart_sync.bundle import load_bundle
    from er_smart_sync.patrol_times import tracks_by_day
    from export.bundle import build_tracks, write_bundle
    from export.smartdb import SmartDb, hyphenate
    from tests.conftest import CA_A, DAY_1, PATROL_1
    from zoneinfo import ZoneInfo

    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "configured", None, {"kind": "backup", "file": "x.zip"})
    b = load_bundle(out)
    assert b.manifest.bundle_schema_version == 2
    by_day = tracks_by_day(b.tracks.for_patrol(hyphenate(PATROL_1)))
    assert by_day == {hyphenate(DAY_1): build_tracks(db, CA_A, ZoneInfo("Asia/Manila"), [])["tracks"]}
    other = next(p["uuid"] for p in b.patrols if p["uuid"] != hyphenate(PATROL_1))
    assert b.tracks.for_patrol(other) == [] and b.tracks.points(hyphenate(PATROL_1)) == 2


# ---- several conservation areas into one site (GUNDI-5946)

CM = "00000000000000000000000000000600"
OTHER_CM = "00000000000000000000000000000777"


def _export(smart_parquet):
    """The synthetic dataset's export folder for ALPHA: the bundle, its data model and its configurable model."""
    from export.__main__ import main as export_main

    work = smart_parquet.parent
    site_data = work / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert export_main(["--work", str(work), "--site-data", str(site_data), "--source-kind", "backup", "--source-file", "x.zip"]) == 0
    return work / "export" / "ALPHA"


def _another_area(src: Path, dst: Path, *, differs=False) -> Path:
    """A second conservation area's export of the same data: its copy of the configurable model has its
    own uuid, as every area's does, and the same name. With differs, its list offers lion where the first
    offers elephant, and its Species field has another title."""
    import shutil

    shutil.copytree(src, dst)
    (dst / f"configurable_model_{CM}.xml").rename(dst / f"configurable_model_{OTHER_CM}.xml")
    dm = dst / "datamodel.json"
    dm.write_text(dm.read_text().replace(CM, OTHER_CM))
    if differs:
        cm = dst / f"configurable_model_{OTHER_CM}.xml"
        text = cm.read_text()
        assert 'keyRef="elephant"' in text
        cm.write_text(text.replace('keyRef="elephant"', 'keyRef="lion"').replace('value="Elephant"', 'value="Lion"').replace('value="Éléphant"', 'value="Lion"'))
        xml = dst / "datamodel.xml"
        assert '<names language_code="en" value="Species"/>' in xml.read_text()
        xml.write_text(xml.read_text().replace('<names language_code="en" value="Species"/>', '<names language_code="en" value="Species seen"/>'))
    return dst


@pytest.fixture
def load_job(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "job", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    return importlib.import_module("load_job")


def _migration(load_job, export_dir, site, tmp_path, *, cm=CM, dry_run=False, category="smart-a", **options):
    return load_job.ErSmartSyncMigration(er_client=site, bundle_dir=export_dir / "bundle", load_dir=tmp_path / f"ld-{export_dir.name}",
                                         host="fake.pamdas.org", token="tok", dry_run=dry_run, ca_identifier=category,
                                         options={"language": "en", "configurable_model": cm, **options})


def _active(site):
    return {(f, v) for f in site.choice_fields() for v, c in site.choices(f).items() if c["is_active"]}


def test_two_copies_of_one_model_write_one_prefix(smart_parquet, tmp_path, load_job):
    from tests.fake_site import FakeSite

    a = _export(smart_parquet)
    b = _another_area(a, tmp_path / "BETA")
    F = sys.modules["findings"]
    sets = [_migration(load_job, d, FakeSite(), tmp_path, cm=cm).resolve_set() for d, cm in ((a, CM), (b, OTHER_CM))]
    assert sets[0] == sets[1] == {"name": "Alpha mobile model", "prefix": F.set_prefix("Alpha mobile model"), "old": False}
    assert CM not in sets[0]["prefix"] and OTHER_CM not in sets[0]["prefix"]
    # the operator's set name decides, whatever the model is called
    named = _migration(load_job, a, FakeSite(), tmp_path, event_type_set="Region 5").resolve_set()
    assert named == {"name": "Region 5", "prefix": F.set_prefix("region  5"), "old": False}


def test_a_site_with_the_old_set_keeps_it(smart_parquet, tmp_path, load_job):
    from tests.fake_site import FakeSite

    a = _export(smart_parquet)
    site = FakeSite()
    site.post_event_type(event_type={"value": f"smart-ca-import_{CM}_animals_liveanimals", "display": "Live animals",
                                     "category": "smart_050500", "schema": {}, "is_active": False}, version="v2")
    site.post_event_category(data={"value": "smart_050500", "display": "x"})
    m = _migration(load_job, a, site, tmp_path, event_type_set="Region 5")
    assert m.resolve_set() == {"name": None, "prefix": f"smart-ca-import_{CM}", "old": True}
    assert m.event_type_prefix == f"smart-ca-import_{CM}"
    stats = m.push_datamodel()
    assert all(v.startswith(f"smart-ca-import_{CM}_") for v in site.event_types())
    assert stats["event_category"] == "smart_050500"   # and its types stay where they were
    # another area, whose model has another uuid, is not held back by it
    other = _migration(load_job, _another_area(a, tmp_path / "BETA"), site, tmp_path, cm=OTHER_CM)
    assert other.resolve_set()["old"] is False


def test_a_load_made_before_set_names_gets_the_models_label(smart_parquet, tmp_path, load_job):
    from tests.fake_site import FakeSite

    m = _migration(load_job, _export(smart_parquet), FakeSite(), tmp_path)   # options carry no event_type_set
    assert m.set_name == "Alpha mobile model" and m.resolve_set()["name"] == "Alpha mobile model"


def test_a_load_without_a_model_reads_nothing_to_resolve_its_set(smart_parquet, tmp_path, load_job):
    class NoReads:
        def __getattr__(self, name):
            raise AssertionError(f"{name} was called to resolve the set of a load with no configurable model")

    m = _migration(load_job, _export(smart_parquet), NoReads(), tmp_path, cm=None)
    assert m.resolve_set() == {"name": None, "prefix": "smart-ca-import", "old": False}
    assert m.set_name is None and m.event_type_prefix == "smart-ca-import"


def test_the_job_records_the_set_and_its_category(smart_parquet, tmp_path, monkeypatch):
    load = _plan(smart_parquet, tmp_path, monkeypatch, scope="datamodel", configurable_model=CM, event_type_set="Region 5")
    F = sys.modules["findings"]
    recorded = load["event_type_set"]
    assert recorded["name"] == "Region 5" and recorded["prefix"] == F.set_prefix("Region 5") and recorded["old"] is False
    assert recorded["category"] and load["plan"]["event_type_set"] == recorded
    assert all(e["value"].startswith(recorded["prefix"] + "_") for e in load["plan"]["event_types"]["create"])
    assert not [f for f in load["findings"] if f["code"] == "shared_set_changes"]   # an empty site: nothing is shared yet


@pytest.mark.parametrize("differs", [False, True])
def test_the_plan_warns_when_a_shared_set_would_change(smart_parquet, tmp_path, load_job, differs):
    from tests.fake_site import FakeSite

    F = sys.modules["findings"]
    a = _export(smart_parquet)
    site = FakeSite()
    _migration(load_job, a, site, tmp_path).push_datamodel()
    before = site.event_types()
    b = _migration(load_job, _another_area(a, tmp_path / "BETA", differs=differs), site, tmp_path, cm=OTHER_CM, dry_run=True)
    b.resolve_set()
    f = F.shared_set_changes(datamodel_stats=b.push_datamodel(), dry_calls=b.dry_calls)
    assert site.event_types() == before   # a plan writes nothing
    if differs:
        assert f["severity"] == "warning" and f["values"] == [F.set_prefix("Alpha mobile model") + "_animals_liveanimals"]
        assert "adds: 1" in f["detail"]
    else:
        assert f is None


@pytest.mark.parametrize("order", ["a_then_b", "b_then_a"])
def test_two_areas_share_one_set_and_take_nothing_from_each_other(smart_parquet, tmp_path, load_job, order):
    from tests.fake_site import FakeSite

    F = sys.modules["findings"]
    a = _export(smart_parquet)
    b = _another_area(a, tmp_path / "BETA", differs=True)
    areas = [(a, CM, "smart-a"), (b, OTHER_CM, "smart-b")]
    if order == "b_then_a":
        areas.reverse()
    site = FakeSite()
    (d1, cm1, cat1), (d2, cm2, cat2) = areas
    _migration(load_job, d1, site, tmp_path, cm=cm1, category=cat1).push_datamodel()
    first_types, first_active, first_categories = site.event_types(), _active(site), site.categories()
    alone = FakeSite()
    _migration(load_job, d2, alone, tmp_path, cm=cm2, category=cat2).push_datamodel()

    _migration(load_job, d2, site, tmp_path, cm=cm2, category=cat2).push_datamodel()

    types = site.event_types()
    prefix = F.set_prefix("Alpha mobile model") + "_"
    # one set: each event type once, all under the name's prefix, none under either model's uuid
    assert set(types) == set(first_types) | set(alone.event_types()) and all(v.startswith(prefix) for v in types)
    # nothing taken from the first area
    for v, t in first_types.items():
        assert types[v]["category"] == t["category"] and (types[v]["is_active"] or not t["is_active"]), v
    assert first_active <= _active(site) and _active(alone) <= _active(site)
    assert {v for _, v in _active(site)} >= {"elephant", "lion"}
    assert site.categories() == first_categories and len(first_categories) == 1
