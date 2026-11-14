# tests/test_job.py — the extraction job's run loop, with the store and the child process faked
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))
import job  # noqa: E402


class FakeStore:
    def __init__(self, fail_live=False):
        self.doc, self.fail_live, self.live_attempts = {"source_name": "b.zip"}, fail_live, 0

    def get(self, id):
        return self.doc

    def update(self, id, **fields):
        if set(fields) == {"log_tail"}:  # the periodic live-log write
            self.live_attempts += 1
            if self.fail_live:
                raise RuntimeError("firestore unavailable")
        self.doc.update(fields)

    def fetch_upload(self, id, name, dest):
        return dest / name

    def put_site(self, id, site):
        self.doc["site_published"] = True

    def put_export(self, id, export_dir):
        pass


class FakeProc:
    def __init__(self, lines, rc=0, raise_after=None):
        self.lines, self.rc, self.raise_after = lines, rc, raise_after
        self.running, self.terminated = True, False

    @property
    def stdout(self):
        for i, line in enumerate(self.lines):
            if self.raise_after is not None and i == self.raise_after:
                raise OSError("pipe broke")
            yield line + "\n"

    def wait(self, timeout=None):
        self.running = False
        return self.rc

    def poll(self):
        return None if self.running else self.rc

    def terminate(self):
        self.terminated = True


@pytest.fixture
def run(tmp_path, monkeypatch):
    def go(store, proc):
        site = tmp_path / "out" / "site" / "data"
        site.mkdir(parents=True)
        (site / "meta.json").write_text(json.dumps([{"cas": [{"id": "050500", "n": "Albay"}], "db_version": "7.5.4", "patrols": 3}]))
        monkeypatch.setenv("JOB_WORK_DIR", str(tmp_path))
        monkeypatch.setenv("JOB_KEEP_WORK", "1")
        monkeypatch.setattr(job, "get_store", lambda: store)
        monkeypatch.setattr(job, "LIVE_TAIL_EVERY", 0)
        monkeypatch.setattr(job.subprocess, "Popen", lambda *a, **k: proc)
        return job.main("d1")
    return go


def test_the_running_job_publishes_its_log_as_it_goes(run):
    store = FakeStore()
    assert run(store, FakeProc(["one", "two"])) == 0
    assert store.live_attempts == 2 and store.doc["status"] == "ready" and store.doc["log_tail"] == "one\ntwo"


def test_a_failed_live_log_write_does_not_fail_the_extraction(run, capsys):
    store, proc = FakeStore(fail_live=True), FakeProc(["one", "two", "three"])
    assert run(store, proc) == 0
    assert store.live_attempts == 3, "each interval tries again"
    assert store.doc["status"] == "ready" and store.doc["site_published"] and store.doc["log_tail"] == "one\ntwo\nthree"
    assert not proc.terminated
    assert "live log not published" in capsys.readouterr().err


def test_an_abandoned_run_stops_its_child_before_the_work_goes(run):
    store, proc = FakeStore(), FakeProc(["one", "two"], raise_after=1)
    with pytest.raises(OSError):
        run(store, proc)
    assert proc.terminated and not proc.running, "terminated and waited for"
    assert store.doc["status"] == "failed" and "pipe broke" in store.doc["error"]
