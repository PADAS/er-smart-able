from __future__ import annotations

import json

from export.datamodel_json import build_datamodel_json, language_coverage
from export.smartdb import SmartDb
from tests.conftest import CA_A, CM


def test_language_coverage(smart_parquet):
    assert language_coverage(SmartDb(smart_parquet), CA_A) == [
        {"code": "en", "default": True, "labels": 25, "missing": 1},
        {"code": "fr", "default": False, "labels": 3, "missing": 23},
    ]


def test_datamodel_json_shape(smart_parquet):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    d = build_datamodel_json(db, ca)
    assert d["ca"] == CA_A and d["ca_id"] == "ALPHA" and d["default_language"] == "en"
    assert [l["code"] for l in d["languages"]] == ["en", "fr"]
    roots = d["categories"]
    assert [c["key"] for c in roots] == ["threats", "animals"]
    animals = roots[1]
    assert animals["labels"] == {"en": "Animals", "fr": "Animaux"} and animals["label"] == "Animals"
    assert animals["icon"] == "species" and animals["multiple"] is True
    live = animals["children"][0]
    assert live["hkey"] == "animals.liveanimals."
    assert [(a["key"], a["active"]) for a in live["attributes"]] == [("species", True), ("count", True), ("note", False)]
    atts = d["attributes"]
    assert atts["species"]["type"] == "LIST" and atts["species"]["required"] is True
    assert [o["key"] for o in atts["species"]["options"]] == ["elephant", "lion"]
    assert atts["count"]["min"] == 0.0 and atts["count"]["max"] == 10000000.0 and atts["count"]["aggregations"] == ["avg", "sum"]
    assert atts["threattype"]["options"][0]["children"][0]["key"] == "wire"
    assert atts["note"]["regex"] == ""
    cm = d["configurable_models"][0]
    assert cm["uuid"] == CM and cm["file"] == f"configurable_model_{CM}.xml" and cm["label"] == "Alpha mobile model"
    group = cm["nodes"][0]
    assert group["label"] == "Sightings" and group["category"] is None
    leaf = group["children"][0]
    assert leaf["category"] == "animals.liveanimals." and leaf["attributes"][0]["key"] == "species"
    assert leaf["attributes"][0]["options"] == ["elephant"]
    assert d["files"] == {"datamodel": "datamodel.xml"}
    json.dumps(d, ensure_ascii=False)  # serialisable
