# tests/test_auth.py — the email allow-list: whole addresses and @domain suffixes, any common separator
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))


def allow(monkeypatch, value):
    monkeypatch.setenv("ALLOWED_EMAILS", value)
    import auth
    return importlib.reload(auth)


def test_entries_split_on_commas_semicolons_or_spaces_and_lower_case(monkeypatch):
    auth = allow(monkeypatch, "@EarthRanger.com, @partner.org;ana@example.org  ")
    assert auth.allowed_entries() == ["@earthranger.com", "@partner.org", "ana@example.org"]
    assert auth.email_allowed("Chris@earthranger.com")
    assert auth.email_allowed("x@partner.org")
    assert auth.email_allowed("ANA@example.org")
    assert not auth.email_allowed("bob@example.org")
    assert not auth.email_allowed("x@notpartner.org")


def test_a_domain_needs_its_at_sign(monkeypatch):
    auth = allow(monkeypatch, "partner.org")
    assert not auth.email_allowed("x@partner.org"), "a bare domain is a whole address that matches nobody"


def test_an_empty_list_allows_anyone(monkeypatch):
    auth = allow(monkeypatch, " , ")
    assert auth.allowed_entries() == []
    assert auth.email_allowed("anyone@anywhere.org")
    importlib.reload(allow(monkeypatch, "@earthranger.com"))   # leave the module as other tests expect it
