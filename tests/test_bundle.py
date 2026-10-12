from __future__ import annotations

import json
from datetime import date, time
from zoneinfo import ZoneInfo

from export.bundle import build_patrols, build_reference, leg_day_span
from export.smartdb import SmartDb, hyphenate
from tests.conftest import (CA_A, EMP_LEAD, EMP_TWO, TEAM, STATION, TRANSPORT_FOOT, MANDATE_LAW, PATROL_1,
                            LEG_1, DAY_1, WP_1, OBS_1, OBS_2, ATTACH_1)

MANILA = ZoneInfo("Asia/Manila")


def test_reference(smart_parquet):
    ref = build_reference(SmartDb(smart_parquet), CA_A)
    assert ref["patrol_types"] == [{"key": "AIR", "active": False, "max_speed": 500}, {"key": "GROUND", "active": True, "max_speed": 120}]
    assert ref["transports"] == [{"uuid": hyphenate(TRANSPORT_FOOT), "key": "foot", "labels": {"en": "Foot"}, "label": "Foot", "patrol_type": "GROUND", "active": True}]
    assert ref["mandates"][0]["key"] == "law" and ref["stations"][0]["label"] == "HQ"
    assert ref["teams"] == [{"uuid": hyphenate(TEAM), "labels": {"en": "Team One"}, "label": "Team One", "member_uuids": [hyphenate(EMP_LEAD), hyphenate(EMP_TWO)]}]
    emps = {e["id"]: e for e in ref["employees"]}
    assert emps["E1"] == {"uuid": hyphenate(EMP_LEAD), "id": "E1", "given_name": "Ana", "family_name": "Cruz",
                          "agency_uuid": ref["agencies"][0]["uuid"], "rank_uuid": ref["ranks"][0]["uuid"],
                          "employment_start": "2017-01-01", "employment_end": None, "active": True}
    assert emps["E2"]["active"] is False and emps["E2"]["employment_end"] == "2018-06-30"
    assert "smartuserid" not in json.dumps(ref) and "birth" not in json.dumps(ref)
    assert ref["ranks"] == [{"uuid": ref["ranks"][0]["uuid"], "agency_uuid": ref["agencies"][0]["uuid"], "labels": {"en": "Ranger"}, "label": "Ranger"}]
    assert ref["patrol_attributes"] == []


def test_leg_day_midnight_and_null_times():
    assert leg_day_span(date(2019, 4, 1), time(22, 0), time(1, 30), MANILA) == ("2019-04-01T22:00:00+08:00", "2019-04-02T01:30:00+08:00")
    assert leg_day_span(date(2019, 4, 1), None, None, MANILA) == (None, None)
    assert leg_day_span(date(2019, 4, 1), time(6, 0), None, MANILA) == ("2019-04-01T06:00:00+08:00", None)


