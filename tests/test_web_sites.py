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


def test_a_failed_index_write_leaves_no_secret_behind(client, tmp_path, monkeypatch):
    app, _ = client
    store = app.get_store()

    def boom(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_write_file", boom)
    with pytest.raises(OSError):
        store.create_site({"name": "x", "url": "x.pamdas.org", **OWNER}, "tok-orphan")
    secrets = tmp_path / "data" / "secrets"
    assert not secrets.exists() or list(secrets.iterdir()) == []


@pytest.fixture
def er(monkeypatch):
    """Stand in for the EarthRanger site: records calls, answers as told."""
    calls = []
    state = {"user": "smart_migration", "reject": False}

    def check(host, token):
        import er_site
        calls.append((host, token))
        if state["reject"]:
            raise er_site.TokenRejected("401 Unauthorized")
        return state["user"]

    monkeypatch.setattr(importlib.import_module("er_site"), "check_token", check)
    monkeypatch.setattr(importlib.import_module("app"), "check_token", check, raising=False)
    return calls, state


@pytest.mark.parametrize("given", ["phinney.staging.pamdas.org", "https://phinney.staging.pamdas.org",
                                   "https://Phinney.staging.pamdas.org/api/v1.0/", "phinney.staging.pamdas.org/"])
def test_register_normalizes_the_url_to_a_host(client, er, given):
    _, c = client
    r = c.post("/api/sites", json={"name": "phinney", "url": given, "token": "abcd1234wxyz"})
    assert r.status_code == 201, r.text
    assert r.json()["url"] == "phinney.staging.pamdas.org"
    assert r.json()["token_hint"] == "wxyz" and r.json()["checked_as"] == "smart_migration"
    assert er[0] == [("phinney.staging.pamdas.org", "abcd1234wxyz")]


def test_the_same_host_can_be_registered_twice(client, er):
    _, c = client
    for t in ("tok-one-aaaa", "tok-two-bbbb"):
        assert c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": t}).status_code == 201
    assert len(c.get("/api/sites").json()) == 2


def test_a_rejected_token_stores_nothing(client, er):
    app, c = client
    er[1]["reject"] = True
    r = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "bad"})
    assert r.status_code == 400 and "401" in r.json()["detail"]
    assert app.get_store().list_sites() == []


def test_a_bad_url_is_a_400(client, er):
    _, c = client
    assert c.post("/api/sites", json={"name": "n", "url": "not a host", "token": "t"}).status_code == 400


def test_sites_are_visible_to_owner_and_shared_only(client, er):
    _, c = client
    id = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "t"}).json()["id"]
    other = {"X-Dev-User": "other@earthranger.com"}
    assert c.get("/api/sites", headers=other).json() == []
    assert c.post(f"/api/sites/{id}/share", json={"email": "other@earthranger.com"}).status_code == 200
    seen = c.get("/api/sites", headers=other).json()
    assert [s["id"] for s in seen] == [id] and seen[0]["mine"] is False
    assert c.delete(f"/api/sites/{id}", headers=other).status_code == 403
    assert c.delete(f"/api/sites/{id}").status_code == 200
    assert c.get("/api/sites").json() == []


def test_the_token_never_appears_in_a_response(client, er):
    _, c = client
    r = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "super-secret-token"})
    assert "super-secret-token" not in r.text and "super-secret-token" not in c.get("/api/sites").text


def test_check_token_reads_the_username(monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")

    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer tok"
        assert str(request.url) == "https://x.pamdas.org/api/v1.0/user/me"
        return httpx.Response(200, json={"data": {"username": "ops", "email": "ops@x"}})

    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(handler))
    assert er_site.check_token("x.pamdas.org", "tok") == "ops"


def test_check_token_distinguishes_rejection_from_unreachable(monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")
    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    with pytest.raises(er_site.TokenRejected):
        er_site.check_token("x.pamdas.org", "tok")
    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(lambda r: httpx.Response(502)))
    with pytest.raises(er_site.SiteUnreachable):
        er_site.check_token("x.pamdas.org", "tok")


def test_a_200_that_is_not_an_earthranger_answer_is_unreachable(monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")
    for resp in (httpx.Response(200, text="<html>"), httpx.Response(200, json=[1])):
        monkeypatch.setattr(er_site, "_transport", lambda resp=resp: httpx.MockTransport(lambda r: resp))
        with pytest.raises(er_site.SiteUnreachable):
            er_site.check_token("x.pamdas.org", "tok")


def test_the_route_answers_400_when_the_site_replies_with_html(client, monkeypatch):
    import httpx
    er_site = importlib.import_module("er_site")
    monkeypatch.setattr(er_site, "_transport", lambda: httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")))
    _, c = client
    r = c.post("/api/sites", json={"name": "n", "url": "x.pamdas.org", "token": "t"})
    assert r.status_code == 400


@pytest.mark.parametrize("bad", ["x.pamdas.org:8080", "user:pass@x.pamdas.org", "https://u@x.pamdas.org",
                                 "169.254.169.254", "http://10.0.0.1/", "127.0.0.1", "localhost", "[::1]"])
def test_hosts_with_ports_credentials_or_ips_are_rejected(client, er, bad):
    er_site = importlib.import_module("er_site")
    with pytest.raises(ValueError):
        er_site.normalize_host(bad)
    _, c = client
    assert c.post("/api/sites", json={"name": "n", "url": bad, "token": "t"}).status_code == 400
    assert er[0] == []


def test_a_validation_error_does_not_echo_the_token(client):
    _, c = client
    r = c.post("/api/sites", json={"token": "super-secret-token"})
    assert r.status_code == 422 and "super-secret-token" not in r.text
    assert all({"loc", "msg", "type"} <= set(e) for e in r.json()["detail"])


def test_the_page_names_its_assets_by_their_content(client):
    """A deploy changes app.css and app.js under the same path; a browser that cached the old ones
    must fetch the new ones (it once showed the new page with the old script and stylesheet)."""
    import hashlib
    import re

    _, c = client
    html = c.get("/").text
    for name in ("app.css", "app.js"):
        digest = hashlib.sha256((ROOT / "web" / "static" / name).read_bytes()).hexdigest()[:12]
        assert re.search(rf'"/static/{re.escape(name)}\?v={digest}"', html), name
        assert c.get(f"/static/{name}?v={digest}").status_code == 200
