"""How much memory loading a bundle's tracks takes, on a made-up bundle of a given size.

    python scripts/measure_load_memory.py --template BUNDLE --points 12000000 --patrols 15000 --version 2

Run it with a Python that has er-smart-sync installed (the load job's environment). BUNDLE is any
small bundle folder (one `./smart-able export` wrote, or er-smart-sync's tests/fixtures/smart_demo_bundle);
its manifest, reference and patrols are kept and its tracks are replaced by that many made-up points
spread over that many made-up patrols (a line of points, no real data). A child process then loads
the bundle with er-smart-sync and reads every patrol's tracks in turn, as an import does. The track
file's size and the child's peak resident memory are printed.

Version 1 is the bundle as it was (tracks.json, read whole); version 2 has the tracks one per line
with an index (tracks.jsonl, read a patrol at a time).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHILD = """
import resource, sys
from er_smart_sync.bundle import load_bundle
from er_smart_sync.patrol_times import tracks_by_day
b = load_bundle(sys.argv[1])
points = 0
for u in sorted(b.tracks.patrol_uuids()):
    by_day = tracks_by_day(b.tracks.for_patrol(u))
    points += sum(len(part["coordinates"]) for tracks in by_day.values() for t in tracks for part in t["parts"])
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(points, peak if sys.platform == "darwin" else peak * 1024)
"""


def uuid(kind: int, n: int) -> str:
    return f"{kind:08x}-0000-4000-8000-{n:012x}"


def write(out: Path, template: Path, points: int, patrols: int, version: int) -> Path:
    """The template's manifest, reference and patrols, and made-up tracks in place of its own."""
    per = max(1, points // patrols)
    manifest = json.loads((template / "manifest.json").read_text())
    manifest["bundle_schema_version"] = version
    (out / "manifest.json").write_text(json.dumps(manifest))
    for name in ("reference.json", "patrols.json"):
        shutil.copy(template / name, out / name)
    coords = [[16.26 + i / 1e7, 2.92 + i / 1e7] for i in range(per)]

    def track(i: int) -> dict:
        return {"uuid": uuid(2, i), "leg_day_uuid": uuid(3, i), "leg_uuid": uuid(4, i), "patrol_uuid": uuid(1, i),
                "distance_km": 1.0, "start": None, "end": None, "parts": [{"coordinates": coords}]}

    if version == 1:
        name = out / "tracks.json"
        with open(name, "w") as f:   # indented, as the exporter wrote version 1
            f.write('{\n "tracks": [\n')
            for i in range(patrols):
                f.write(json.dumps(track(i), indent=1) + (",\n" if i + 1 < patrols else "\n"))
            f.write(" ]\n}\n")
        return name
    name, index, at = out / "tracks.jsonl", {}, 0
    with open(name, "wb") as f:
        for i in range(patrols):
            raw = (json.dumps(track(i), separators=(",", ":")) + "\n").encode()
            f.write(raw)
            index[uuid(1, i)] = {"offset": at, "length": len(raw), "tracks": 1, "points": per}
            at += len(raw)
    (out / "tracks.index.json").write_text(json.dumps({"patrols": index}))
    return name


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--template", type=Path, required=True, help="a small bundle folder to take everything but the tracks from")
    a.add_argument("--points", type=int, required=True)
    a.add_argument("--patrols", type=int, required=True)
    a.add_argument("--version", type=int, choices=(1, 2), required=True)
    args = a.parse_args()
    with tempfile.TemporaryDirectory(prefix="measure-load-") as d:
        tracks = write(Path(d), args.template, args.points, args.patrols, args.version)
        size = tracks.stat().st_size
        done = subprocess.run([sys.executable, "-c", CHILD, d], capture_output=True, text=True)
        if done.returncode:
            print(done.stderr, file=sys.stderr)
            return 1
        points, peak = (int(x) for x in done.stdout.split())
    mib = 1048576
    print(f"version {args.version}: {points:,} points in {args.patrols:,} patrols; {tracks.name} {size / mib:,.0f} MiB; "
          f"peak memory {peak / mib:,.0f} MiB ({peak / size:.2f}x the track file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
