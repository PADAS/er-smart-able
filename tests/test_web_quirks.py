"""The deployed service serves the docs page from its own build, like the
browser page, so a docs restyle reaches datasets extracted before it."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
pytest.importorskip("fastapi")


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


def test_quirks_page_comes_from_the_service_build(client, tmp_path, monkeypatch):
    app, c = client
    built = tmp_path / "quirks.html"
    built.write_text("<p>current docs</p>")
    monkeypatch.setattr(app, "QUIRKS", built)
    store = app.get_store()
    id = store.create({"name": "x", "owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com",
                       "shared_with": [], "status": "ready"})
    stale = store._p(id) / "site" / "quirks.html"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("<p>stale docs</p>")
    r = c.get(f"/d/{id}/quirks.html")
    assert r.status_code == 200 and "current docs" in r.text
