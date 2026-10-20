"""Starting an extraction claims the dataset first, so two requests cannot
launch two jobs that write the same site."""
from __future__ import annotations

import importlib
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def _dataset(store, status="uploaded", updated_at=None, upload=True):
    id = store.create({"name": "x", "source_name": "backup.zip", "status": status,
                       "updated_at": updated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"), **OWNER})
    if upload:
        p = store.upload_path(id, "backup.zip")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"zip")
    return id


@pytest.fixture
def launches(client, monkeypatch):
    app, _ = client
    calls = []
    monkeypatch.setattr(app.get_store(), "start_extract", lambda id: calls.append(id) or "exec-1")
    return calls


def test_a_second_request_while_queued_is_refused(client, launches):
    app, c = client
    id = _dataset(app.get_store())
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200
    r = c.post(f"/api/datasets/{id}/extract")
    assert r.status_code == 409
    assert launches == [id]
    assert app.get_store().get(id)["status"] == "queued"


def test_concurrent_claims_admit_exactly_one(client):
    app, _ = client
    store = app.get_store()
    id = _dataset(store)
    results, start = [], threading.Barrier(16)

    def claim():
        start.wait()
        results.append(store.claim_extract(id))

    threads = [threading.Thread(target=claim) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1


def test_a_hold_older_than_the_job_timeout_lapses(client, launches):
    app, c = client
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
    id = _dataset(app.get_store(), status="running", updated_at=old)
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200
    assert launches == [id]


def test_a_job_that_fails_to_start_releases_the_hold(client, monkeypatch):
    app, c = client
    store = app.get_store()
    id = _dataset(store)

    def broken(id):
        raise RuntimeError("quota")

    monkeypatch.setattr(store, "start_extract", broken)
    assert c.post(f"/api/datasets/{id}/extract").status_code == 502
    assert store.get(id)["status"] == "failed"
    monkeypatch.setattr(store, "start_extract", lambda id: "exec-2")
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200


def test_a_missing_upload_leaves_the_status_alone(client, launches):
    app, c = client
    id = _dataset(app.get_store(), status="uploading", upload=False)
    assert c.post(f"/api/datasets/{id}/extract").status_code == 400
    assert app.get_store().get(id)["status"] == "uploading"
    assert launches == []


def test_the_list_says_when_a_dataset_is_held(client, launches):
    app, c = client
    store = app.get_store()
    fresh = _dataset(store)
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
    stale = _dataset(store, status="running", updated_at=old)
    c.post(f"/api/datasets/{fresh}/extract")
    held = {d["id"]: d["extract_held"] for d in c.get("/api/datasets").json()}
    assert held == {fresh: True, stale: False}


@pytest.mark.parametrize("status, anchor", [("running", "started_at"), ("queued", "extract_claimed_at")])
def test_a_metadata_edit_does_not_renew_a_stale_hold(client, launches, status, anchor):
    app, c = client
    store = app.get_store()
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
    id = _dataset(store, status=status)
    store.update(id, **{anchor: old})
    # sharing rewrites updated_at; the hold is measured from the claim or the job's start
    assert c.post(f"/api/datasets/{id}/share", json={"email": "colleague@earthranger.com"}).status_code == 200
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200
    assert launches == [id]


def test_a_claim_is_measured_from_its_own_time(client, launches):
    app, c = client
    store = app.get_store()
    id = _dataset(store)
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200
    doc = store.get(id)
    assert doc["extract_claimed_at"] and sys.modules["store"].extract_in_progress(doc)


def test_a_local_run_past_the_timeout_is_killed_with_its_children(client, monkeypatch, tmp_path):
    import os
    import time

    app, _ = client
    store = app.get_store()
    monkeypatch.setattr(sys.modules["store"], "EXTRACT_TIMEOUT", timedelta(seconds=1))
    child_pid = tmp_path / "child.pid"
    worker = ("import subprocess, sys, time; "
              "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
              f"open({str(child_pid)!r}, 'w').write(str(c.pid)); time.sleep(60)")
    monkeypatch.setattr(store, "job_command", lambda id: [sys.executable, "-c", worker])
    id = _dataset(store)
    store.start_extract(id)
    deadline = time.time() + 10
    while time.time() < deadline and store.get(id)["status"] != "failed":
        time.sleep(0.1)
    doc = store.get(id)
    assert doc["status"] == "failed" and "timed out" in doc["error"]
    pid = int(child_pid.read_text())
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the worker's child survived the timeout")
