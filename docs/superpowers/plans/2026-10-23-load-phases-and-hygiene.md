# Load Phases and Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a bundle in two phases (patrols and events, then tracks), post track points before the source assignment, bound every HTTP request with a timeout, and show per-phase progress on the load page.

**Architecture:** The ordering lives in er-smart-sync's `patrol_import.run_import`, which walks the selected patrols once per phase with the existing per-patrol loop and ledger. The hosted load job (`web/load_job.py`) sets a socket timeout, passes a worker count, and records the phase in the load's `progress`; the page (`web/static/app.js`) renders it. er-smart-sync is released and pinned in the load image last.

**Tech Stack:** Python 3.10+ (er-smart-sync), Python 3.12 (load job), pytest, vanilla JS.

**Spec:** `docs/superpowers/specs/2026-10-23-load-phases-and-hygiene-design.md`. Background: `docs/load-performance.md`.

**Repositories:** er-smart-sync is `~/padas/earthranger-smart-utils`; branch `feat/import-phases` from `fix/empty-attachment-skip` (so the release carries the empty-photo fix). smart-able is `~/padas/er-smart-able`; branch `feat/load-phases` from `fix/empty-attachments`. Run er-smart-sync tests with `.venv/bin/python -m pytest`, smart-able tests with `uv run pytest`.

## Global Constraints

- Nothing written changes: ids, event bodies, segment times, track batching, photo handling, ledger stages (`patrol`, `events`, `tracks`) and ledger file.
- Phase names are exactly `events` and `tracks`.
- Progress callback keys are exactly `{phase, total, done, failed, already_imported}`; `total` is the selected patrol count in both phases.
- `LOAD_NETWORK_TIMEOUT_SECONDS` defaults to `600`; `LOAD_WORKERS` defaults to `1`.
- One patrol's failure in either phase never stops the others.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The trufflehog pre-commit hook is global; commit from the repo's main checkout, not a linked worktree (see memory note on worktree hooks).

## Review Focus

1. **A continuation that resumes after phase one finished**: every patrol is ledger-skipped in phase one and phase two writes the tracks; no event is re-posted. Pinned in Task 2.
2. **A failure between posting points and assigning the source**: the re-run posts the points again (das answers 409, the client carries on) and then assigns. Pinned in Task 1.
3. **A stop at the soft deadline during phase one**: phase two does not start, and the run reports `stopped_early`. Pinned in Task 2.
4. **Loads recorded before this change** (no `phase` in `progress`) still render on the page as today. Checked by hand in Task 5.
5. **The phase boundary reaching the page promptly**: the job writes `progress` on a phase change even inside the 30-second/10-patrol throttle. Pinned in Task 4.

---

### Task 1: Track points before the source assignment (er-smart-sync)

**Files:**
- Modify: `src/er_smart_sync/patrol_import.py` (`_import_tracks`)
- Test: `tests/test_patrol_import.py`

**Interfaces:**
- Produces: `FakeAPI.log: list[str]`, appended `"create_events"`, `"post_observations"`, `"assign"` in call order (Task 2 uses it). `FakeAPI.fail_assign_once: bool`.

- [ ] **Step 1: Add `log` to `FakeAPI`** (append in `create_events`, `post_observations`, `assign_source`), and `fail_assign_once`: when true, `assign_source` sets it false and raises `ERClientException("assign failed")`.

- [ ] **Step 2: Write the failing tests**

```python
def test_track_points_are_posted_before_the_source_is_assigned(tmp_path):
    b = load_bundle(FIXTURE)
    api = FakeAPI(b)
    _run(api, b, tmp_path, skip_events=True)
    seq = [c for c in api.log if c in ("post_observations", "assign")]
    assert seq[0] == "post_observations" and seq[-1] == "assign"
    assert all(seq[i - 1] == "post_observations" for i, c in enumerate(seq) if c == "assign")


def test_a_failed_assignment_reruns_the_points_then_assigns(tmp_path):
    b = load_bundle(FIXTURE)
    api = FakeAPI(b)
    api.fail_assign_once = True
    r = _run(api, b, tmp_path, skip_events=True)
    (failed,) = r.failed
    r2 = _run(api, b, tmp_path, skip_events=True)
    assert not r2.failed
    keys = [(o["source"], o["recorded_at"]) for o in api.observations]
    assert len(keys) == len(set(keys))
    assert "tracks" in ImportLedger(tmp_path / "ledger.json", "site|ca").stages(failed)
    assert api.log[-1] == "assign"
```

