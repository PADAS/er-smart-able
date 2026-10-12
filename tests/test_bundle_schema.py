from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from export.bundle import validate_bundle_dir, write_bundle
from export.smartdb import SmartDb

SCHEMA = json.loads((Path(__file__).parent.parent / "export" / "bundle.schema.json").read_text())


def test_schema_is_valid_2020_12():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"].endswith("/bundle.schema.json")


def test_fixture_bundle_validates(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "configured", None, {"kind": "backup", "file": "x.zip"})
    assert validate_bundle_dir(out) == []


def test_validation_reports_errors(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "configured", None, {"kind": "backup", "file": "x.zip"})
    m = json.loads((out / "manifest.json").read_text())
    m["bundle_schema_version"] = "one"
    (out / "manifest.json").write_text(json.dumps(m))
    (out / "tracks.json").unlink()
    errs = validate_bundle_dir(out)
    assert any("manifest.json" in e and "bundle_schema_version" in e for e in errs)
    assert any("tracks.json" in e and "missing" in e for e in errs)
