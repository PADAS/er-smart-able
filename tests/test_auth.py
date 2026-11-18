# tests/test_auth.py — the email allow-list: whole addresses and @domain suffixes, any common separator
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))


import pytest  # noqa: E402


@pytest.fixture
def allow(monkeypatch):
    """Reload auth with a given ALLOWED_EMAILS; afterwards reload it with the environment as it was,
    whichever test ran and in whatever order."""
    import auth

    def go(value):
        monkeypatch.setenv("ALLOWED_EMAILS", value)
        return importlib.reload(auth)

    yield go
    monkeypatch.undo()
    importlib.reload(auth)


def test_entries_split_on_commas_semicolons_or_spaces_and_lower_case(allow):
    auth = allow("@EarthRanger.com, @partner.org;ana@example.org  ")
    assert auth.allowed_entries() == ["@earthranger.com", "@partner.org", "ana@example.org"]
    assert auth.email_allowed("Chris@earthranger.com")
    assert auth.email_allowed("x@partner.org")
    assert auth.email_allowed("ANA@example.org")
    assert not auth.email_allowed("bob@example.org")
    assert not auth.email_allowed("x@notpartner.org")


def test_a_domain_needs_its_at_sign(allow):
    auth = allow("partner.org")
    assert not auth.email_allowed("x@partner.org"), "a bare domain is a whole address that matches nobody"


def test_an_empty_list_allows_anyone(allow):
    auth = allow(" , ")
    assert auth.allowed_entries() == []
    assert auth.email_allowed("anyone@anywhere.org")


@pytest.fixture
def support(monkeypatch):
    """Reload auth with a given SUPPORT_EMAILS (None: unset), and put it back afterwards."""
    import auth

    def go(value=None):
        monkeypatch.delenv("SUPPORT_EMAILS", raising=False)
        if value is not None:
            monkeypatch.setenv("SUPPORT_EMAILS", value)
        return importlib.reload(auth)

    yield go
    monkeypatch.undo()
    importlib.reload(auth)


def test_support_is_whole_addresses_only(support):
    auth = support("Sup@EarthRanger.com,, @earthranger.com ; two@partner.org,")
    assert auth.support_entries() == ["sup@earthranger.com", "two@partner.org"]
    assert auth.is_support("SUP@earthranger.com") and auth.is_support("two@partner.org")
    assert not auth.is_support("other@earthranger.com") and not auth.is_support("") and not auth.is_support(None)


def test_nobody_is_support_when_unset(support):
    auth = support()
    assert auth.support_entries() == [] and not auth.is_support("dev@earthranger.com")


def test_support_needs_a_verified_address(support):
    auth = support("sup@earthranger.com")
    who = {"uid": "u1", "email": "sup@earthranger.com"}
    assert auth._from_decoded({**who, "email_verified": True})["support"] is True
    assert auth._from_decoded({**who, "email_verified": False})["support"] is False
    assert auth._from_decoded(who)["support"] is False
    assert auth._from_decoded({"uid": "u2", "email": "other@earthranger.com", "email_verified": True})["support"] is False
