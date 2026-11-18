"""Support view: the addresses in SUPPORT_EMAILS can see every dataset, site and load, and change none.
"Can read" lets a person start, run and delete loads, which write to EarthRanger with the site owner's
token, so support view is a weaker permission that only routes that read accept."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
SUP = {"X-Dev-User": "sup@earthranger.com"}
OTHER = {"X-Dev-User": "other@earthranger.com"}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Alpha", "languages": ["en"], "default_language": "en",
           "configurable_models": [], "patrols": 3}]
WHEN = {"created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00"}
TOKEN = "tok-secret-1234"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SUPPORT_EMAILS", "sup@earthranger.com")
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    yield app, TestClient(app.app)
    for m in ("app", "store", "auth", "er_site"):   # the next test file imports them under its own environment
        sys.modules.pop(m, None)


def seed(app, tmp_path) -> dict:
    """A ready dataset, a site and a load of one into the other, all the owner's."""
    store = app.get_store()
    ds = store.create({"name": "x", "source_name": "backup.zip", "status": "ready", "export": EXPORT,
                       "log_tail": "extract log", **WHEN, **OWNER})
    b = store._p(ds) / "export" / "ALPHA" / "bundle"
    b.mkdir(parents=True)
    (b / "manifest.json").write_text("{}")
    upload = store.upload_path(ds, "backup.zip")
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_bytes(b"zip")
    site = store.create_site({"name": "s", "url": "example.pamdas.org", "token_hint": TOKEN[-4:], "checked_as": "migration",
                              **WHEN, **OWNER}, TOKEN)
    load = store.create_load({"dataset_id": ds, "ca_id": "ALPHA", "site_id": site, "status": "planned", "stage": None,
                              "options": {"language": "en", "configurable_model": None, "roster_group": None},
                              "continuations": 0, **WHEN, **OWNER})
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    store.put_load_file(ds, load, "plan.json", plan)
    return {"ds": ds, "site": site, "load": load}


def reads(ids) -> list:
    return [f"/api/datasets/{ids['ds']}", f"/api/datasets/{ids['ds']}/loads", f"/api/loads/{ids['load']}",
            f"/api/loads/{ids['load']}/files/plan.json", f"/d/{ids['ds']}/", f"/d/{ids['ds']}/index.html"]


def test_me_says_who_is_support(client):
    _, c = client
    assert c.get("/api/me", headers=SUP).json()["support"] is True
    assert c.get("/api/me", headers=OTHER).json()["support"] is False
    assert c.get("/api/me").json()["support"] is False


def test_all_lists_everything_for_support_only(client, tmp_path):
    app, c = client
    ids = seed(app, tmp_path)
    assert c.get("/api/datasets", headers=SUP).json() == [] and c.get("/api/sites", headers=SUP).json() == []
    [d] = c.get("/api/datasets?all=1", headers=SUP).json()
    assert d["id"] == ids["ds"] and d["access"] == "support" and d["mine"] is False
    r = c.get("/api/sites?all=1", headers=SUP)
    [s] = r.json()
    assert s["id"] == ids["site"] and s["access"] == "support" and s["token_hint"] is None and s["checked_as"] == "migration"
    assert "tok-secret" not in r.text and "1234" not in r.text
    for path in ("/api/datasets?all=1", "/api/sites?all=1"):   # the parameter means nothing from anyone else
        r = c.get(path, headers=OTHER)
        assert r.status_code == 200 and r.json() == []
    [mine] = c.get("/api/sites").json()
    assert mine["token_hint"] == "1234" and mine["access"] == "owner"
    assert c.get("/api/datasets").json()[0]["access"] == "owner"


def test_support_opens_every_read_route(client, tmp_path):
    app, c = client
    ids = seed(app, tmp_path)
    for path in reads(ids):
        assert c.get(path, headers=SUP).status_code == 200, path
    d = c.get(f"/api/datasets/{ids['ds']}", headers=SUP).json()
    assert d["access"] == "support" and d["mine"] is False and d["log_tail"] == "extract log"
    assert [l["access"] for l in c.get(f"/api/datasets/{ids['ds']}/loads", headers=SUP).json()] == ["support"]
    l = c.get(f"/api/loads/{ids['load']}", headers=SUP).json()
    assert l["access"] == "support" and l["mine"] is False
    assert c.get(f"/api/loads/{ids['load']}").json()["access"] == "owner"


