# Loading without holding every track in memory

Ticket: GUNDI-5944.

## Purpose

A load's planning job was killed at its memory limit before it planned
anything. The conservation area's `bundle/tracks.json` is 801 MiB, and the
loader reads each bundle file whole, parses it whole and validates it
whole, which takes about 4.4 times the file's size. The job also copies the
export to `/tmp`, which Cloud Run holds in memory. Together that was about
4.5 GiB against a 2 GiB limit. The limit is now 8 GiB, which only moves
the ceiling.

The import needs one patrol's tracks at a time. This change makes the
bundle and the loader work that way, so a load's memory depends on its
largest patrol and not on the conservation area's tracks.

## What was decided

- The bundle's tracks become one track per line, grouped by patrol, with a
  small index (bundle version 2).
- The library reads one patrol's tracks from a path by byte offset. The
  same code runs on a laptop and in the cloud job.
- Bundles already extracted (version 1) keep loading as they do today. No
  dataset is forced to re-extract.
- Afterwards, as a second step, the job stops copying the export into
  memory: an ephemeral disk or a read-only bucket mount, chosen by a trial.

## Two repositories

| Repository | What changes |
| --- | --- |
| `PADAS/er-smart-able` | `smart-able export` writes version 2; the bundle schema; `web/load_job.py`; the load image's pin of the library |
| `PADAS/earthranger-smart-utils` | `er_smart_sync.bundle` reads versions 1 and 2; the import asks for tracks a patrol at a time; the vendored schema; a release |

The library is released first, reading both versions. The app then pins
that release and starts writing version 2 in the same app release, because
the extraction job and the load job share an image.

## Bundle version 2

`manifest.json`, `reference.json` and `patrols.json` keep their content.
`manifest.json` says `"bundle_schema_version": 2`.

`tracks.json` is replaced by two files.

**`tracks.jsonl`**: UTF-8, one track per line, each line a JSON object with
no indentation and no spaces after separators, ending in `\n`. A track has
the fields it has today (`uuid`, `leg_day_uuid`, `leg_uuid`, `patrol_uuid`,
`distance_km`, `start`, `end`, `parts`). The lines are ordered by
`patrol_uuid`, then leg day, then track `uuid`, so one patrol's lines are
one contiguous run of bytes.

**`tracks.index.json`**:

```json
{"patrols": {"<patrol uuid>": {"offset": 0, "length": 5120, "tracks": 3, "points": 412}}}
```

`offset` and `length` are bytes into `tracks.jsonl`. A patrol with no
tracks has no entry. The entries, in file order, cover the file exactly:
the first starts at 0, each starts where the one before ends, and the last
ends at the file's size.

The schema (`export/bundle.schema.json`, vendored in the library as
`bundle/schema.json`) allows manifest version 1 or 2, keeps `$defs/track`
for one line, keeps `$defs/tracks` for version 1, and gains
`$defs/tracks_index`.

A bundle's manifest counts (`tracks`, `track_points`) are unchanged.

## The exporter (`export/bundle.py`)

- `write_bundle` writes `tracks.jsonl` a line at a time, recording each
  patrol's offset, length and counts, then writes `tracks.index.json`.
- It still builds the tracks in memory first. The extraction job has
  16 GiB and that is not the failure being fixed.
- `validate_bundle_dir` checks a version 2 bundle: each line against
  `$defs/track`, the index against `$defs/tracks_index`, and that the index
  covers the file exactly and each run's lines carry that patrol's uuid.
- `BUNDLE_SCHEMA_VERSION` is 2. The exporter no longer writes version 1.

## The library (`er_smart_sync`)

`Bundle.tracks` stops being a list. It becomes a track store with one
interface for both versions:

- `for_patrol(patrol_uuid) -> list[dict]`: that patrol's tracks, or `[]`.
- `points(patrol_uuid) -> int` and `count(patrol_uuid) -> int`.
- `patrol_uuids() -> set[str]`: the patrols that have tracks.

For version 2 the store holds the index and the path. `for_patrol` reads
`length` bytes at `offset`, parses each line, and checks each track against
`$defs/track`. It may be called from several threads at once (the import
can run with more than one worker), so each call does its own positioned
read and shares no file position.

For version 1 the store is built from the list that `tracks.json` parses
to, as today. Memory for a version 1 bundle is what it was.