- [ ] **Step 3: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/test_patrol_import.py -k "before_the_source or failed_assignment" -v`
Expected: the first FAILS (`seq[0] == "assign"`).

- [ ] **Step 4: In `_import_tracks`, per batch: get or create the source, post the points in lists of `OBSERVATION_BATCH`, then `api.assign_source(...)`, then add to `counts["track_points"]`.**

- [ ] **Step 5: Run the file's tests**

Run: `.venv/bin/python -m pytest tests/test_patrol_import.py -q`
Expected: all pass.

- [ ] **Step 6: Commit** `import-patrols: post a batch's track points before assigning its source` with a body naming the das per-point lookup it avoids (`docs/load-performance.md` in smart-able).

### Task 2: Two phases in `run_import` (er-smart-sync)

**Files:**
- Modify: `src/er_smart_sync/patrol_import.py` (`run_import`, `_import_one`)
- Test: `tests/test_patrol_import.py`

**Interfaces:**
- Consumes: `FakeAPI.log` (Task 1).
- Produces: progress callback dicts `{"phase": "events"|"tracks", "total": int, "done": int, "failed": int, "already_imported": int}`, one with `done == 0` at each phase start. `ImportResult` fields unchanged; `result.imported` = selected patrols whose ledger holds every wanted stage at the end; `result.failed[uuid]` = phase reasons joined with `"; "`; `result.counts["already_imported"]` counted once per run.

- [ ] **Step 1: Write the failing tests** (and replace `test_progress_is_reported_per_patrol`; change `test_a_set_stop_event_starts_no_more_patrols` to set the stop only when `p["done"] >= 1`)

```python
def test_tracks_start_after_every_patrols_events(tmp_path):
    b = load_bundle(FIXTURE); api = FakeAPI(b)
    _run(api, b, tmp_path)
    last_events = max(i for i, c in enumerate(api.log) if c == "create_events")
    first_points = api.log.index("post_observations")
    assert last_events < first_points


def test_progress_is_reported_per_phase(tmp_path):
    b = load_bundle(FIXTURE); api = FakeAPI(b); seen = []
    _run(api, b, tmp_path, progress=seen.append)
    assert [p["phase"] for p in seen] == ["events"] * 6 + ["tracks"] * 6
    assert seen[0]["done"] == 0 and seen[6]["done"] == 0
    assert seen[5]["done"] == seen[-1]["done"] == 5 and seen[-1]["total"] == 5
    assert set(seen[-1]) == {"phase", "total", "done", "failed", "already_imported"}


def test_a_patrol_whose_events_fail_still_gets_its_tracks(tmp_path):
    # reject one event of a tracked patrol: events fail, tracks land, the patrol is failed not imported
    ...


def test_a_patrol_not_created_closes_the_tracks_phase_as_failed(tmp_path):
    b = load_bundle(FIXTURE); api = FakeAPI(b); api.fail_patrol = "SMART_000003"; seen = []
    r = _run(api, b, tmp_path, progress=seen.append)
    (reason,) = r.failed.values()
    assert "boom" in reason and "; " not in reason
    assert seen[-1]["phase"] == "tracks" and seen[-1]["done"] == 5 and seen[-1]["failed"] == 1


def test_a_stop_in_the_events_phase_skips_the_tracks_phase(tmp_path):
    import threading
    b = load_bundle(FIXTURE); api = FakeAPI(b); stop = threading.Event()
    r = _run(api, b, tmp_path, progress=lambda p: p["done"] >= 2 and stop.set(), stop=stop)
    assert r.stopped_early and "post_observations" not in api.log


def test_a_rerun_with_events_done_goes_straight_to_tracks(tmp_path):
    b = load_bundle(FIXTURE); api = FakeAPI(b)
    _run(api, b, tmp_path, skip_tracks=True)
    api.log.clear(); api.calls.clear()
    r = _run(api, b, tmp_path)
    assert "create_events" not in api.log and "post_observations" in api.log
    assert len(r.imported) == 5 and r.counts["already_imported"] == 0
```

