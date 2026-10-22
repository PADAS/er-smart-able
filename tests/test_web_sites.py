"""Sites: the EarthRanger targets a load writes to. The token lives only in
the secret store; the doc keeps a hint."""
from __future__ import annotations

import importlib
import sys
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
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def test_create_site_keeps_the_token_out_of_the_index(client, tmp_path):
    app, _ = client
    store = app.get_store()
    id = store.create_site({"name": "phinney", "url": "phinney.staging.pamdas.org", **OWNER}, "tok-secret-1234")
    doc = store.get_site(id)
    assert doc["secret_name"] == f"smart-able-site-{id}" and "tok-secret" not in str(doc)
    assert "tok-secret" not in (tmp_path / "data" / "sites.json").read_text()
    assert store.read_site_token(id) == "tok-secret-1234"
    assert oct((tmp_path / "data" / "secrets" / doc["secret_name"]).stat().st_mode)[-3:] == "600"


def test_delete_site_removes_the_secret(client):
    app, _ = client
    store = app.get_store()
    id = store.create_site({"name": "x", "url": "x.pamdas.org", **OWNER}, "t")
    store.delete_site(id)
    assert store.get_site(id) is None
    with pytest.raises(KeyError):
        store.read_site_token(id)