def test_a_stranger_still_gets_404(client, tmp_path):
    app, c = client
    ids = seed(app, tmp_path)
    for path in reads(ids):
        assert c.get(path, headers=OTHER).status_code == 404, path


def test_a_reader_does_not_get_the_log(client, tmp_path):
    app, c = client
    ids = seed(app, tmp_path)
    assert c.post(f"/api/datasets/{ids['ds']}/share", json={"email": "other@earthranger.com"}).status_code == 200
    d = c.get(f"/api/datasets/{ids['ds']}", headers=OTHER).json()
    assert d["access"] == "shared" and "log_tail" not in d


def test_support_keeps_owner_and_reader_rights(client, tmp_path):
    app, c = client
    ids = seed(app, tmp_path)
    own = c.post("/api/datasets", json={"name": "mine", "filename": "b.zip", "size": 3, "content_type": "application/zip"},
                 headers=SUP).json()["id"]
    assert c.get(f"/api/datasets/{own}", headers=SUP).json()["access"] == "owner"
    assert c.post(f"/api/datasets/{own}/share", json={"email": "other@earthranger.com"}, headers=SUP).status_code == 200
    assert c.post(f"/api/datasets/{ids['ds']}/share", json={"email": "sup@earthranger.com"}).status_code == 200
    assert c.get(f"/api/datasets/{ids['ds']}", headers=SUP).json()["access"] == "shared"
    assert c.get(f"/api/loads/{ids['load']}", headers=SUP).json()["access"] == "shared"
    assert c.delete(f"/api/loads/{ids['load']}", headers=SUP).status_code == 200   # a reader may, as before


# Every route that is not a GET, and what support view gets from it. "own" makes or ends something of the
# caller's own; every other entry is tried as support against the owner's dataset, site and load and must
# be refused. A route added later fails the test below until it has an entry here.
OWN = "own"
WRITES = {
    ("POST", "/api/session"): OWN,
    ("POST", "/api/signout"): OWN,
    ("POST", "/api/datasets"): OWN,
    ("POST", "/api/sites"): OWN,
    ("PUT", "/api/datasets/{id}/upload"): lambda c, i: c.put(f"/api/datasets/{i['ds']}/upload", content=b"x", headers=SUP),
    ("POST", "/api/datasets/{id}/extract"): lambda c, i: c.post(f"/api/datasets/{i['ds']}/extract", headers=SUP),
    ("DELETE", "/api/datasets/{id}/upload"): lambda c, i: c.delete(f"/api/datasets/{i['ds']}/upload", headers=SUP),
    ("DELETE", "/api/datasets/{id}"): lambda c, i: c.delete(f"/api/datasets/{i['ds']}", headers=SUP),
    ("POST", "/api/datasets/{id}/share"): lambda c, i: c.post(f"/api/datasets/{i['ds']}/share", json={"email": "sup@earthranger.com"}, headers=SUP),
    ("DELETE", "/api/datasets/{id}/share/{email}"): lambda c, i: c.delete(f"/api/datasets/{i['ds']}/share/dev@earthranger.com", headers=SUP),
    ("PATCH", "/api/sites/{id}"): lambda c, i: c.patch(f"/api/sites/{i['site']}", json={"name": "taken"}, headers=SUP),
    ("DELETE", "/api/sites/{id}"): lambda c, i: c.delete(f"/api/sites/{i['site']}", headers=SUP),
    ("POST", "/api/sites/{id}/share"): lambda c, i: c.post(f"/api/sites/{i['site']}/share", json={"email": "sup@earthranger.com"}, headers=SUP),
    ("DELETE", "/api/sites/{id}/share/{email}"): lambda c, i: c.delete(f"/api/sites/{i['site']}/share/dev@earthranger.com", headers=SUP),
    ("POST", "/api/datasets/{id}/loads"): lambda c, i: c.post(f"/api/datasets/{i['ds']}/loads", json={"ca_id": "ALPHA", "site_id": i["site"], "options": {}}, headers=SUP),
    ("POST", "/api/loads/{id}/run"): lambda c, i: c.post(f"/api/loads/{i['load']}/run", headers=SUP),
    ("POST", "/api/loads/{id}/replan"): lambda c, i: c.post(f"/api/loads/{i['load']}/replan", headers=SUP),
    ("DELETE", "/api/loads/{id}"): lambda c, i: c.delete(f"/api/loads/{i['load']}", headers=SUP),
}