For `test_a_patrol_whose_events_fail_still_gets_its_tracks`: pick the first patrol whose leg has a track in `b.tracks` and set `api.reject_event` to one of its events' ids so the single-post retry also rejects it; assert that patrol's uuid is in `r.failed` and not in `r.imported`, that `api.observations` contains points from its source, and that its ledger stages include `tracks` but not `events`.

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/test_patrol_import.py -k "phase or tracks_start or still_gets or not_created or straight_to" -v`
Expected: FAIL (no `phase` key; tracks interleaved).

- [ ] **Step 3: Restructure `run_import`**

Compute `already = {uuid for selected if want <= ledger.stages(uuid)}` once; set `result.counts["already_imported"] = len(already)` and drop the increment in `_import_one`. Walk the selected patrols once per phase through the existing sequential-or-pool loop (extract it as a helper that takes the phase name and that phase's `want`): phase `events` with `want & {"patrol", "events"}`, phase `tracks` with `{"tracks"}` when `"tracks" in want`. In phase `tracks`, a patrol whose ledger lacks `patrol` is not walked: it counts `done` and `failed` in the phase with no new reason. Call `progress` with `done == 0` at each phase start. Check `stop` before each patrol in both phases; a stop in phase one ends the run without starting phase two. Join reasons per patrol with `"; "`. Build `result.imported` from the ledger after the last phase. `_reactivate` / `_retire` and `ensure_source_provider` keep wrapping the whole run.

- [ ] **Step 4: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including the worker tests (`_run_workers`) and the re-run tests (`already_imported == 5`).

- [ ] **Step 5: Commit** `import-patrols: import every patrol's events before any track`.

### Task 3: er-smart-sync docs and release

**Files:**
- Modify: `docs/cli-reference/import-patrols.md`, `docs/changelog.md`

- [ ] **Step 1: Document** in the import-patrols reference: the two phases, that a patrol whose events failed still gets its tracks and is reported failed, that a stop in the first phase leaves tracks for the next run, and that more than one `--workers` is slower on today's EarthRanger (link the analysis). Changelog entry `0.10.0` with the phases, the points ordering and the empty-attachment skip.

- [ ] **Step 2: Verify** `.venv/bin/python -m pytest -q` passes and `mkdocs build --strict` succeeds if mkdocs is installed in the venv.

- [ ] **Step 3: Commit**, push `feat/import-phases`, open the PR. **Stop here and ask the user** before merging and tagging `v0.10.0`; the tag is what Task 6 pins.

### Task 4: Load job — timeout, workers, phase progress (smart-able)

**Files:**
- Modify: `web/load_job.py` (`Runner.__init__`, `Runner.run`, `Runner._import`, `ErSmartSyncMigration.__init__`, `ErSmartSyncMigration.import_patrols`)
- Test: `tests/test_load_job.py`

**Interfaces:**
- Consumes: the callback dicts from Task 2.
- Produces: live `progress` = `{patrols_total, done, failed, skipped, events, track_points, phase, phase_started_at}`; final `progress` as today, without `phase`/`phase_started_at`. `migration_factory(..., workers=int)`.

- [ ] **Step 1: Make `FakeMigration.import_patrols` emit both phases**: a `done == 0` call then one per patrol with `phase="events"`, then the same with `phase="tracks"`, keeping today's `failed` and `already_imported` values. Accept and record `workers` in its factory.

- [ ] **Step 2: Write the failing tests**

```python
def test_live_progress_names_the_phase(env, monkeypatch):
    # capture every _update like test_the_log_tail_is_recorded_as_the_job_goes
    ...
    phases = [c["progress"].get("phase") for c in calls if c.get("progress")]
    assert "events" in phases and "tracks" in phases
    starts = {c["progress"]["phase"]: c["progress"]["phase_started_at"] for c in calls if c.get("progress", {}).get("phase")}
    assert starts["events"] <= starts["tracks"]

def test_a_phase_change_is_written_at_once(env, monkeypatch):
    # with the periodic throttle not due (fake clock frozen), the first "tracks" callback still produces a progress write

def test_the_network_timeout_is_set(env, monkeypatch):
    seen = []
    monkeypatch.setattr(load_job.socket, "setdefaulttimeout", seen.append)
    _run(env, "run", FakeMigration(), "queued")                       # default
    _run(env, "run", FakeMigration(), "queued", extra_env={"LOAD_NETWORK_TIMEOUT_SECONDS": "42"})
    assert seen == [600.0, 42.0]

def test_load_workers_reach_the_migration(env):
    # LOAD_WORKERS=3 in the job's env -> the factory is called with workers=3; absent -> 1
```

