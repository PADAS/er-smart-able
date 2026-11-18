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
    (out / "tracks.jsonl").unlink()
    errs = validate_bundle_dir(out)
    assert any("manifest.json" in e and "bundle_schema_version" in e for e in errs)
    assert any("tracks.jsonl" in e and "missing" in e for e in errs)


# ---- version 2: the tracks' lines and their index are checked against each other
from export.bundle import write_tracks  # noqa: E402


def _bundle(smart_parquet, tmp_path, tracks=None):
    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "inferred", None, {"kind": "backup", "file": "x.zip"})
    if tracks is not None:
        write_tracks(tracks, out)
    return out


def _tracks(out) -> list:
    return [json.loads(l) for l in (out / "tracks.jsonl").read_text().splitlines()]


def _other(track: dict, n: int) -> dict:
    """The same track under another patrol, so a bundle has more than one run."""
    u = f"00000000-0000-4000-8000-{n:012x}"
    return {**track, "uuid": u, "patrol_uuid": f"ffffffff-0000-4000-8000-{n:012x}"}


def test_a_bundle_with_several_patrols_tracks_validates(smart_parquet, tmp_path):
    out = _bundle(smart_parquet, tmp_path)
    [t] = _tracks(out)
    write_tracks([t, _other(t, 1), _other(t, 2), {**_other(t, 2), "uuid": "00000000-0000-4000-8000-0000000000ff"}], out)
    assert validate_bundle_dir(out) == []
    write_tracks([], out)
    assert validate_bundle_dir(out) == []


def _index(out):
    return json.loads((out / "tracks.index.json").read_text())


def test_an_index_that_does_not_cover_the_file_is_reported(smart_parquet, tmp_path):
    out = _bundle(smart_parquet, tmp_path)
    [t] = _tracks(out)
    write_tracks([t, _other(t, 1)], out)
    good = _index(out)
    last = max(good["patrols"], key=lambda u: good["patrols"][u]["offset"])
    for change, expect in (({"length": good["patrols"][last]["length"] - 1}, "does not end at the end of a line"),
                           ({"offset": good["patrols"][last]["offset"] + 1}, "was expected"),
                           ({"tracks": 2}, "says 2 tracks"), ({"points": 99}, "says 99 points")):
        doc = json.loads(json.dumps(good))
        doc["patrols"][last].update(change)
        (out / "tracks.index.json").write_text(json.dumps(doc))
        errs = validate_bundle_dir(out)
        assert errs and all(e.startswith("tracks.index.json: ") for e in errs) and expect in errs[0], (change, errs)
    doc = json.loads(json.dumps(good))
    del doc["patrols"][last]
    (out / "tracks.index.json").write_text(json.dumps(doc))
    assert any("covers" in e for e in validate_bundle_dir(out))
    (out / "tracks.index.json").write_text(json.dumps({"patrols": {last: {"offset": 0}}}))
    assert any(e.startswith("tracks.index.json: ") and "required" in e for e in validate_bundle_dir(out))
    (out / "tracks.index.json").unlink()
    assert "tracks.index.json: missing" in validate_bundle_dir(out)


def test_a_line_that_is_wrong_is_reported(smart_parquet, tmp_path):
    out = _bundle(smart_parquet, tmp_path)
    [t] = _tracks(out)
    write_tracks([t, _other(t, 1)], out)
    index = _index(out)["patrols"]
    a, b = sorted(index, key=lambda u: index[u]["offset"])
    (out / "tracks.index.json").write_text(json.dumps({"patrols": {a: index[b], b: index[a]}}))   # each points at the other's line
    errs = validate_bundle_dir(out)
    assert len(errs) == 2 and all("belongs to patrol" in e and e.startswith("tracks.jsonl: ") for e in errs)
    write_tracks([{**t, "distance_km": "far"}], out)
    errs = validate_bundle_dir(out)
    assert len(errs) == 1 and errs[0].startswith("tracks.jsonl: ") and "line 1" in errs[0] and "distance_km" in errs[0]
    raw = bytearray((out / "tracks.jsonl").read_bytes())
    raw[0] = ord("[")
    (out / "tracks.jsonl").write_bytes(bytes(raw))
    assert any("not valid JSON" in e for e in validate_bundle_dir(out))


def test_a_version_1_directory_still_validates(smart_parquet, tmp_path):
    out = _bundle(smart_parquet, tmp_path)
    tracks = _tracks(out)
    (out / "tracks.jsonl").unlink()
    (out / "tracks.index.json").unlink()
    (out / "tracks.json").write_text(json.dumps({"tracks": tracks}))
    m = json.loads((out / "manifest.json").read_text())
    m["bundle_schema_version"] = 1
    (out / "manifest.json").write_text(json.dumps(m))
    assert validate_bundle_dir(out) == []
    (out / "tracks.json").unlink()
    assert validate_bundle_dir(out) == ["tracks.json: missing"]
