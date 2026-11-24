"""The uploaded backup: when it expires, deleting it early, and what that leaves."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")

OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
OTHER = {"owner_email": "someone@earthranger.com", "owner_uid": "someone", "shared_with": ["dev@earthranger.com"]}


def make(tmp_path, monkeypatch, days=None):
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    if days is None:
        monkeypatch.delenv("UPLOAD_RETENTION_DAYS", raising=False)
    else:
        monkeypatch.setenv("UPLOAD_RETENTION_DAYS", str(days))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient
    return app, TestClient(app.app)


def dataset(store, who=OWNER, status="ready", upload=True, **extra):
    id = store.create({"name": "x", "source_name": "backup.zip", "status": status, "export": [],
                       "created_at": "2026-10-21T09:30:00+00:00", "updated_at": "2026-10-21T09:30:00+00:00", **who, **extra})
    site = store._p(id) / "site"; site.mkdir(parents=True); (site / "index.html").write_text("extracted")
    if upload:
        up = store.upload_path(id, "backup.zip"); up.parent.mkdir(parents=True, exist_ok=True); up.write_bytes(b"zip")
    return id


def test_a_dataset_says_whether_its_backup_is_stored_and_when_it_expires(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    id = dataset(app.get_store())
    assert c.get(f"/api/datasets/{id}").json()["upload"] == {"present": True, "expires_at": "2026-11-20T09:30:00+00:00", "deleted_at": None}
    gone = dataset(app.get_store(), upload=False)
    assert c.get(f"/api/datasets/{gone}").json()["upload"]["present"] is False


def test_with_no_retention_the_backup_has_no_expiry(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch)   # the local backend has no rule that deletes it
    id = dataset(app.get_store())
    assert c.get(f"/api/datasets/{id}").json()["upload"] == {"present": True, "expires_at": None, "deleted_at": None}


def test_the_list_does_not_ask_storage_about_every_backup(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    dataset(app.get_store())
    assert "upload" not in c.get("/api/datasets").json()[0]


def test_the_owner_deletes_the_backup_and_the_extracted_data_stays(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store)
    r = c.delete(f"/api/datasets/{id}/upload")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert not store.upload_exists(id, "backup.zip") and (store._p(id) / "site" / "index.html").read_text() == "extracted"
    up = c.get(f"/api/datasets/{id}").json()["upload"]
    assert up["present"] is False and up["deleted_at"] and up["expires_at"] == "2026-11-20T09:30:00+00:00"
    assert c.delete(f"/api/datasets/{id}/upload").status_code == 200, "deleting what is already gone is not an error"
    r = c.post(f"/api/datasets/{id}/extract")
    assert r.status_code == 400 and r.json()["code"] == "upload_incomplete"


def test_only_the_owner_deletes_the_backup(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store, who=OTHER)
    r = c.delete(f"/api/datasets/{id}/upload")
    assert r.status_code == 403 and r.json()["code"] == "owner_only" and store.upload_exists(id, "backup.zip")
    assert c.get(f"/api/datasets/{id}").json()["upload"]["present"] is True, "someone it is shared with still sees its state"


def test_the_backup_is_not_deleted_while_it_is_being_extracted(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store()
    from store import now
    id = dataset(store, status="running", started_at=now())
    r = c.delete(f"/api/datasets/{id}/upload")
    assert r.status_code == 409 and r.json()["code"] == "dataset_extracting" and store.upload_exists(id, "backup.zip")


def test_the_retention_in_the_app_and_in_the_storage_rule_are_one_number():
    tf = (ROOT / "web" / "infra" / "main.tf").read_text()
    assert "age            = var.upload_retention_days" in tf and 'variable "upload_retention_days"' in (ROOT / "web" / "infra" / "variables.tf").read_text()
    assert "UPLOAD_RETENTION_DAYS=${{ vars.UPLOAD_RETENTION_DAYS || 30 }}" in (ROOT / ".github" / "workflows" / "deploy.yml").read_text()


# ---- review of PR 39
def test_deleting_the_backup_and_extracting_cannot_both_go_ahead(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store()
    a = dataset(store)
    assert store.claim_upload_delete(a) is True and store.claim_extract(a) is False, "a reserved deletion keeps an extraction out"
    b = dataset(store)
    assert store.claim_extract(b) is True and store.claim_upload_delete(b) is False, "a claimed extraction keeps the deletion out"
    assert store.upload_exists(b, "backup.zip")


def test_an_extraction_asked_for_while_the_backup_is_being_deleted_is_refused(tmp_path, monkeypatch):
    """The interleaving from review: DELETE has checked, POST /extract arrives, DELETE removes the file."""
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store)
    started, during = [], {}
    monkeypatch.setattr(type(store), "start_extract", lambda self, i: started.append(i) or "x")
    real = type(store).delete_upload

    def slow_delete(self, i, name):   # the extract request lands before the object is gone
        during["r"] = c.post(f"/api/datasets/{i}/extract")
        real(self, i, name)
    monkeypatch.setattr(type(store), "delete_upload", slow_delete)
    assert c.delete(f"/api/datasets/{id}/upload").status_code == 200
    assert during["r"].status_code == 400 and during["r"].json()["code"] == "upload_incomplete"
    assert started == [] and store.get(id)["status"] == "ready" and not store.upload_exists(id, "backup.zip")


def test_of_a_deletion_and_an_extraction_started_together_exactly_one_wins(tmp_path, monkeypatch):
    import threading
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store()
    for _ in range(20):
        id = dataset(store); got = {}
        go = threading.Barrier(2)
        def run(name, fn):
            go.wait(); got[name] = fn(id)
        ts = [threading.Thread(target=run, args=("delete", store.claim_upload_delete)), threading.Thread(target=run, args=("extract", store.claim_extract))]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert sorted(got.values()) == [False, True], got


def test_the_cloud_store_reserves_the_deletion_in_a_transaction():
    src = (ROOT / "web" / "store.py").read_text()
    gcp = src[src.index("class GcpStore"):]
    body = gcp[gcp.index("def claim_upload_delete"):]; body = body[:body.index("\n    def ", 10)]
    assert "@firestore.transactional" in body and "extract_in_progress" in body and "upload_deleted_at" in body
    claim = gcp[gcp.index("def claim_extract"):]; claim = claim[:claim.index("\n    def ", 10)]
    assert "upload_deleted_at" in claim, "an extraction is not claimed once the backup's deletion is reserved"


def test_expiry_is_promised_only_for_a_name_the_storage_rule_deletes(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store()
    from store import EXPIRING_SUFFIXES
    tf = (ROOT / "web" / "infra" / "main.tf").read_text()
    assert 'matches_suffix = [".zip", ".bak"]' in tf and EXPIRING_SUFFIXES == (".zip", ".bak"), "the rule's suffixes, which match by case"
    old = store.create({"name": "x", "source_name": "OLD.ZIP", "status": "ready", "export": [],
                        "created_at": "2026-10-21T09:30:00+00:00", "updated_at": "2026-10-21T09:30:00+00:00", **OWNER})
    up = store.upload_path(old, "OLD.ZIP"); up.parent.mkdir(parents=True); up.write_bytes(b"zip")
    assert c.get(f"/api/datasets/{old}").json()["upload"] == {"present": True, "expires_at": None, "deleted_at": None}, "the rule never matches it: no date"


def test_a_new_upload_is_stored_under_a_name_the_rule_matches(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    r = c.post("/api/datasets", json={"name": "", "filename": "North Zone.BAK.ZIP", "size": 3, "content_type": "application/zip"})
    assert r.status_code == 201
    id = r.json()["id"]
    doc = app.get_store().get(id)
    assert doc["source_name"] == "North Zone.BAK.zip" and doc["name"] == "North Zone.BAK"
    assert c.put(r.json()["upload"]["url"], content=b"zip").status_code in (200, 204)
    assert app.get_store().upload_exists(id, "North Zone.BAK.zip")
    assert c.get(f"/api/datasets/{id}").json()["upload"]["expires_at"]


# ---- uploading a backup again, for a dataset that has one already
def reupload(c, id, name="newer.zip", body=b"newer", size=5):
    r = c.post(f"/api/datasets/{id}/upload", json={"filename": name, "size": size})
    assert r.status_code == 200, r.text
    target = r.json()["upload"]
    assert target["method"] == "PUT" and target["url"] == f"/api/datasets/{id}/upload"
    assert c.put(target["url"], content=body).status_code == 200
    return r


def started(app, monkeypatch):
    calls = []
    monkeypatch.setattr(app.get_store(), "start_extract", lambda id: calls.append(id) or "exec-1")
    return calls


def test_a_backup_uploaded_again_replaces_the_stored_one_when_it_is_extracted(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store); calls = started(app, monkeypatch)
    reupload(c, id, "NEWER.ZIP")
    # sent, and not yet asked to be extracted: the dataset is as it was, its data still there
    doc = store.get(id)
    assert doc["status"] == "ready" and doc["source_name"] == "backup.zip" and store.upload_exists(id, "backup.zip")
    assert c.get(f"/api/datasets/{id}").json()["upload"]["expires_at"] == "2026-11-20T09:30:00+00:00"
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200 and calls == [id]
    doc = store.get(id)
    assert doc["source_name"] == "NEWER.zip", "stored under a name the rule matches"
    assert doc["source_size"] == 5 and doc["status"] == "queued" and not doc.get("pending_source_name")
    assert store.upload_path(id, "NEWER.zip").read_bytes() == b"newer"
    assert not store.upload_exists(id, "backup.zip"), "the file it replaces goes"
    assert (store._p(id) / "site" / "index.html").read_text() == "extracted", "until the extraction replaces it"
    # the rule deletes the new file by its own age, so the date shown counts from the new upload
    from datetime import datetime, timedelta
    up = c.get(f"/api/datasets/{id}").json()["upload"]
    assert up["present"] is True and up["deleted_at"] is None
    assert c.get(f"/api/datasets/{id}").json()["uploaded_at"] == doc["uploaded_at"], "the page says when this backup was uploaded"
    assert datetime.fromisoformat(up["expires_at"]) - datetime.fromisoformat(doc["uploaded_at"]) == timedelta(days=30)


def test_a_backup_that_was_deleted_can_be_uploaded_again_and_extracted(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store); calls = started(app, monkeypatch)
    assert c.delete(f"/api/datasets/{id}/upload").status_code == 200
    assert c.post(f"/api/datasets/{id}/extract").json()["code"] == "upload_incomplete"
    reupload(c, id, "backup.zip", b"again", 5)   # the same name as the one that went
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200 and calls == [id]
    up = c.get(f"/api/datasets/{id}").json()["upload"]
    assert up["present"] is True and up["deleted_at"] is None
    assert store.upload_path(id, "backup.zip").read_bytes() == b"again"


def test_an_upload_that_is_abandoned_changes_nothing(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store); calls = started(app, monkeypatch)
    r = c.post(f"/api/datasets/{id}/upload", json={"filename": "newer.zip", "size": 9})   # and the file never arrives
    assert r.status_code == 200
    up = c.get(f"/api/datasets/{id}").json()
    assert up["upload"]["present"] is True and up["source_name"] == "backup.zip" and up["status"] == "ready"
    # extracting again reads the backup that is stored, as before
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200 and calls == [id]
    assert store.get(id)["source_name"] == "backup.zip" and store.upload_path(id, "backup.zip").read_bytes() == b"zip"


def test_only_the_owner_uploads_a_backup_again_and_only_a_zip(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); theirs = dataset(store, who=OTHER); mine = dataset(store)
    r = c.post(f"/api/datasets/{theirs}/upload", json={"filename": "newer.zip"})
    assert r.status_code == 403 and r.json()["code"] == "owner_only" and not store.get(theirs).get("pending_source_name")
    r = c.post(f"/api/datasets/{mine}/upload", json={"filename": "notes.txt"})
    assert r.status_code == 400 and r.json()["code"] == "upload_not_zip" and not store.get(mine).get("pending_source_name")


def test_no_backup_is_uploaded_again_while_the_dataset_is_extracted_or_loaded(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store()
    from store import now
    busy = dataset(store, status="running", started_at=now())
    r = c.post(f"/api/datasets/{busy}/upload", json={"filename": "newer.zip"})
    assert r.status_code == 409 and r.json()["code"] == "dataset_extracting"
    id = dataset(store)
    store.create_load({"dataset_id": id, "ca_id": "A", "site_id": "s", "status": "running", "started_at": now(),
                       "created_at": now(), "updated_at": now(), **OWNER})
    r = c.post(f"/api/datasets/{id}/upload", json={"filename": "newer.zip"})
    assert r.status_code == 409 and r.json()["code"] == "load_running" and not store.get(id).get("pending_source_name")


def test_an_extraction_under_way_is_not_handed_a_backup_uploaded_meanwhile(tmp_path, monkeypatch):
    app, c = make(tmp_path, monkeypatch, days=30)
    store = app.get_store(); id = dataset(store); calls = started(app, monkeypatch)
    reupload(c, id)
    from store import now
    store.update(id, status="running", started_at=now())   # an extraction of the stored backup began meanwhile
    r = c.post(f"/api/datasets/{id}/extract")
    assert r.status_code == 409 and r.json()["code"] == "extract_active" and calls == []
    assert store.get(id)["source_name"] == "backup.zip" and store.upload_exists(id, "backup.zip"), "the file being read stays"
    store.update(id, status="ready")
    assert c.post(f"/api/datasets/{id}/extract").status_code == 200 and store.get(id)["source_name"] == "newer.zip"