`test_run_imports_when_only_warnings_remain` keeps its exact final-progress assertion: it proves the final write carries no phase. Adapt `_run`'s signature if it has no way to pass env; follow how existing tests set `LOAD_SOFT_DEADLINE_SECONDS`.

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/test_load_job.py -k "phase or timeout or workers" -v`
Expected: FAIL.

- [ ] **Step 4: Implement**
  - `Runner.__init__`: `self.network_timeout = float(env.get("LOAD_NETWORK_TIMEOUT_SECONDS", 600))`, `self.workers = int(env.get("LOAD_WORKERS", 1))`.
  - `Runner.run`: `socket.setdefaulttimeout(self.network_timeout)` before building the migration; pass `workers=self.workers` to the factory.
  - `_import.progress`: track the current phase; on a change set `phase_started_at = now()` and force the write (the periodic log-tail push keeps its own cadence). Live `progress` adds `phase` and `phase_started_at`; `skipped` stays `already_imported`. The final write is unchanged.
  - `ErSmartSyncMigration`: accept `workers=1`; pass `ImportOptions(workers=workers)` and, when above one, `api_factory` building `ERPatrolAPI(ERClient(...same arguments...))`.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit** `load job: a network timeout, a worker setting, and the phase in progress`.

### Task 5: The load page and help (smart-able)

**Files:**
- Modify: `web/static/app.js` (`importSummary`, the dataset-card line near `l.progress.patrols_total`), `web/help/03-loading.md`, `web/DEPLOY.md` (the two new env vars)

- [ ] **Step 1: `importSummary(l, live)`**. When `live` and `p.phase`: `"Events: 720 of 2,761 patrols"` (`"Tracks: …"` in phase two), failed and already-there as today, the rate from `p.phase_started_at` and the phase's written count, and time left as `"about 3 h left in this phase, then tracks"` in phase one, `"about 40 min left"` in phase two. Otherwise (finished, or a load from before this change): `"2,761 of 2,761 patrols, 8 failed · 25 h"`, the elapsed time from the import row's `started_at` to `finished_at`, no per-minute rate. A live load with no `phase` keeps today's rate text.

- [ ] **Step 2: Help.** Replace the "roughly two patrols a minute" paragraph in `03-loading.md` with: the run imports every patrol's events first, then every patrol's tracks; the time is driven by EarthRanger's write speed, roughly 0.8 seconds per observation plus a little per track point, so a region with 70,000 observations takes about a day; the page shows the phase, its rate and the time left. Keep the continuation paragraph. Add `LOAD_NETWORK_TIMEOUT_SECONDS` and `LOAD_WORKERS` to the env table in `DEPLOY.md`.

- [ ] **Step 3: Verify**
  - `node --check web/static/app.js` prints nothing.
  - `uv run pytest tests/test_help.py -q` passes.
  - Run the service locally (the `run` skill) and look at the dev Camarines Norte load (old shape, no `phase`) and a local load from Task 4's fake: both render, and the finished one shows elapsed time.

- [ ] **Step 4: Commit** `load page: show the import phase, its rate and the time left`.

### Task 6: Pin the release (smart-able)

**Files:**
- Modify: `web/requirements-load.txt`

- [ ] **Step 1: After the user has tagged `v0.10.0`**, change the pin to `@v0.10.0`.
- [ ] **Step 2: Verify** `uv run pytest -q` passes and, if the load venv exists locally, `uv pip install --python <load venv> -r web/requirements-load.txt` resolves.
- [ ] **Step 3: Commit** `load job: er-smart-sync 0.10.0 (two phases, empty photos skipped)`, push `feat/load-phases`, open the PR.
