#!/usr/bin/env python3
"""Infer an IANA timezone for each conservation area from its waypoint GPS
locations, using timezonefinder.

SMART stores timestamps as naive local wall-clock times with no timezone. This
writes <data_dir>/timezones.json so the browser (and later Export/Load to
EarthRanger) can anchor them to a real zone.

Usage: infer_timezones.py <data_dir>   (run by `./smart-able browse`)
"""
import json
import statistics
import sys
from pathlib import Path

from timezonefinder import TimezoneFinder

data = Path(sys.argv[1] if len(sys.argv) > 1 else "site/data")
wps = json.loads((data / "waypoints.json").read_text())

by_ca: dict[str, tuple[list, list]] = {}
for w in wps:
    x, y = w.get("x"), w.get("y")
    if x is None or y is None or (abs(x) < 0.01 and abs(y) < 0.01):
        continue  # missing or 0,0 placeholder GPS
    xs, ys = by_ca.setdefault(w["ca"], ([], []))
    xs.append(x)
    ys.append(y)

tf = TimezoneFinder()
zones = {}
for ca, (xs, ys) in by_ca.items():
    # median centroid is robust to stray points
    zones[ca] = tf.timezone_at(lng=statistics.median(xs), lat=statistics.median(ys))
    print(f"  {ca}: {zones[ca]}  ({len(xs)} waypoints)")

default_ca = max(by_ca, key=lambda c: len(by_ca[c][0])) if by_ca else None
out = {"default": zones.get(default_ca), "byCa": zones}
(data / "timezones.json").write_text(json.dumps(out, indent=1))
print(f"  default timezone: {out['default']}")
