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


@pytest.fixture
def launches(client, monkeypatch):
    app, _ = client
    calls = []
    monkeypatch.setattr(app.get_store(), "start_load", lambda id, mode: calls.append((id, mode)) or "exec-1")
    return calls


def test_create_load_plans_first(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    r = c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site, "options": {"roster_group": "Rangers"}})
    assert r.status_code == 201, r.text
    load = r.json()
    assert load["status"] == "planning" and load["site"] == {"id": site, "name": "s", "url": "x.pamdas.org"}
    assert load["options"] == {"language": "en", "configurable_model": None, "roster_group": "Rangers"}
    assert launches == [(load["id"], "plan")]
    assert c.get(f"/api/datasets/{ds}/loads").json()[0]["id"] == load["id"]
    assert c.get(f"/api/loads/{load['id']}").json()["held"] is True


def test_create_load_refuses_bad_inputs(client, launches):
    app, c = client
    store = app.get_store()
    site = _site(store)
    no_export = _dataset(store, export=[])
    assert c.post(f"/api/datasets/{no_export}/loads", json={"ca_id": "ALPHA", "site_id": site}).status_code == 400
    ds = _dataset(store)
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "NOPE", "site_id": site}).status_code == 400
    empty = _dataset(store, export=[{**EXPORT[0], "patrols": 0}])
    assert c.post(f"/api/datasets/{empty}/loads", json={"ca_id": "ALPHA", "site_id": site}).status_code == 400
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": "missing"}).status_code == 404
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site, "options": {"language": "xx"}}).status_code == 400
    assert launches == []


def test_a_second_active_load_for_the_same_target_is_refused(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    body = {"ca_id": "ALPHA", "site_id": site}
    assert c.post(f"/api/datasets/{ds}/loads", json=body).status_code == 201
    assert c.post(f"/api/datasets/{ds}/loads", json=body).status_code == 409
    other = _site(store)
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": other}).status_code == 201


def test_run_confirms_a_plan_and_continues_a_stopped_load(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    planned = _load(store, ds, site, status="planned")
    assert c.post(f"/api/loads/{planned}/run").status_code == 200
    assert store.get_load(planned)["status"] == "queued" and launches[-1] == (planned, "run")
    stopped = _load(store, ds, site, status="needs_attention")
    assert c.post(f"/api/loads/{stopped}/run").status_code == 200
    done = _load(store, ds, site, status="done")
    assert c.post(f"/api/loads/{done}/run").status_code == 409
    assert c.post(f"/api/loads/{done}/replan").status_code == 200
    assert store.get_load(done)["status"] == "planning" and launches[-1] == (done, "plan")
    assert c.post(f"/api/loads/{planned}/replan").status_code == 409   # it is queued now


def test_a_removed_site_blocks_run_and_replan(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site, status="needs_attention")
    store.delete_site(site)
    before = store.get_load(id)
    assert c.post(f"/api/loads/{id}/run").status_code == 409
    assert c.post(f"/api/loads/{id}/replan").status_code == 409
    assert store.get_load(id) == before and launches == []
    assert c.get(f"/api/loads/{id}").json()["site"] is None


def test_permissions_follow_the_dataset(client, launches):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site)
    other = {"X-Dev-User": "other@earthranger.com"}
    assert c.get(f"/api/loads/{id}", headers=other).status_code == 404
    assert c.post(f"/api/loads/{id}/run", headers=other).status_code == 404
    c.post(f"/api/datasets/{ds}/share", json={"email": "other@earthranger.com"})
    assert c.get(f"/api/loads/{id}", headers=other).status_code == 200
    # the site is not shared with them, so they cannot start a new load into it
    assert c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site}, headers=other).status_code == 404


def test_delete_and_files(client, tmp_path):
    app, c = client
    store = app.get_store()
    ds, site = _dataset(store), _site(store)
    id = _load(store, ds, site, status="running", started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    assert c.delete(f"/api/loads/{id}").status_code == 409
    store.update_load(id, status="done")
    src = tmp_path / "log.txt"; src.write_text("hello")
    store.put_load_file(ds, id, "log.txt", src)
    assert c.get(f"/api/loads/{id}/files/log.txt").text == "hello"
    assert c.get(f"/api/loads/{id}/files/nope.txt").status_code == 404
    assert c.get(f"/api/loads/{id}/files/..%2Fsecret").status_code in (400, 404)
    assert c.delete(f"/api/loads/{id}").status_code == 200
    assert store.get_load(id) is None
