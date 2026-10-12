from __future__ import annotations

from export.smartdb import SmartDb, hyphenate, safe_id
from tests.conftest import CA_A, CA_B, CAT_THREATS, ATT_SPECIES, LIST_ELE, TRANSPORT_FOOT


def test_hyphenate_and_safe_id():
    assert hyphenate("0c7cbb411a60485d85138255206466a4") == "0c7cbb41-1a60-485d-8513-8255206466a4"
    assert hyphenate("0c7cbb41-1a60-485d-8513-8255206466a4") == "0c7cbb41-1a60-485d-8513-8255206466a4"
    assert safe_id("Region 05 / Albay") == "Region_05___Albay"
    assert safe_id("050500") == "050500"


def test_cas_and_version(smart_parquet):
    db = SmartDb(smart_parquet)
    cas = db.cas()
    assert [c.id for c in cas] == ["ALPHA", "BETA"]
    assert cas[0].name == "Alpha & Co" and cas[0].country == "PH"
    assert db.smart_version() == "7.5.4"
    assert db.has("patrol") and not db.has("no_such_table")


def test_languages_default_first(smart_parquet):
    db = SmartDb(smart_parquet)
    langs = db.languages(CA_A)
    assert [(l.code, l.default) for l in langs] == [("en", True), ("fr", False)]


def test_labels_fallback(smart_parquet):
    db = SmartDb(smart_parquet)
    L = db.labels(CA_A)
    assert L.get(ATT_SPECIES) == "Species"              # default language
    assert L.get(ATT_SPECIES, "fr") == "Espèce"
    assert L.get(CAT_THREATS, "fr") == 'Threats & "risks" <all>'   # fr missing -> default
    assert L.all(LIST_ELE) == {"en": "Elephant", "fr": "Éléphant"}
    assert L.get("0" * 32) is None
    assert TRANSPORT_FOOT in db.labelled_elements(CA_A)
    assert LIST_ELE in db.labelled_elements(CA_A)
    assert len(db.labelled_elements(CA_A)) == 26   # 3 cats, 7 atts, 4 list, 3 tree, transport, mandate, station, rank, team, cm, 2 nodes, config
    assert len(db.labelled_elements(CA_B)) == 0
