"""Which timezone a CA's wall-clock times belong to.

SMART stores dates and times without a zone. Precedence: SMART_ABLE_TIMEZONE
(configured), then the browser's timezones.json written by
browse/infer_timezones.py, then a fresh inference from the CA's waypoints
(both "inferred"), then UTC ("default", always with a warning).
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

from .smartdb import CA, SmartDb


def resolve_timezone(db: SmartDb, ca: CA, site_data: Optional[Path], env: Mapping = os.environ) -> Tuple[str, str]:
    name = env.get("SMART_ABLE_TIMEZONE")
    if name:
        ZoneInfo(name)  # raises for an unknown zone, which is what we want
        return name, "configured"
    if site_data and (site_data / "timezones.json").exists():
        tz = json.loads((site_data / "timezones.json").read_text())
        name = (tz.get("byCa") or {}).get(ca.id)
        if name:
            return name, "inferred"
    rows = db.rows(f"SELECT x, y FROM {db.t('waypoint')} WHERE ca_uuid = ? AND x IS NOT NULL AND y IS NOT NULL "
                   f"AND NOT (abs(x) < 0.01 AND abs(y) < 0.01)", [ca.uuid])
    if rows:
        from timezonefinder import TimezoneFinder
        name = TimezoneFinder().timezone_at(lng=statistics.median(r["x"] for r in rows), lat=statistics.median(r["y"] for r in rows))
        if name:
            return name, "inferred"
    return "UTC", "default"


def localize(naive: datetime, zone: ZoneInfo) -> str:
    return naive.replace(tzinfo=zone).isoformat()


def track_ms_iso(ms: float, zone: ZoneInfo) -> str:
    """SMART track points store the local wall-clock time as epoch
    milliseconds, as if the local clock were UTC (verified on Lawin, see
    docs/smart-data-quirks.md#tracks). Decode it as a naive time and anchor
    it to the bundle zone like every other SMART time."""
    naive = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).replace(tzinfo=None, microsecond=0)
    return localize(naive, zone)


def plausible_epoch_ms(z: Optional[float]) -> bool:
    """True when z reads as a time between 1990 and 2100 in epoch milliseconds."""
    return z is not None and 631152000000 <= z <= 4102444800000
