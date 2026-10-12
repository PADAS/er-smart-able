from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from export.smartdb import SmartDb
from export.timezone import localize, plausible_epoch_ms, resolve_timezone, utc_ms_iso
from tests.conftest import T0


def test_configured_wins(smart_parquet):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    assert resolve_timezone(db, ca, None, {"SMART_ABLE_TIMEZONE": "Africa/Nairobi"}) == ("Africa/Nairobi", "configured")


def test_site_timezones_json(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    (tmp_path / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert resolve_timezone(db, ca, tmp_path, {}) == ("Asia/Manila", "inferred")


def test_inferred_from_waypoints(smart_parquet):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    assert resolve_timezone(db, ca, None, {}) == ("Asia/Manila", "inferred")   # fixture waypoint at 123.9E 14.1N


def test_default_when_no_gps(smart_parquet):
    db = SmartDb(smart_parquet)
    beta = db.cas()[1]
    assert resolve_timezone(db, beta, None, {}) == ("UTC", "default")


def test_formatting():
    z = ZoneInfo("Asia/Manila")
    assert localize(datetime(2019, 3, 4, 6, 10, 0), z) == "2019-03-04T06:10:00+08:00"
    assert utc_ms_iso(T0, z) == "2019-03-04T06:10:00+08:00"
    assert plausible_epoch_ms(T0) and not plausible_epoch_ms(1234.5) and not plausible_epoch_ms(5e15)