def test_every_write_route_is_refused_through_support_view(client, tmp_path, monkeypatch):
    app, c = client
    from fastapi.routing import APIRoute

    ids = seed(app, tmp_path)
    store = app.get_store()
    monkeypatch.setattr(store, "start_load", lambda *a, **k: pytest.fail("a load was started"))
    monkeypatch.setattr(store, "start_extract", lambda *a, **k: pytest.fail("an extraction was started"))

    def state():
        return json.dumps([store.get(ids["ds"]), store.get_site(ids["site"]), store.get_load(ids["load"]),
                           store.list_loads(ids["ds"]), store.upload_exists(ids["ds"], "backup.zip")], sort_keys=True, default=str)

    before = state()
    found = {(m, r.path) for r in app.app.routes if isinstance(r, APIRoute) for m in r.methods - {"GET", "HEAD", "OPTIONS"}}
    assert found - set(WRITES) == set(), "decide what support view gets from these routes, and add them to WRITES"
    assert set(WRITES) - found == set(), "these routes are gone; remove them from WRITES"
    for key, call in WRITES.items():
        if call is OWN:
            continue
        r = call(c, ids)
        assert r.status_code in (403, 404), (key, r.status_code, r.text)
        assert state() == before, key
    assert store.read_site_token(ids["site"]) == TOKEN


# ---- the record: a support view of someone else's data is logged, once in ten minutes
def records(caplog) -> list:
    return [r.getMessage() for r in caplog.records if r.name == "support"]


def test_a_support_view_is_recorded_once_in_ten_minutes(client, tmp_path, caplog, monkeypatch):
    app, c = client
    ids = seed(app, tmp_path)
    with caplog.at_level("INFO", logger="support"):
        for path in (f"/api/datasets/{ids['ds']}", f"/api/datasets/{ids['ds']}", f"/api/datasets/{ids['ds']}/loads"):
            assert c.get(path, headers=SUP).status_code == 200
        assert records(caplog) == [f"support_view viewer=sup@earthranger.com kind=dataset id={ids['ds']} owner=dev@earthranger.com"]
        later = app.time.monotonic() + app.SUPPORT_LOG_EVERY_SECONDS + 1
        monkeypatch.setattr(app.time, "monotonic", lambda: later)
        c.get(f"/api/datasets/{ids['ds']}", headers=SUP)
        assert len(records(caplog)) == 2


def test_the_record_covers_each_kind(client, tmp_path, caplog):
    app, c = client
    ids = seed(app, tmp_path)
    with caplog.at_level("INFO", logger="support"):
        for path in ("/api/datasets?all=1", "/api/sites?all=1", "/api/datasets?all=1", f"/api/loads/{ids['load']}",
                     f"/api/loads/{ids['load']}/files/plan.json", f"/d/{ids['ds']}/", f"/d/{ids['ds']}/index.html"):
            assert c.get(path, headers=SUP).status_code == 200
    kinds = [m.split()[2] for m in records(caplog)]
    assert kinds == ["kind=list", "kind=list", "kind=load", "kind=load_file", "kind=browser"]
    assert f"id={ids['load']}/plan.json" in records(caplog)[3]
    assert TOKEN not in caplog.text and "1234" not in caplog.text


def test_no_record_for_an_owner_a_reader_or_a_plain_list(client, tmp_path, caplog):
    app, c = client
    ids = seed(app, tmp_path)
    c.post(f"/api/datasets/{ids['ds']}/share", json={"email": "sup@earthranger.com"})
    with caplog.at_level("INFO", logger="support"):
        for path in reads(ids):
            assert c.get(path).status_code == 200                 # the owner
            assert c.get(path, headers=SUP).status_code == 200    # support, but shared on this one
        c.get("/api/datasets", headers=SUP)                       # their own list
        c.get("/api/datasets?all=1", headers=OTHER)               # not support: the parameter is ignored
        c.get(f"/api/datasets/{ids['ds']}", headers=OTHER)        # a stranger's 404
    assert records(caplog) == []


def test_the_record_reaches_the_service_output(client):
    """The record is logged at INFO, which Python drops unless asked: its logger asks, and the line is
    printed once, by the handler the service sets up (logging.basicConfig in app.py)."""
    import logging

    app, _ = client
    log = logging.getLogger("support")
    assert log is app._support_log and log.isEnabledFor(logging.INFO)
    assert log.propagate and not log.handlers   # one line each, through the service's own handler
