"""Loads: one attempt to put a conservation area into a site. Claims and
holds work as for extraction; a dataset's loads go with it."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
           "configurable_models": [{"uuid": "abc", "label": "Mobile"}], "patrols": 3, "timezone": "Asia/Manila"}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def _dataset(store, export=EXPORT, status="ready"):
    id = store.create({"name": "x", "source_name": "backup.zip", "status": status, "export": export,
                       "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    if export:
        b = store._p(id) / "export" / "ALPHA" / "bundle"
        b.mkdir(parents=True)
        (b / "manifest.json").write_text("{}")
    return id


def _site(store):
    return store.create_site({"name": "s", "url": "x.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")


def _load(store, dataset_id, site_id, status="planned", **extra):
    return store.create_load({"dataset_id": dataset_id, "ca_id": "ALPHA", "site_id": site_id, "status": status,
                              "stage": None, "options": {"language": "en", "configurable_model": None, "roster_group": None},
                              "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00",
                              "continuations": 0, **OWNER, **extra})


def test_claim_admits_exactly_one_of_many(client):
    app, _ = client
    store = app.get_store()
    id = _load(store, _dataset(store), _site(store))
    results, start = [], threading.Barrier(16)

    def claim():
        start.wait()
        results.append(store.claim_load(id, "queued"))

    threads = [threading.Thread(target=claim) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert store.get_load(id)["status"] == "queued" and store.get_load(id)["claimed_at"]


@pytest.mark.parametrize("status, anchor", [("running", "started_at"), ("queued", "claimed_at"),
                                            ("planning", "claimed_at"), ("continuing", "claimed_at")])
def test_a_stale_hold_lapses(client, status, anchor):
    app, _ = client
    store = app.get_store()
    old = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat(timespec="seconds")
    id = _load(store, _dataset(store), _site(store), status=status, **{anchor: old})
    assert sys.modules["store"].load_in_progress(store.get_load(id)) is False
    assert store.claim_load(id, "queued") is True


def test_a_fresh_hold_refuses(client):
    app, _ = client
    store = app.get_store()
    id = _load(store, _dataset(store), _site(store), status="running",
               started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert store.claim_load(id, "queued") is False


def test_load_files_round_trip_and_go_with_the_load(client, tmp_path):
    app, _ = client
    store = app.get_store()
    ds = _dataset(store)
    id = _load(store, ds, _site(store))
    src = tmp_path / "plan.json"
    src.write_text('{"patrols": {"total": 3}}')
    store.put_load_file(ds, id, "plan.json", src)
    chunks, size, ctype = store.get_load_file(ds, id, "plan.json")
    assert b"".join(chunks) == src.read_bytes() and ctype == "application/json"
    fetched = store.fetch_load_dir(ds, id, tmp_path / "fetched")
    assert (fetched / "plan.json").is_file()
    store.delete_load(id)
    assert store.get_load(id) is None and store.get_load_file(ds, id, "plan.json") is None


def test_deleting_a_dataset_deletes_its_loads(client):
    app, c = client
    store = app.get_store()
    ds = _dataset(store)
    id = _load(store, ds, _site(store), status="running",
               started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert c.delete(f"/api/datasets/{ds}").status_code == 200
    assert store.get_load(id) is None and store.list_loads(ds) == []


def test_start_load_runs_the_job_with_its_mode(client, monkeypatch):
    app, _ = client
    store = app.get_store()
    seen = {}
    monkeypatch.setattr(store, "load_job_command", lambda id, mode: [sys.executable, "-c",
                        f"import pathlib; pathlib.Path({str(store.dir / 'ran')!r}).write_text({mode!r})"])
    id = _load(store, _dataset(store), _site(store))
    assert store.start_load(id, "plan") == "local-thread"
    import time
    deadline = time.time() + 5
    while time.time() < deadline and not (store.dir / "ran").exists():
        time.sleep(0.05)
    assert (store.dir / "ran").read_text() == "plan"