def test_patrols(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    att_root = tmp_path / "site_attachments"
    (att_root / CA_A / "patrol" / PATROL_1).mkdir(parents=True)
    (att_root / CA_A / "patrol" / PATROL_1 / "photo1.jpg").write_bytes(b"\xff\xd8jpg")
    out = tmp_path / "bundle"
    warnings: list = []
    d = build_patrols(db, CA_A, MANILA, att_root, out, warnings)
    assert warnings == []
    p1, p2 = d["patrols"]
    assert p1["uuid"] == hyphenate(PATROL_1) and p1["id"] == "P-0001" and p1["patrol_type"] == "GROUND"
    assert p1["station_uuid"] == hyphenate(STATION) and p1["team_uuid"] == hyphenate(TEAM)
    assert p1["objective"] == "Boundary walk" and p1["comment"] == "Fine weather" and p1["armed"] is False
    assert p1["start_date"] == "2019-03-04" and p1["end_date"] == "2019-03-05" and p1["attributes"] == []
    leg = p1["legs"][0]
    assert leg["uuid"] == hyphenate(LEG_1) and leg["transport_uuid"] == hyphenate(TRANSPORT_FOOT) and leg["mandate_uuid"] == hyphenate(MANDATE_LAW)
    assert leg["members"] == [{"employee_uuid": hyphenate(EMP_LEAD), "leader": True, "pilot": False},
                              {"employee_uuid": hyphenate(EMP_TWO), "leader": False, "pilot": False}]
    day = leg["days"][0]
    assert day == {"uuid": hyphenate(DAY_1), "date": "2019-03-04", "start_time": "06:10:00", "end_time": "14:35:00", "rest_minutes": 0,
                   "start": "2019-03-04T06:10:00+08:00", "end": "2019-03-04T14:35:00+08:00", "has_track": True}
    wp = leg["waypoints"][0]
    assert wp["uuid"] == hyphenate(WP_1) and wp["leg_day_uuid"] == hyphenate(DAY_1) and wp["id"] == "WP-1"
    assert wp["time"] == "2019-03-04T08:12:31+08:00" and wp["location"] == [123.9, 14.1] and wp["comment"] == "Near the river"
    assert wp["source"] == "PATROL" and wp["last_modified_by_uuid"] == hyphenate(EMP_LEAD)
    assert wp["attachments"] == [{"uuid": hyphenate(ATTACH_1), "filename": "photo1.jpg", "path": f"attachments/{hyphenate(WP_1)}/photo1.jpg"}]
    assert (out / "attachments" / hyphenate(WP_1) / "photo1.jpg").read_bytes() == b"\xff\xd8jpg"
    obs = {o["uuid"]: o for o in wp["observation_groups"][0]["observations"]}
    o1, o2 = obs[hyphenate(OBS_1)], obs[hyphenate(OBS_2)]
    assert o1["category_key"] == "animals.liveanimals" and o1["category_hkey"] == "animals.liveanimals." and o1["employee_uuid"] == hyphenate(EMP_LEAD)
    assert o1["attributes"] == [{"key": "count", "type": "NUMERIC", "value": 3.0},
                                {"key": "species", "type": "LIST", "value": "elephant", "label": "Elephant"}]
    assert o2["employee_uuid"] is None
    assert {a["key"]: a for a in o2["attributes"]} == {
        "threattype": {"key": "threattype", "type": "TREE", "value": "snare.wire", "label": "Wire snare"},
        "threat": {"key": "threat", "type": "MLIST", "value": ["snare", "fire"], "labels": ["Snare", "Fire"]},
        "armed": {"key": "armed", "type": "BOOLEAN", "value": True},
        "seen": {"key": "seen", "type": "DATE", "value": "2019-03-01"}}
    assert p2["legs"][0]["days"][0]["end"] == "2019-04-02T01:30:00+08:00" and p2["legs"][0]["days"][0]["has_track"] is False
    assert p2["legs"][0]["days"][0]["rest_minutes"] is None and p2["legs"][0]["waypoints"] == []


def test_missing_attachment_warns(smart_parquet, tmp_path):
    warnings: list = []
    build_patrols(SmartDb(smart_parquet), CA_A, MANILA, tmp_path / "nothing", tmp_path / "bundle", warnings)
    assert warnings == [f"attachment photo1.jpg of waypoint {hyphenate(WP_1)} is not in the extracted filestore"]


def test_json_is_utf8(smart_parquet, tmp_path):
    d = build_patrols(SmartDb(smart_parquet), CA_A, MANILA, None, None, [])
    s = json.dumps(d, ensure_ascii=False)
    assert "Elephant" in s and "\\u" not in s
    labels = [a.get("label") for p in d["patrols"] for l in p["legs"] for w in l["waypoints"]
              for g in w["observation_groups"] for o in g["observations"] for a in o["attributes"]]
    assert "Elephant" in labels


from export.bundle import build_tracks, check_track_offset, write_bundle  # noqa: E402
from tests.conftest import T0, TRACK_1, PATROL_1 as _P1, wkb_line_z  # noqa: E402,F401


def test_tracks(smart_parquet):
    warnings: list = []
    d = build_tracks(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    assert warnings == []
    t = d["tracks"][0]
    assert t["uuid"] == hyphenate(TRACK_1) and t["leg_day_uuid"] == hyphenate(DAY_1) and t["leg_uuid"] == hyphenate(LEG_1) and t["patrol_uuid"] == hyphenate(PATROL_1)
    assert t["distance_km"] == 1.5
    assert t["start"] == "2019-03-04T06:10:00+08:00" and t["end"] == "2019-03-04T07:10:00+08:00"
    assert t["parts"] == [{"coordinates": [[123.72, 13.06], [123.73, 13.07]],
                           "times": ["2019-03-04T06:10:00+08:00", "2019-03-04T07:10:00+08:00"]}]


def test_track_without_plausible_times(smart_parquet):
    import duckdb
    p = smart_parquet / "track.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{p}'")
    con.execute("UPDATE x SET geometry = ?", [wkb_line_z([(1.0, 2.0, 350.0), (1.1, 2.1, 360.0)])])  # Z is an elevation
    con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
    con.close()
    warnings: list = []
    d = build_tracks(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    t = d["tracks"][0]
    assert "times" not in t["parts"][0] and t["start"] is None and t["end"] is None
    assert warnings == ["1 track(s) have Z values that are not epoch-millisecond timestamps; their points carry no times"]


def test_track_offset_check(smart_parquet):
    warnings: list = []
    check_track_offset(SmartDb(smart_parquet), CA_A, warnings)
    assert warnings == []   # track first point == leg-day start time: Z is local wall-clock as expected


def test_track_offset_check_flags_shifted_tracks(smart_parquet):
    import duckdb
    p = smart_parquet / "track.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{p}'")
    con.execute("UPDATE x SET geometry = ?", [wkb_line_z([(123.72, 13.06, T0 - 8 * 3600000), (123.73, 13.07, T0 - 7 * 3600000)])])  # as if UTC
    con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
    con.close()
    warnings: list = []
    check_track_offset(SmartDb(smart_parquet), CA_A, warnings)
    assert warnings == ["track times are 8 h behind the leg-day start times on 1 of 1 leg days with both; SMART normally stores track times as local wall-clock, "
                        "so these tracks may be in UTC or the leg-day times may be wrong (see quirks.html#patrol-times)"]


def test_write_bundle(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    out = tmp_path / "bundle"
    m = write_bundle(db, ca, out, "Asia/Manila", "inferred", None, {"kind": "backup", "file": "x.zip"})
    assert sorted(p.name for p in out.iterdir()) == ["manifest.json", "patrols.json", "reference.json", "tracks.json"]
    assert m["bundle_schema_version"] == 1 and m["conservation_area"]["uuid"] == hyphenate(CA_A) and m["conservation_area"]["id"] == "ALPHA"
    assert m["source"] == {"kind": "backup", "file": "x.zip", "smart_version": "7.5.4"}
    assert m["timezone"] == {"name": "Asia/Manila", "source": "inferred"}
    assert m["default_language"] == "en" and m["languages"][1] == {"code": "fr", "default": False, "labels": 3, "missing": 23}
    assert m["counts"] == {"patrols": 2, "legs": 2, "leg_days": 2, "waypoints": 1, "observations": 2, "tracks": 1, "track_points": 2, "employees": 2, "attachments": 1}
    # best available time source per leg day: DAY_1 has a timed track, DAY_2 only its start/end times
    assert m["time_coverage"] == {"leg_days": 2, "track": 1, "leg_day_times": 1, "waypoints": 0, "date_only": 0}
    assert m["generator"]["name"] == "smart-able"
    assert any("not in the extracted filestore" in w for w in m["warnings"])
    assert json.loads((out / "manifest.json").read_text()) == m
    assert m["generated_at"].endswith("Z")


def test_placeholder_leg_start_warns(smart_parquet, tmp_path):
    """SMART stores an unset leg start date as 1970-01-01 and then generates a
    leg-day row for every day up to the end date (13 such legs in the
    Camarines Norte export, 93,697 bogus leg days). Flag them."""
    import duckdb
    p = smart_parquet / "patrol_leg.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{p}'")
    con.execute("UPDATE x SET start_date = DATE '1970-01-01' WHERE id = 'P-0002-1'")
    con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
    con.close()
    warnings: list = []
    d = build_patrols(SmartDb(smart_parquet), CA_A, MANILA, None, None, warnings)
    assert [w for w in warnings if not w.startswith("attachment")] == [
        "1 leg(s) start on 1970-01-01, SMART's placeholder for an unset date, or span more than a year; "
        "their leg days are kept as stored (see quirks.html#patrol-times)"]
    leg = d["patrols"][1]["legs"][0]
    assert leg["start_date"] == "1970-01-01" and leg["placeholder_dates"] is True
    assert d["patrols"][0]["legs"][0]["placeholder_dates"] is False


def _rewrite(parquet_path, sql_update):
    import duckdb
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{parquet_path}'")
    con.execute(sql_update)
    con.execute(f"COPY x TO '{parquet_path}' (FORMAT PARQUET)")
    con.close()


def test_null_track_geometry_is_skipped_with_a_warning(smart_parquet):
    _rewrite(smart_parquet / "track.parquet", "UPDATE x SET geometry = NULL")
    warnings: list = []
    d = build_tracks(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    assert d["tracks"] == []
    assert warnings == [f"track {hyphenate(TRACK_1)} has no geometry; left out"]
    check_track_offset(SmartDb(smart_parquet), CA_A, warnings)   # must not raise
    assert len(warnings) == 1


def test_attachment_filename_with_path_parts_is_refused(smart_parquet, tmp_path):
    _rewrite(smart_parquet / "wp_attachments.parquet", "UPDATE x SET filename = '../../escape.jpg'")
    warnings: list = []
    d = build_patrols(SmartDb(smart_parquet), CA_A, MANILA, tmp_path / "att", tmp_path / "bundle", warnings)
    wp = d["patrols"][0]["legs"][0]["waypoints"][0]
    assert wp["attachments"] == []
    assert warnings == [f"attachment '../../escape.jpg' of waypoint {hyphenate(WP_1)} has a path in its name; left out"]
    assert not (tmp_path / "escape.jpg").exists()
