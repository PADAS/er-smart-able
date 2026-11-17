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


def test_the_page_carries_the_languages_the_message_script_and_the_shell_marks(client):
    h = client.get("/").text
    assert re.search(r'<script src="/static/i18n\.js\?v=\w+"></script>\s*<script src="/static/pages\.js', h)
    langs = json.loads(re.search(r'<script type="application/json" id="languages">(.*?)</script>', h, re.S).group(1))
    assert [l["code"] for l in langs] == ["en", "fr", "es", "pt", "sw"] and langs[1]["reviewed"] is False
    assert re.findall(r'<option value="(\w+)" lang="\1">', h) == ["en", "fr", "es", "pt", "sw"]
    assert re.search(r'<meta name="locales-v" content="\w{6,}">', h) and 'id="langNote"' in h
    assert 'data-i18n="shell.sites"' in h and 'data-i18n="shell.signOut"' in h and 'data-i18n-aria="shell.help"' in h


def test_message_files_are_served(client):
    r = client.get("/static/locales/en.json")
    assert r.status_code == 200 and "shell" in r.json()
