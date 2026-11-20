"""The page carries the language menu, the registry, and the marks that make the shell translatable."""
from __future__ import annotations

import importlib
import json
import re
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

    return TestClient(app.app)


@pytest.fixture
def loads_client(tmp_path, monkeypatch):
    """The app and its test client, with the store and the job launch the load tests use."""
    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("LOCAL_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    for m in ("app", "store", "auth", "er_site"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    from fastapi.testclient import TestClient

    return app, TestClient(app.app)


def test_the_page_carries_the_languages_the_message_script_and_the_shell_marks(client):
    h = client.get("/").text
    assert re.search(r'<script src="/static/i18n\.js\?v=\w+"></script>\s*<script src="/static/nav\.js\?v=\w+"></script>\s*<script src="/static/pages\.js', h)
    langs = json.loads(re.search(r'<script type="application/json" id="languages">(.*?)</script>', h, re.S).group(1))
    assert [l["code"] for l in langs] == ["en", "fr", "es", "pt", "sw"] and langs[1]["reviewed"] is False
    assert re.search(r'<meta name="locales-v" content="\w{6,}">', h) and 'id="langNote"' in h
    # the sidebar, its language menu and sign-out are drawn by nav.js from the list above (tests/js/nav.test.js)
    assert 'id="menuSites"' not in h and 'id="rail"' in h and 'data-i18n-aria="shell.help"' in h and re.search(r'<meta name="app-version" content="[^"]+">', h)


def test_message_files_are_served(client):
    r = client.get("/static/locales/en.json")
    assert r.status_code == 200 and "shell" in r.json()


OWNER = {"owner_email": "dev@earthranger.com", "owner_uid": "dev_dev_at_earthranger_com", "shared_with": []}
EXPORT = [{"ca_id": "050500", "dir": "ALPHA", "name": "Albay", "languages": ["en"], "default_language": "en",
           "configurable_models": [], "patrols": 3, "timezone": "Asia/Manila"}]


def test_an_error_keeps_its_english_detail_and_gains_a_code(client):
    r = client.get("/api/datasets/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Dataset not found", "code": "dataset_not_found", "values": {}}


def test_an_error_with_a_name_in_it_gives_the_name_as_a_value(loads_client):
    app, c = loads_client
    store = app.get_store()
    ds = store.create({"name": "x", "source_name": "b.zip", "status": "ready", "export": EXPORT,
                       "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00", **OWNER})
    b = store._p(ds) / "export" / "ALPHA" / "bundle"
    b.mkdir(parents=True)
    (b / "manifest.json").write_text("{}")
    site = store.create_site({"name": "s", "url": "x.pamdas.org", "created_at": "2026-10-21T00:00:00+00:00", **OWNER}, "tok")
    r = c.post(f"/api/datasets/{ds}/loads", json={"ca_id": "ALPHA", "site_id": site, "options": {"language": "zz"}})
    assert r.status_code == 400 and r.json()["code"] == "language_not_in_bundle" and r.json()["values"] == {"language": "zz"}
    assert "zz" in r.json()["detail"]


def test_a_validation_error_has_a_code_and_still_drops_what_was_submitted(client):
    r = client.post("/api/sites", json={"name": "NAME-VALUE", "url": "example.pamdas.org", "token": {"secret": "TOKEN-VALUE"}})
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"
    assert "TOKEN-VALUE" not in r.text and "NAME-VALUE" not in r.text and "example.pamdas.org" not in r.text


def test_the_two_host_refusals_have_their_own_codes(client):
    only = client.post("/api/sites", json={"name": "x", "url": "https://site.pamdas.org:8443", "token": "t"})
    assert only.status_code == 400 and only.json()["code"] == "site_host_only"
    assert only.json()["detail"] == "Enter just the site's host name, like site.pamdas.org"
    missing = client.post("/api/sites", json={"name": "x", "url": "localhost", "token": "t"})
    assert missing.json()["code"] == "site_host_missing"
    assert client.post("/api/sites", json={"name": "x", "url": "a.pamdas.org", "token": "  "}).json()["code"] == "token_required"


@pytest.mark.parametrize("exc_name,code", [("TokenRejected", "token_rejected"), ("SiteUnreachable", "site_unreachable")])
def test_the_reason_comes_from_the_check_and_never_holds_the_token(client, monkeypatch, exc_name, code):
    import er_site
    token = "SECRET-TOKEN-1234"

    def fail(host, tok):
        raise getattr(er_site, exc_name)(f"{host} answered 401 Unauthorized")
    monkeypatch.setattr(sys.modules["app"], "check_token", fail)
    r = client.post("/api/sites", json={"name": "x", "url": "a.pamdas.org", "token": token})
    assert r.status_code == 400 and r.json()["code"] == code
    assert r.json()["values"] == {"reason": "a.pamdas.org answered 401 Unauthorized"}
    assert token not in r.text


def test_the_texts_check_token_raises_are_built_without_the_token():
    src = (ROOT / "web" / "er_site.py").read_text()
    body = src[src.index("def check_token"):]
    assert not re.search(r"(?:Unreachable|Rejected)\([^\n]*\btoken\b", body)


def test_no_route_raises_a_bare_http_exception():
    for f in ("app.py", "auth.py"):
        src = (ROOT / "web" / f).read_text()
        assert not re.search(r"raise HTTPException\(", src), f
    codes = set(re.findall(r'ApiError\(\s*\d+,\s*"(\w+)"', (ROOT / "web" / "app.py").read_text() + (ROOT / "web" / "auth.py").read_text()))
    codes |= {"site_host_only", "site_host_missing", "token_rejected", "site_unreachable", "invalid_request"}
    en = json.loads((ROOT / "web" / "static" / "locales" / "en.json").read_text())["errors"]
    assert codes and codes <= set(en), codes - set(en)


@pytest.mark.parametrize("url", ["[abc", "https://[::1", "a.pamdas.org]"])
def test_a_malformed_bracketed_host_is_a_400_with_the_host_guidance(client, url):
    import er_site
    try:
        er_site.normalize_host(url)
    except ValueError as e:
        raised = str(e)
    r = client.post("/api/sites", json={"name": "x", "url": url, "token": "t"})
    assert r.status_code == 400 and r.json()["code"] == "site_host_missing" and r.json()["detail"] == raised


def test_help_is_served_in_the_language_asked_for_with_the_quirks_in_english(client):
    en = client.get("/api/help").json()["sections"]
    fr = client.get("/api/help?lang=fr").json()["sections"]
    assert [s["id"] for s in fr] == [s["id"] for s in en]
    assert {s["id"]: s["lang"] for s in fr} == {"overview": "fr", "sites": "fr", "loading": "fr", "statuses": "fr", "stops": "fr", "quirks": "en"}
    assert fr[0]["title"] != en[0]["title"] and all(s["lang"] == "en" for s in en)
    assert 'id="finding-team"' in next(s for s in fr if s["id"] == "stops")["html"], "the anchors the app links to survive translation"
    assert 'id="rangers-accounts"' in next(s for s in fr if s["id"] == "loading")["html"]


def test_help_in_an_unknown_language_is_english(client):
    assert client.get("/api/help?lang=../../etc").json() == client.get("/api/help").json()


def test_a_help_page_with_no_translation_is_the_english_one(client, monkeypatch, tmp_path):
    import help_pages
    d = tmp_path / "help"; (d / "fr").mkdir(parents=True)
    (d / "01-a.md").write_text("# A\n\nenglish"); (d / "02-b.md").write_text("# B\n\nenglish"); (d / "fr" / "01-a.md").write_text("# A fr\n\nfrançais")
    monkeypatch.setattr(help_pages, "HELP_DIR", d); help_pages._cache.clear()
    got = {s["id"]: (s["lang"], s["title"]) for s in help_pages.sections("fr")}
    assert got["a"] == ("fr", "A fr") and got["b"] == ("en", "B")
