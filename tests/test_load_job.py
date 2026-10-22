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
        self._call("import_patrols")
        imported, stopped_early = [], False
        for i, p in enumerate(PATROLS):
            if stop.is_set():
                stopped_early = True
                break
            if self.clock is not None:
                self.clock.advance(self.per_patrol_seconds)
            if p["uuid"] not in self.failed:
                imported.append(p["uuid"]); self.done.add(p["uuid"])
            progress({"total": len(PATROLS), "done": i + 1, "failed": sum(1 for u in self.failed if u in [q["uuid"] for q in PATROLS[:i + 1]]), "already_imported": 0})
        return {"imported": imported, "failed": dict(self.failed), "stopped_early": stopped_early}


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


def _run(env, mode, migration, status, clock=None, env_vars=None, check_token=lambda host, token: "ops"):
    store, load_job, ds, site, tmp = env
    id = _load(store, ds, site, status)
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
        if "progress" in fields and not raised:
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
