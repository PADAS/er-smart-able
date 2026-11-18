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
