# Tracks By Patrol (app) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `smart-able export` writes a bundle whose tracks can be read one patrol at a time, and the load job uses it, so a load no longer holds every track in memory.

**Architecture:** The exporter writes bundle version 2: `tracks.jsonl` (one track per line, grouped by patrol) and `tracks.index.json` (each patrol's byte range and counts) in place of `tracks.json`. The load job asks the library for tracks by patrol and takes the plan's point counts from the index.

**Tech Stack:** Python 3.12, DuckDB over Parquet (`export/smartdb.py`), `jsonschema`, pytest. Tests: `.venv/bin/python -m pytest -q` (365 passed, 2 skipped before this change; the 2 skipped include `tests/test_load_e2e.py`, which needs `er_smart_sync` importable).

**Spec:** `docs/superpowers/specs/2026-11-18-tracks-by-patrol-design.md`. Ticket GUNDI-5944.

**Depends on:** the library's plan, `docs/superpowers/plans/2026-11-18-tracks-by-patrol.md` in `PADAS/earthranger-smart-utils` (local checkout `/Users/chrisdo/padas/earthranger-smart-utils`, branch `feat/tracks-by-patrol`). Task 1 here needs nothing from it. Task 2 needs its code to test against and its release tag to pin.

**Not in this plan:** step 2 of the spec (the trial of an ephemeral disk against a bucket mount, and bringing the load job's memory back down). It needs a version 2 bundle of a large area on the hosted app, so it is planned after this is deployed.

## Global Constraints

- Version 2 layout, exactly as the library reads it: `tracks.jsonl` is UTF-8, one track per line written with `json.dumps(track, ensure_ascii=False, separators=(",", ":")) + "\n"`, ordered by `patrol_uuid`, then `leg_day_uuid`, then `uuid`. `tracks.index.json` is `{"patrols": {"<patrol uuid>": {"offset": int, "length": int, "tracks": int, "points": int}}}` with byte offsets; entries in offset order start at 0, each starts where the one before ends, and the last ends at the file's size. A patrol with no tracks has no entry.
- A track's fields are unchanged. `manifest.json`, `reference.json` and `patrols.json` are unchanged except `"bundle_schema_version": 2`. The manifest's `counts` are unchanged.
- `export/bundle.schema.json` and the library's `src/er_smart_sync/bundle/schema.json` end byte-identical. The changes: `$defs.manifest.properties.bundle_schema_version` becomes `{"type": "integer", "enum": [1, 2]}`; `$defs.tracks_index` is added as written in the library's plan, Task 1; `$defs.track` and `$defs.tracks` stay.
- The exporter writes version 2 only.
- Parquet, the dataset browser's data and `browse/` are not touched.
- No real conservation area's rangers, customer host or token in tests, docs or commits; `example.pamdas.org` only.
- The pinned library version is the tag the user chooses for the library's release. Do not tag either repository.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Review Focus

1. **A conservation area with no tracks.** `tracks.jsonl` is empty (zero bytes), the index is `{"patrols": {}}`, and the bundle validates and loads. (Task 1)
2. **Tracks of one patrol spread over several leg days and legs.** They are still one contiguous run, and the index's `tracks` and `points` are the run's totals. (Task 1)
3. **A track with a non-ASCII character or a long coordinate list.** Offsets are bytes of the encoded line. (Task 1)
4. **A windowed load.** The plan counts only the selected patrols' points, and an unselected patrol's tracks are never asked for. (Task 2)
5. **A dataset extracted before this change.** Its version 1 bundle still plans and loads through the same job. (Task 2)

---

### Task 1: The exporter writes version 2

**Files:**
- Modify: `export/bundle.py`, `export/bundle.schema.json`, `RUNBOOK.md` (the table row for `bundle/tracks.json`)
- Test: `tests/test_bundle.py`, `tests/test_bundle_schema.py`

**Interfaces:**
- Produces, `export/bundle.py`:
  - `BUNDLE_SCHEMA_VERSION = 2`
  - `write_tracks(tracks: list, out_dir: Path) -> dict`: sorts the tracks, writes `tracks.jsonl` a line at a time and `tracks.index.json`, and returns the index. `write_bundle` calls it in place of writing `tracks.json`. The other three files are written as today.
  - `validate_bundle_dir(path) -> List[str]`: validates `manifest`, `reference`, `patrols` as today; for version 2, `tracks.index.json` against `$defs/tracks_index`, each line of `tracks.jsonl` against `$defs/track`, that the index tiles the file, that each run has the index's number of lines and points, and that each line's `patrol_uuid` is its run's. For a version 1 directory it validates `tracks.json` as today. Error strings keep the form `<file>: <where>: <message>`, and a missing file is `<file>: missing`.
- `build_tracks`, `load_tracks`, `check_track_offset`, `time_coverage` and the manifest counts are unchanged.

- [ ] **Step 1: Write the failing tests.** In `tests/test_bundle.py`, change the file listing assertion to `["manifest.json", "patrols.json", "reference.json", "tracks.index.json", "tracks.jsonl"]` and replace reads of `tracks.json` with a helper `read_tracks(out) -> list` that parses `tracks.jsonl`. Add:

```python
def test_tracks_are_one_per_line_grouped_by_patrol(smart_parquet, tmp_path):
    out = _export(smart_parquet, tmp_path)   # however this file already runs the exporter
    raw = (out / "tracks.jsonl").read_bytes()
    lines = raw.split(b"\n")
    assert lines[-1] == b"" and all(b"\n" not in l and b": " not in l for l in lines[:-1])
    tracks = [json.loads(l) for l in lines[:-1]]
    order = [(t["patrol_uuid"], t["leg_day_uuid"], t["uuid"]) for t in tracks]
    assert order == sorted(order)
    index = json.loads((out / "tracks.index.json").read_text())["patrols"]
    at = 0
    for uuid, e in sorted(index.items(), key=lambda kv: kv[1]["offset"]):
        assert e["offset"] == at
        run = [json.loads(l) for l in raw[at:at + e["length"]].split(b"\n")[:-1]]
        assert {t["patrol_uuid"] for t in run} == {uuid} and len(run) == e["tracks"]
        assert sum(len(p["coordinates"]) for t in run for p in t["parts"]) == e["points"]
        at += e["length"]
    assert at == len(raw)
    m = json.loads((out / "manifest.json").read_text())
    assert m["bundle_schema_version"] == 2
    assert m["counts"]["tracks"] == len(tracks) == sum(e["tracks"] for e in index.values())
    assert m["counts"]["track_points"] == sum(e["points"] for e in index.values())

def test_an_area_with_no_tracks_writes_an_empty_file_and_index(...):   # the existing no-tracks case: b"" and {"patrols": {}}, and it validates
def test_write_tracks_counts_bytes_not_characters(tmp_path):
    # write_tracks on two hand-made tracks of patrols "a" and "b", the first with "uuid": "tré";
    # the index's offset for "b" equals the length in bytes of the first line encoded as UTF-8
```

In `tests/test_bundle_schema.py`: the missing-file case removes `tracks.jsonl` and expects `tracks.jsonl: missing`; add cases that `validate_bundle_dir` reports an index that stops short of the file, a run with a line of another patrol, and a line that fails `$defs/track`; and `test_a_version_1_directory_still_validates` (write the same tracks as `tracks.json` with manifest version 1).

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_bundle.py tests/test_bundle_schema.py`
Expected: FAIL (`tracks.jsonl` does not exist)

- [ ] **Step 3: Implement** `write_tracks`, the `write_bundle` change, the schema changes and `validate_bundle_dir`. Update the module docstring and `RUNBOOK.md`'s row to name `bundle/tracks.jsonl` and `bundle/tracks.index.json`.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Check the schema matches the library's**

Run: `diff export/bundle.schema.json /Users/chrisdo/padas/earthranger-smart-utils/src/er_smart_sync/bundle/schema.json`
Expected: no output (once the library's Task 1 is done; if it is not yet, the diff shows only the changes named in Global Constraints)

- [ ] **Step 6: Commit**

```bash
git add export/bundle.py export/bundle.schema.json RUNBOOK.md tests/test_bundle.py tests/test_bundle_schema.py
git commit -m "export: bundle version 2, tracks one per line with an index by patrol"
```

---

### Task 2: The load job reads tracks by patrol

**Files:**
- Modify: `web/load_job.py` (`ErSmartSyncMigration._window_bundle`, `.counts`), `web/requirements-load.txt`
- Test: `tests/test_load_job.py`, `tests/test_load_e2e.py`

**Interfaces:**
- Consumes, from the library: `bundle.tracks.points(patrol_uuid) -> int`; `Bundle.tracks` is a `TrackStore`, not a list.
- Produces:
  - `_window_bundle()` returns `replace(self.bundle, patrols=selected)`; the track store is passed through untouched.
  - `counts()` for a windowed load: `track_points` is `sum(self.bundle.tracks.points(u) for u in selected)`. The unwindowed case still returns the manifest's counts.
  - `web/requirements-load.txt` pins the library's new tag.

`tests/test_load_e2e.py` runs only where `er_smart_sync` is importable. To run it here, use the load venv with the library checkout installed (`web/DEPLOY.md`, "Running locally"): `uv venv .venv-load && uv pip install --python .venv-load/bin/python -e /Users/chrisdo/padas/earthranger-smart-utils pytest fastapi httpx` and then `.venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py`. If its dependencies cannot be made to coexist, say so in the report; do not skip silently.

- [ ] **Step 1: Write the failing tests.** In `tests/test_load_e2e.py` (or `tests/test_load_job.py` where the real `ErSmartSyncMigration` is constructed), with a bundle written by this repository's exporter from the `smart_parquet` fixture:

```python
def test_plan_counts_come_from_the_index(...):
    # unwindowed: counts() == the manifest's counts
    # windowed to a range holding some patrols: counts()["track_points"] equals the sum, over the selected patrols,
    # of the points in their lines of tracks.jsonl; and the tracks of an unselected patrol were never read
    # (wrap bundle.tracks.for_patrol and assert it was not called at all by counts())

def test_a_version_1_bundle_still_plans(...):
    # the same data written as version 1 (tracks.json, manifest version 1): the plan's counts equal the version 2 plan's
```

- [ ] **Step 2: Run and see them fail**

Run: `.venv-load/bin/python -m pytest -q tests/test_load_e2e.py`
Expected: FAIL (`TrackStore` is not subscriptable as the old filter uses it, or the count differs)

- [ ] **Step 3: Implement** the two methods and the pin.

- [ ] **Step 4: Run both ways**

Run: `.venv/bin/python -m pytest -q` and `.venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py`
Expected: PASS in both

- [ ] **Step 5: Commit**

```bash
git add web/load_job.py web/requirements-load.txt tests/test_load_job.py tests/test_load_e2e.py
git commit -m "Load job: the plan's track points come from the bundle's index; tracks are read by patrol"
```

---

### Task 3: Measure it, and say so

**Files:**
- Modify: `web/DEPLOY.md`, `docs/decisions.md`, `docs/load-performance.md`
- Create: `scripts/measure_load_memory.py`

**Interfaces:**
- Produces: `scripts/measure_load_memory.py --points N --patrols P --version {1,2}`: writes a made-up bundle of that size to a temporary folder (no real data), then, in a child process started with the load venv's Python, runs `load_bundle` and builds every patrol (leg times and track batches, no network), and prints the bundle's track file size and the child's peak resident memory.

- [ ] **Step 1: Write the script** and run it at the failed area's scale and at a tenth of it:

Run: `.venv-load/bin/python scripts/measure_load_memory.py --points 12000000 --patrols 15000 --version 1` and the same with `--version 2`, then both with `--points 1200000`
Expected: version 1's peak is several times its track file; version 2's peak is about the same at both sizes. Record the four numbers.

- [ ] **Step 2: Write them down.**
  - `docs/load-performance.md`: a short section with the four numbers and how to reproduce them.
  - `docs/decisions.md`: the decision, in that file's style: tracks by patrol with an index; why not one file per patrol, why not a streaming parser; version 1 still read.
  - `web/DEPLOY.md`: in the load job's memory paragraph, that a dataset extracted before this release has a version 1 bundle, which still needs about 5.5 times its `tracks.json` in memory, and that re-extracting it writes version 2; that the memory figure stays at 8 GiB until the export is no longer copied into memory (the spec's step 2).

- [ ] **Step 3: Run the suite and commit**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

```bash
git add scripts/measure_load_memory.py web/DEPLOY.md docs/decisions.md docs/load-performance.md
git commit -m "Tracks by patrol: the measurements, the decision, and what an older dataset needs"
```
