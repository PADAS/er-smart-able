"""The load job: stages in order, the stop rule, continuation, and every
exit path recording an outcome on the load."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
           "configurable_models": [{"uuid": "abc", "label": "Mobile"}], "patrols": 3, "timezone": "Asia/Manila"}]
TEAM = {"code": "team", "title": "Create the patrol team Alpha", "steps": ["Admin > Teams."]}
ICONS = {"code": "patrol_type_icons", "title": "Pick icons", "steps": ["Admin > Patrol types."]}
PATROLS = [{"uuid": "u1", "id": "P-1", "start_date": "2019-03-04"}, {"uuid": "u2", "id": "P-2", "start_date": "2019-03-05"},
           {"uuid": "u3", "id": "P-3", "start_date": "2019-03-06"}]


class FakeMigration:
    def __init__(self, *, checklist=(), preflight=None, failed=None, per_patrol_seconds=0, clock=None, raise_in=None):
        self.dry_calls = []
        self.checklist = list(checklist)
        self.preflight_report = preflight or {"blocking": [], "warnings": []}
        self.failed = failed or {}
        self.calls = []
        self.per_patrol_seconds = per_patrol_seconds
        self.clock = clock
        self.raise_in = raise_in
        self.done = set()
        self.phase_skipped = {}   # phase -> the count reported with its last patrol

    def _call(self, name):
        self.calls.append(name)
        if self.raise_in == name:
            raise RuntimeError(f"boom in {name}")

    def push_datamodel(self):
        self._call("push_datamodel"); return {"event_types_created": 2, "event_types_unchanged": 0}

    def patrol_datamodel(self, out_dir):
        self._call("patrol_datamodel")
        (Path(out_dir) / "checklist.md").write_text("# checklist")
        return self.checklist, {"schema_written": True, "subjects_grouped": 1}, [{"kind": "patrol_type", "action": "created", "value": "patrol_foot"}]

    def preflight(self):
        self._call("preflight"); return self.preflight_report

    def patrols(self):
        return PATROLS

    def counts(self):
        return {"observations": 9, "track_points": 300}

    def ledger_done(self):
        return set(self.done)

    def import_patrols(self, progress, stop):
        """Both phases, as er-smart-sync reports them: a done == 0 call at each
        phase start, then one per patrol; the clock advances per patrol."""
        self._call("import_patrols")
        imported = []
        for phase in ("events", "tracks"):
            progress({"phase": phase, "total": len(PATROLS), "done": 0, "failed": 0, "already_imported": 0, "phase_skipped": 0})
            for i, p in enumerate(PATROLS):
                if stop.is_set():
                    return {"imported": imported, "failed": dict(self.failed), "stopped_early": True}
                if self.clock is not None:
                    self.clock.advance(self.per_patrol_seconds)
                if phase == "tracks" and p["uuid"] not in self.failed:
                    imported.append(p["uuid"]); self.done.add(p["uuid"])
                progress({"phase": phase, "total": len(PATROLS), "done": i + 1,
                          "failed": sum(1 for u in self.failed if u in [q["uuid"] for q in PATROLS[:i + 1]]), "already_imported": 0,
                          "phase_skipped": self.phase_skipped.get(phase, 0) if i + 1 >= len(PATROLS) else 0})
        return {"imported": imported, "failed": dict(self.failed), "stopped_early": False}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("store", "load_job", "findings", "er_site"):
        sys.modules.pop(m, None)
    store = importlib.import_module("store").get_store()
    load_job = importlib.import_module("load_job")
    ds = store.create({"name": "x", "source_name": "b.zip", "status": "ready", "export": EXPORT,
                       "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    b = store._p(ds) / "export" / "ALPHA" / "bundle"
    b.mkdir(parents=True)
    (b / "manifest.json").write_text(json.dumps({"counts": {"observations": 9, "track_points": 300}}))
    site = store.create_site({"name": "s", "url": "x.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    return store, load_job, ds, site, tmp_path


def _load(store, ds, site, status, **extra):
    return store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": status, "stage": None,
                              "options": {"language": "en", "configurable_model": None, "roster_group": "Rangers"},
                              "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                              "continuations": 0, "findings": [], **OWNER, **extra})


def _run(env, mode, migration, status, clock=None, env_vars=None, check_token=lambda host, token: "ops", **load_extra):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, status, **load_extra)
    seen = {}
    factory = lambda **kw: seen.update(kw) or migration
    runner = load_job.Runner(store, id, mode, work=tmp / "work", migration_factory=factory, check_token=check_token,
                             clock=clock or Clock(), env={"LOAD_SOFT_DEADLINE_SECONDS": "100", "LOAD_MAX_CONTINUATIONS": "2", **(env_vars or {})})
    rc = runner.run()
    return rc, store.get_load(id), seen


def test_plan_mode_writes_the_plan_and_imports_nothing(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, seen = _run(env, "plan", m, "planning")
    assert rc == 0 and load["status"] == "planned" and load["stage"] == "import"
    assert m.calls == ["push_datamodel", "patrol_datamodel", "preflight"]
    assert seen["dry_run"] is True and seen["host"] == "x.pamdas.org" and seen["token"] == "tok"
    assert seen["ca_identifier"] == "smart-050500" and seen["options"]["roster_group"] == "Rangers"
    assert load["plan"]["patrols"] == {"total": 3, "first": "2019-03-04", "last": "2019-03-06", "already_done": 0,
                                       "events": 9, "track_points": 300}
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons"]
    store = env[0]
    assert store.get_load_file(load["dataset_id"], load["id"], "plan.json") is not None
    assert store.get_load_file(load["dataset_id"], load["id"], "checklist.json") is not None


def test_plan_mode_with_blocking_findings_is_still_planned(env):
    rc, load, _ = _run(env, "plan", FakeMigration(checklist=[TEAM]), "planning")
    assert load["status"] == "planned" and load["findings"][0]["severity"] == "blocking"


def test_run_stops_after_patrol_datamodel_on_a_blocking_item(env):
    m = FakeMigration(checklist=[TEAM])
    rc, load, _ = _run(env, "run", m, "queued")
    assert rc == 0 and load["status"] == "needs_attention" and load["stage"] == "patrol_datamodel"
    assert m.calls == ["push_datamodel", "patrol_datamodel"]
    assert load["findings"][0]["code"] == "team"


def test_run_stops_after_preflight_on_a_blocking_finding(env):
    pre = {"blocking": [{"code": "team_missing", "level": "blocking", "message": "m", "fix": "f", "count": 1,
                         "examples": [], "affected_patrols": ["u1"]}], "warnings": []}
    m = FakeMigration(checklist=[ICONS], preflight=pre)
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "needs_attention" and load["stage"] == "preflight"
    assert "import_patrols" not in m.calls
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons", "team_missing"]


def test_run_imports_when_only_warnings_remain(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "done" and load["stage"] == "import"
    assert m.calls[-1] == "import_patrols"
    assert load["progress"] == {"patrols_total": 3, "done": 3, "failed": 0, "skipped": 0, "events": 9, "track_points": 300}
    assert "patrol_type_icons" in [f["code"] for f in load["findings"]]
    store = env[0]
    assert store.get_load_file(load["dataset_id"], load["id"], "log.txt") is not None
    assert load["log_tail"]


def test_failed_patrols_need_attention(env):
    m = FakeMigration(failed={"u2": "500 on the track"})
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "needs_attention"
    f = [f for f in load["findings"] if f["code"] == "patrols_failed"][0]
    assert f["affected"]["patrols"] == ["u2"] and "P-2: 500 on the track" in f["detail"]
    assert load["progress"]["failed"] == 1


def test_the_soft_deadline_stops_and_continues(env, monkeypatch):
    store = env[0]
    starts = []
    monkeypatch.setattr(store, "start_load", lambda id, mode: starts.append((id, mode)) or "exec-2")
    clock = Clock()
    m = FakeMigration(per_patrol_seconds=60, clock=clock)
    rc, load, _ = _run(env, "run", m, "queued", clock=clock)
    assert load["status"] == "continuing" and load["continuations"] == 1
    assert starts == [(load["id"], "run")]
    assert load["progress"]["done"] < 3
    # a continuing load is still live: it keeps the phase it stopped in, so the bar does not drop to the finished count
    assert load["progress"]["phase"] == "events" and load["progress"]["done"] >= 1


def test_too_many_continuations_fail(env, monkeypatch):
    store, load_job, ds, site, tmp = env
    monkeypatch.setattr(store, "start_load", lambda id, mode: "exec-3")
    clock = Clock()
    id = _load(store, ds, site, "queued", continuations=2)
    m = FakeMigration(per_patrol_seconds=60, clock=clock)
    runner = load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: m,
                             check_token=lambda h, t: "ops", clock=clock,
                             env={"LOAD_SOFT_DEADLINE_SECONDS": "100", "LOAD_MAX_CONTINUATIONS": "2"})
    assert runner.run() == 0
    load = store.get_load(id)
    assert load["status"] == "failed" and "not finishing" in load["error"]


def test_an_exception_in_a_stage_records_failed(env):
    rc, load, _ = _run(env, "run", FakeMigration(raise_in="preflight"), "queued")
    assert load["status"] == "failed" and "boom in preflight" in load["error"] and load["stage"] == "preflight"


def test_a_rejected_token_needs_attention(env):
    import er_site

    def rejected(host, token):
        raise er_site.TokenRejected("401 Unauthorized")

    m = FakeMigration()
    rc, load, _ = _run(env, "run", m, "queued", check_token=rejected)
    assert load["status"] == "needs_attention" and load["findings"][0]["code"] == "site_token_rejected"
    assert m.calls == []


def test_a_missing_site_fails(env):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, "queued")
    store.delete_site(site)
    runner = load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: FakeMigration(),
                             check_token=lambda h, t: "ops", clock=Clock(), env={})
    assert runner.run() == 0
    assert store.get_load(id)["status"] == "failed" and "site" in store.get_load(id)["error"].lower()


def test_a_missing_load_exits_2(env):
    store, load_job, ds, site, tmp = env
    assert load_job.Runner(store, "nope", "run", work=tmp / "work", migration_factory=lambda **kw: FakeMigration(),
                           check_token=lambda h, t: "ops", clock=Clock(), env={}).run() == 2


def test_a_claimed_slot_is_marked_running_with_a_start_time(env):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, "queued")
    m = FakeMigration()
    seen_running = {}
    real_update = store.update_load

    def spy(load_id, **fields):
        if fields.get("status") == "running":
            seen_running.update(fields)
        real_update(load_id, **fields)

    store.update_load = spy
    load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: m,
                    check_token=lambda h, t: "ops", clock=Clock(), env={}).run()
    assert seen_running.get("started_at")


def test_a_raising_store_update_in_progress_does_not_abort_the_import(env, monkeypatch):
    store = env[0]
    real_update = store.update_load
    raised = []

    def flaky(load_id, **fields):
        if fields.get("progress") and not raised:
            raised.append(1)
            raise RuntimeError("firestore hiccup")
        real_update(load_id, **fields)

    monkeypatch.setattr(store, "update_load", flaky)
    m = FakeMigration()
    rc, load, _ = _run(env, "run", m, "queued")
    assert raised and rc == 0 and load["status"] == "done"
    assert load["progress"]["done"] == 3
    assert "progress update failed: RuntimeError: firestore hiccup" in load["log_tail"]


def test_library_log_output_reaches_the_log(env):
    import logging

    class Logging(FakeMigration):
        def preflight(self):
            logging.getLogger("er_smart_sync.preflight").info("checked 3 patrols")
            return super().preflight()

    rc, load, _ = _run(env, "run", Logging(), "queued")
    assert "checked 3 patrols" in load["log_tail"]
    store = env[0]
    chunks, _, _ = store.get_load_file(load["dataset_id"], load["id"], "log.txt")
    assert "checked 3 patrols" in b"".join(chunks).decode()
    assert not any(type(h).__name__ == "_RunLogHandler" for h in logging.getLogger().handlers)


def _stored_log(store, load):
    chunks, _, _ = store.get_load_file(load["dataset_id"], load["id"], "log.txt")
    return b"".join(chunks).decode()


def test_the_outcome_line_reaches_the_tail_and_the_log(env):
    rc, load, _ = _run(env, "run", FakeMigration(), "queued")
    line = f"load {load['id']}: done"
    assert line in load["log_tail"] and line in _stored_log(env[0], load)


def test_the_token_never_reaches_the_log(env):
    store, load_job, ds, _, tmp = env
    site = store.create_site({"name": "s2", "url": "y.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER},
                             "SECRET-TOKEN-xyz")
    id = _load(store, ds, site, "queued")
    seen = {}
    m = FakeMigration(failed={"u2": "500 on the track"})
    load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: seen.update(kw) or m,
                    check_token=lambda h, t: "ops", clock=Clock(), env={}).run()
    load = store.get_load(id)
    assert seen["token"] == "SECRET-TOKEN-xyz"
    assert "SECRET-TOKEN-xyz" not in load["log_tail"] and "SECRET-TOKEN-xyz" not in _stored_log(store, load)
    assert "SECRET-TOKEN-xyz" not in json.dumps(load)


def test_a_store_error_on_the_outcome_keeps_the_failed_patrol_findings(env, monkeypatch):
    store = env[0]
    real_update = store.update_load
    n = {"progress": 0}

    def flaky(load_id, **fields):
        if fields.get("progress"):
            n["progress"] += 1
            if n["progress"] == 9:  # the outcome write, after a start and three patrols in each of the two phases
                raise RuntimeError("store down")
        real_update(load_id, **fields)

    monkeypatch.setattr(store, "update_load", flaky)
    rc, load, _ = _run(env, "run", FakeMigration(checklist=[ICONS], failed={"u2": "500 on the track"}), "queued")
    assert load["status"] == "needs_attention" and "could not be recorded" in load["error"]
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons", "patrols_failed"]
    assert load["progress"] is None


UNPUSHED = {"blocking": [{"code": "patrol_types", "level": "blocking", "message": "1 patrol type(s) the legs need are missing",
                          "fix": "f", "count": 1, "examples": [], "affected_patrols": ["u1"]},
                         {"code": "teams", "level": "blocking", "message": "1 patrol team(s) are missing or inactive",
                          "fix": "f", "count": 1, "examples": [], "affected_patrols": ["u1"]}], "warnings": []}


def test_a_plan_marks_what_the_run_will_create(env):
    rc, load, _ = _run(env, "plan", FakeMigration(preflight=UNPUSHED), "planning")
    by_code = {f["code"]: f for f in load["findings"]}
    assert load["status"] == "planned"
    assert by_code["patrol_types"]["severity"] == "info"
    assert by_code["patrol_types"]["title"].startswith("Will be created by this load: ")
    assert by_code["teams"]["severity"] == "blocking"


def test_a_run_keeps_preflight_findings_blocking(env):
    rc, load, _ = _run(env, "run", FakeMigration(preflight=UNPUSHED), "queued")
    assert load["status"] == "needs_attention" and load["stage"] == "preflight"
    assert {f["code"]: f["severity"] for f in load["findings"]} == {"patrol_types": "blocking", "teams": "blocking"}


def test_the_event_category_option_reaches_the_migration(env):
    options = {"language": "en", "configurable_model": None, "roster_group": None, "event_category": "lawin050500"}
    rc, load, seen = _run(env, "plan", FakeMigration(), "planning", options=options)
    assert seen["ca_identifier"] == "lawin050500"


def test_a_load_without_the_event_category_option_uses_the_default(env):
    options = {"language": "en", "configurable_model": None, "roster_group": None}   # made before the option existed
    rc, load, seen = _run(env, "plan", FakeMigration(), "planning", options=options)
    assert seen["ca_identifier"] == "smart-050500"


def test_the_log_tail_is_capped(env):
    import logging

    class Loud(FakeMigration):
        def preflight(self):
            for i in range(100):
                logging.getLogger("er_smart_sync.preflight").info("payload %d %s", i, "y" * 5000)
            return super().preflight()

    rc, load, _ = _run(env, "run", Loud(), "queued")
    lines = load["log_tail"].split("\n")
    assert len(lines) == 60 and all(len(line) <= 500 for line in lines)
    assert "y" * 5000 in _stored_log(env[0], load)   # log.txt keeps every line whole


def test_an_outcome_too_big_to_record_still_records_the_status(env, monkeypatch):
    store = env[0]
    real_update = store.update_load
    refused = []

    def limited(load_id, **fields):
        if fields.get("status") == "needs_attention" and fields.get("findings") and not refused:
            refused.append(fields)
            raise RuntimeError("400 Document exceeds the maximum size")
        real_update(load_id, **fields)

    monkeypatch.setattr(store, "update_load", limited)
    rc, load, _ = _run(env, "run", FakeMigration(failed={"u2": "500 on the track"}), "queued")
    assert refused and rc == 0
    assert load["status"] == "needs_attention" and load["stage"] == "import"
    assert [f["code"] for f in load["findings"]] == ["patrols_failed"]   # what the operator acts on survives
    assert load["log_tail"] is None and load["progress"] is None and "see log.txt" in load["error"]
    log = _stored_log(store, load)
    assert "recording the outcome failed: RuntimeError: 400 Document exceeds the maximum size" in log
    assert "needs_attention recorded without the tail, plan and progress" in log


def test_a_failed_run_keeps_its_error_when_the_outcome_is_too_big(env, monkeypatch):
    store = env[0]
    real_update = store.update_load

    def limited(load_id, **fields):
        if fields.get("status") == "failed" and fields.get("log_tail"):
            raise RuntimeError("too big")
        real_update(load_id, **fields)

    monkeypatch.setattr(store, "update_load", limited)
    rc, load, _ = _run(env, "run", FakeMigration(raise_in="preflight"), "queued")
    assert rc == 0 and load["status"] == "failed" and "boom in preflight" in load["error"]


def test_a_deleted_load_stops_the_import(env):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, "queued")
    clock = Clock()

    class Deleting(FakeMigration):
        def import_patrols(self, progress, stop):
            def wrapped(p):
                if p["phase"] == "tracks" and p["done"] == 2:
                    store.delete_load(id)
                progress(p)
            return super().import_patrols(wrapped, stop)

    m = Deleting(per_patrol_seconds=31, clock=clock)   # each patrol crosses the 30 s push cycle
    runner = load_job.Runner(store, id, "run", work=tmp / "work", migration_factory=lambda **kw: m,
                             check_token=lambda h, t: "ops", clock=clock, env={"LOAD_SOFT_DEADLINE_SECONDS": "1000"})
    assert runner.run() == 0
    assert m.done == {"u1", "u2"}             # stopped before the third patrol
    assert store.get_load(id) is None and store.get_load_file(ds, id, "log.txt") is None
    assert "load deleted; stopping" in runner.log_lines
    assert not any(line.startswith("error:") for line in runner.log_lines)


def _updates(env, monkeypatch):
    """Every update_load call the job makes, in order."""
    store = env[0]
    import copy
    calls, real = [], store.update_load
    monkeypatch.setattr(store, "update_load", lambda id, **f: calls.append(copy.deepcopy(f)) or real(id, **f))
    return calls


def test_stages_record_status_times_and_metrics(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, _ = _run(env, "run", m, "queued")
    assert load["status"] == "done"
    st = load["stages"]
    assert list(st) == ["datamodel", "patrol_datamodel", "preflight", "import"]
    assert all(r["status"] == "done" and r["started_at"] <= r["finished_at"] for r in st.values())
    assert st["datamodel"]["metrics"] == {"event_types_created": 2, "event_types_unchanged": 0}
    assert st["patrol_datamodel"]["metrics"] == {"schema_written": True, "subjects_grouped": 1}
    assert st["preflight"]["metrics"] == {"blocking": 0, "warnings": 0, "patrols": 3}
    assert st["import"]["metrics"] == {"imported": 3, "failed": 0, "skipped": 0}


def test_a_plan_records_its_stages_too(env):
    rc, load, _ = _run(env, "plan", FakeMigration(), "planning")
    assert load["status"] == "planned" and [r["status"] for r in load["stages"].values()] == ["done"] * 4
    assert load["mode"] == "plan"
    assert load["stages"]["import"]["metrics"] == {"planned": 3, "already_done": 0}


def test_a_stop_marks_its_stage_stopped_and_leaves_the_rest_out(env):
    rc, load, _ = _run(env, "run", FakeMigration(checklist=[TEAM]), "queued")
    assert load["status"] == "needs_attention"
    assert [(s, r["status"]) for s, r in load["stages"].items()] == [("datamodel", "done"), ("patrol_datamodel", "stopped")]
    assert load["stages"]["patrol_datamodel"]["finished_at"]


def test_an_exception_marks_its_stage_failed(env):
    rc, load, _ = _run(env, "run", FakeMigration(raise_in="preflight"), "queued")
    assert load["status"] == "failed" and load["stages"]["preflight"]["status"] == "failed"


def test_a_rejected_token_stops_the_first_stage(env):
    def reject(host, token):
        raise sys.modules["er_site"].TokenRejected("401")
    rc, load, _ = _run(env, "run", FakeMigration(), "queued", check_token=reject)
    assert load["stages"] == {"datamodel": {**load["stages"]["datamodel"], "status": "stopped"}}


def test_a_new_execution_starts_its_stages_afresh(env, monkeypatch):
    calls = _updates(env, monkeypatch)
    old = {"datamodel": {"status": "done", "started_at": "x", "finished_at": "y", "metrics": {}}}
    rc, load, _ = _run(env, "plan", FakeMigration(), "planning", stages=old, stage="import", progress={"done": 120, "patrols_total": 500})
    assert load["stages"]["datamodel"]["started_at"] != "x"
    first = next(c for c in calls if c.get("status") == "running")
    assert first["stages"] == {} and first["stage"] is None and first["progress"] is None
    assert load["progress"] is None   # a plan imports nothing: the old run's counts do not show under it


def test_the_log_tail_is_recorded_as_the_job_goes(env, monkeypatch):
    calls = _updates(env, monkeypatch)
    clock = Clock()
    _run(env, "run", FakeMigration(per_patrol_seconds=31, clock=clock), "queued", clock=clock)
    staged = [c for c in calls if c.get("stage")]
    assert staged and all(c.get("log_tail") for c in staged)
    progress = [c for c in calls if "progress" in c]
    assert any(c.get("log_tail") for c in progress)          # with the periodic (30 s) write
    assert not all(c.get("log_tail") for c in progress)      # not with every patrol


def test_failed_patrols_leave_the_import_row_done(env):
    rc, load, _ = _run(env, "run", FakeMigration(failed={"u2": "boom"}), "queued")
    assert load["status"] == "needs_attention"
    assert load["stages"]["import"]["status"] == "done" and load["stages"]["import"]["metrics"] == {"imported": 2, "failed": 1, "skipped": 0}


def test_a_continuation_leaves_the_import_row_running(env, monkeypatch):
    store = env[0]
    monkeypatch.setattr(store, "start_load", lambda id, mode: "exec-2")
    clock = Clock()
    rc, load, _ = _run(env, "run", FakeMigration(per_patrol_seconds=60, clock=clock), "queued", clock=clock)
    assert load["status"] == "continuing" and load["stages"]["import"]["status"] == "running"


def test_live_progress_names_the_phase(env, monkeypatch):
    calls = _updates(env, monkeypatch)
    _run(env, "run", FakeMigration(), "queued")
    live = [c["progress"] for c in calls if c.get("progress") and c["progress"].get("phase")]
    assert [p["phase"] for p in live][0] == "events" and live[-1]["phase"] == "tracks"
    starts = {p["phase"]: p["phase_started_at"] for p in live}
    assert starts["events"] <= starts["tracks"]
    assert all(p["patrols_total"] == 3 for p in live)


def test_a_phase_change_is_written_at_once(env, monkeypatch):
    calls = _updates(env, monkeypatch)
    _run(env, "run", FakeMigration(), "queued")   # the clock never moves: no periodic write is due
    live = [c["progress"] for c in calls if c.get("progress") and c["progress"].get("phase")]
    first_tracks = next(p for p in live if p["phase"] == "tracks")
    assert first_tracks["done"] == 0


def test_the_final_progress_carries_no_phase(env):
    rc, load, _ = _run(env, "run", FakeMigration(), "queued")
    assert "phase" not in load["progress"] and "phase_started_at" not in load["progress"]


def test_the_network_timeout_is_set(env, monkeypatch):
    load_job = env[1]
    seen = []
    monkeypatch.setattr(load_job, "bound_http_timeouts", seen.append)
    _run(env, "run", FakeMigration(), "queued")
    _run(env, "run", FakeMigration(), "queued", env_vars={"LOAD_NETWORK_TIMEOUT_SECONDS": "42"})
    assert seen == [600.0, 42.0]


@pytest.fixture
def stalled_server():
    """A server that accepts connections and never answers."""
    import socket
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    held = []

    def accept():
        try:
            while True:
                held.append(srv.accept())
        except OSError:   # closed at teardown
            pass

    threading.Thread(target=accept, daemon=True).start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}"
    for conn, _ in held:
        conn.close()
    srv.close()


@pytest.mark.parametrize("how", ["session", "module"])   # erclient posts JSON on a session and files with requests.post
def test_a_stalled_response_times_out(env, monkeypatch, stalled_server, how):
    import socket
    import time
    import requests
    load_job = env[1]
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", requests.adapters.HTTPAdapter.send)   # restored after the test
    monkeypatch.setattr(socket, "getdefaulttimeout", socket.getdefaulttimeout)
    old = socket.getdefaulttimeout()
    try:
        load_job.bound_http_timeouts(0.5)
        post = requests.Session().post if how == "session" else requests.post
        t0 = time.monotonic()
        with pytest.raises(requests.exceptions.Timeout):
            post(stalled_server + "/api/v1.0/activity/events", data="[]")
        assert time.monotonic() - t0 < 5
    finally:
        socket.setdefaulttimeout(old)


def test_a_caller_s_own_timeout_is_kept(env, monkeypatch):
    import requests
    load_job = env[1]
    seen = []
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", lambda self, request, **kw: seen.append(kw.get("timeout")))
    import socket
    old = socket.getdefaulttimeout()
    try:
        load_job.bound_http_timeouts(30)
        adapter = requests.adapters.HTTPAdapter()
        adapter.send(None, timeout=None)
        adapter.send(None, timeout=7)
        adapter.send(None)
        load_job.bound_http_timeouts(30)   # a second call does not stack another wrapper
        adapter.send(None, timeout=None)
    finally:
        socket.setdefaulttimeout(old)
    assert seen == [30, 7, 30, 30]


def test_load_workers_reach_the_migration(env):
    _, _, seen = _run(env, "run", FakeMigration(), "queued")
    assert seen["workers"] == 1
    _, _, seen = _run(env, "run", FakeMigration(), "queued", env_vars={"LOAD_WORKERS": "3"})
    assert seen["workers"] == 3


def test_live_progress_carries_the_phase_skipped_count(env, monkeypatch):
    calls = _updates(env, monkeypatch)
    m = FakeMigration()
    m.phase_skipped = {"events": 2}
    _run(env, "run", m, "queued")
    live = [c["progress"] for c in calls if c.get("progress") and c["progress"].get("phase") == "events"]
    assert live[-1]["phase_skipped"] == 2


DM_ONLY = {"language": "en", "configurable_model": None, "roster_group": "Rangers", "scope": "datamodel"}


def test_a_data_model_load_stops_after_patrol_setup(env):
    m = FakeMigration()
    rc, load, _ = _run(env, "run", m, "queued", options=DM_ONLY)
    assert rc == 0 and load["status"] == "done" and load["stage"] == "patrol_datamodel"
    assert m.calls == ["push_datamodel", "patrol_datamodel"]
    assert set(load["stages"]) == {"datamodel", "patrol_datamodel"}
    assert all(r["status"] == "done" for r in load["stages"].values())
    assert load["progress"] is None


def test_a_data_model_plan_has_no_patrols(env):
    m = FakeMigration(checklist=[ICONS])
    rc, load, _ = _run(env, "plan", m, "planning", options=DM_ONLY)
    assert load["status"] == "planned" and load["stage"] == "patrol_datamodel"
    assert m.calls == ["push_datamodel", "patrol_datamodel"]
    assert "patrols" not in load["plan"] and "event_types" in load["plan"]
    assert [f["code"] for f in load["findings"]] == ["patrol_type_icons"]


def test_a_data_model_load_still_stops_on_what_the_site_needs(env):
    m = FakeMigration(checklist=[TEAM])
    rc, load, _ = _run(env, "run", m, "queued", options=DM_ONLY)
    assert load["status"] == "needs_attention" and load["stage"] == "patrol_datamodel"


def test_a_windowed_load_counts_only_its_patrols(env):
    class Windowed(FakeMigration):
        def patrols(self):
            return PATROLS[1:]   # the migration applies the window
    rc, load, _ = _run(env, "plan", Windowed(), "planning")
    assert load["plan"]["patrols"]["total"] == 2 and load["plan"]["patrols"]["first"] == "2019-03-05"