`load_bundle`:

- accepts version 1 or 2 and refuses anything else, naming the versions it
  reads;
- for version 2, reads and validates `manifest.json`, `reference.json`,
  `patrols.json` and `tracks.index.json` up front, and checks the index
  against the size of `tracks.jsonl` (a missing file, or an index that
  runs past the end, is a `BundleError` at load);
- does not read `tracks.jsonl`.

The import (`patrol_import.py`) builds its by-day lookup from
`bundle.tracks.for_patrol(patrol["uuid"])` when it builds that patrol,
instead of one lookup for the whole bundle built at the start. Leg times
and track batches are computed exactly as before from those tracks.

A track line that is not valid JSON or does not match the schema raises
when its patrol is built. The import already treats an error in one patrol
as that patrol's failure and carries on; that is what happens here. Before,
one bad track refused the whole bundle at load.

## The app (`web/load_job.py`)

- The date window keeps only the selected patrols. It no longer filters a
  track list: tracks are fetched by patrol, so an unselected patrol's are
  never read.
- The plan's track point count is the sum of `points()` over the selected
  patrols.
- `web/requirements-load.txt` pins the new library release.

## What stays as it is

- `patrols.json` is read whole (58 MiB for the area that failed, about
  250 MiB parsed). It is the next file to grow with a site and is left for
  another ticket.
- A version 1 bundle with a very large `tracks.json` still needs the memory
  it needs today. Re-extracting the dataset writes version 2. `web/DEPLOY.md`
  says so; the app does not detect it.
- The dataset browser does not read the bundle.

## Step 2: stop copying the export into memory

After step 1 the job still downloads the export to `/tmp`: about 460 MiB
for the area that failed, so memory grows 1x with the track file where it
grew about 5.5x. Step 2 removes that, with no change to step 1's code,
because the library reads from a path.

Two candidates, tried on the 801 MiB area before either is adopted:

| | Ephemeral disk | Read-only bucket mount |
| --- | --- | --- |
| How | `--add-volume type=ephemeral-disk` and `JOB_WORK_DIR` on it; the job downloads as today | `--add-volume type=cloud-storage,readonly=true`; the job opens the bundle under the mount and skips the download |
| Fixed copy for the run | yes | no |
| To confirm | launch stage; what "live migration is not supported" means for a 22-hour load | read speed for many small positioned reads; behaviour if the dataset is re-extracted under a load |

The trial measures, for a plan of that area: peak memory, time to first
patrol, and total time. The choice and its flags go in
`.github/workflows/deploy.yml` and `web/DEPLOY.md`, and the load job's
memory comes back down from 8 GiB.

## Tests

Library:

- A version 2 bundle and the version 1 bundle of the same data give the
  same tracks for every patrol, the same leg times, and the same import
  calls.
- `for_patrol` reads only its own byte range: with every other byte of
  `tracks.jsonl` replaced by garbage, the patrol's tracks still load.
- Memory: importing one patrol from a bundle whose `tracks.jsonl` is far
  larger than that patrol's run allocates (by `tracemalloc`) less than a
  small multiple of the run, and `load_bundle` allocates nothing in
  proportion to `tracks.jsonl`.
- `load_bundle` refuses: version 3; a version 2 bundle with no
  `tracks.jsonl`; an index that runs past the file; an index entry with a
  negative or overlapping range.
- A bad line fails its own patrol and no other.
- `for_patrol` from several threads returns each patrol's own tracks.

App:

- The exporter's output passes `validate_bundle_dir`; the index covers the
  file; lines are grouped by patrol; counts match the manifest.
- `validate_bundle_dir` rejects an index that does not cover the file and
  a line under the wrong patrol.
- The load job's plan counts for a windowed and an unwindowed load match
  what version 1 gave for the same data.
- The existing end-to-end load test runs on a version 2 bundle.

## Acceptance (from the ticket)

- A plan and a load of an area with an 800 MiB track file complete in a
  job with 2 GiB: after step 1 with the download (about 460 MiB on `/tmp`
  plus the parsed patrols), and with room to spare after step 2.
- Peak memory does not grow with the area's track points: true of the
  process after step 1, and of the job as a whole after step 2.
- Counts in the plan are unchanged for an existing bundle.
- A dataset extracted before the change still loads.
