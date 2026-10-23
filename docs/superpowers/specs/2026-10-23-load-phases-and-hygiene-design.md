# Load in two phases, points before assignment, and a network timeout

Date: 2026-10-23. Status: approved design, not yet implemented.

## Intent

Make the import of a bundle's patrol history into EarthRanger as fast and
as predictable as the client side allows, without changing what is written.
The measurements in `docs/load-performance.md` show that event creation is
the floor (0.7 to 0.9 s per event, serialized per site by das) and that
nothing on the client side moves it. What the client does control is the
order of its writes, how it handles a request that never returns, and how it
reports where it is. This design covers those three things. The das-side
bulk ingest that would change the order of magnitude is a separate decision
for the EarthRanger team and is out of scope here.

## Goals

- Track points are posted before the source is assigned to the subject, so
  das skips its per-point subject-source lookup and queued status task and
  does one status and segment recompute per assignment instead.
- A load runs in two phases: every patrol with its events and photos first,
  then every patrol's tracks, so a large batch of points never sits between
  event writes and the event phase runs at a steady rate.
- A request that hangs fails the patrol after a bounded wait instead of
  stalling the job until its 25-hour stale rule.
- The load page shows which phase the run is in, progress and rate within
  that phase, and a time-left estimate that is honest about the phase after.
- The CLI (`import-patrols`) gets the same behavior.

## Non-goals

- Parallel event creation. The per-site lock makes it pointless; one worker
  stays the default. (Workers remain available for experiments; see below.)
- Any change to what is written: ids, event bodies, segment times, track
  batching, photo handling, the ledger's stages and files.
- das changes, or working around das internals beyond the write order.
- Skipping the patrol read before create, slimmer responses, or other
  per-call trims; measured as no gain.

## Anti-goals

- Writing anything twice, or losing the per-patrol failure isolation: one
  patrol's failure in either phase must not stop the others.
- A continuation or a re-run that redoes a finished phase.
- A progress bar that goes backwards or a rate that mixes the phases.

## Constraints and facts

- `patrol_import.run_import` imports each selected patrol through its
  remaining stages in one call (`_import_one` with `want` from
  `{"patrol", "events", "tracks"}` minus the skip options). The ledger
  records `patrol`, `events`, `tracks` per patrol and is what a re-run and a
  continuation resume from.
- `_import_tracks` assigns the source to the subject for the batch's day
  range, then posts the points in lists of 1,000.
- `run_import` reports progress by a callback per patrol with
  `{total, done, failed, already_imported}`; the hosted job
  (`web/load_job.py`) writes that to the load's `progress` and the page
  computes a rate from `stages.import.started_at`.
- The CLI sets a process-wide socket timeout of 600 s
  (`cli._set_network_timeout`); the hosted job, which calls er-smart-sync as
  a library, sets none.
- A `stop` event is checked before each new patrol; the job sets it at the
  soft deadline and the run returns `stopped_early`.
- Workers (`--workers`, `api_factory`) exist in er-smart-sync and the hosted
  job does not use them.

## Design

### er-smart-sync

**Two phases in `run_import`.** The selected patrols are walked twice. Phase
`events` imports, per patrol, the `patrol` stage and the `events` stage (with
photos). Phase `tracks` imports the `tracks` stage. Each phase uses the same
per-patrol loop as today (sequential, or the worker pool when workers are
configured), the same ledger checks (a stage already done is skipped), and
the same stop check between patrols. `skip_events` drops the events stage
from phase one (the patrol stage still runs); `skip_tracks` drops phase two.

A patrol's phase-two import runs whenever its `patrol` stage is done,
whether or not its events succeeded: tracks do not depend on events. A
patrol that failed in phase one and succeeds in phase two keeps its phase-one
error in `result.failed`; one that fails in both has both reasons joined
with `; `. `result.imported` lists the patrols that finished every wanted
stage. The counters and the exit code mean what they mean today.

**Points before assignment in `_import_tracks`.** For each batch: get or
create the source, post the batch's points, then assign the source to the
subject for the batch's range. A failure after the points are posted and
before the assignment is a failed patrol; the re-run posts the points again
(das skips the duplicates, as today) and then assigns.

**Progress per phase.** The callback's dict becomes
`{phase, total, done, failed, already_imported}`. `phase` is `events` or
`tracks`. `total` is the selected patrol count in both phases. `done` and
`failed` count within the phase and reset when it starts; a patrol that
phase two cannot walk because its `patrol` stage never landed counts as done
and failed in phase two at once, with its phase-one reason and no new write,
so each phase closes at `total`. `already_imported` is the whole-run count of
patrols that had nothing left to do in any wanted stage when the run began,
computed once and repeated in every call. The callback is called once with
`done == 0` when a phase starts, so the consumer learns the boundary.

**What the result means.** `result.imported` is the patrols with every
wanted stage done at the end of the run, read from the ledger after the last
phase (a patrol whose events failed and whose tracks succeeded is not in it).
`result.failed` maps each patrol with any failure to its reason, both phases'
reasons joined with `; `. The exit code and `format_result` keep their
meaning. A stop during phase one ends the run before phase two starts; the
continuation re-walks phase one from the ledger (one callback per patrol, as
a continuation does today) and then runs phase two.

### The hosted load job

**Progress document.** While the run is live, `progress` carries `phase`
and `phase_started_at`, with `done` and `failed` counting within the phase
and `skipped` the whole-run already-imported count; `patrols_total` stays
the selected count. The final write, on `done`, `needs_attention` or
`continuing`, clears `phase` and reports the whole run: `done` is the
patrols that finished every stage plus those that failed, `failed` the
patrols with any failure, `skipped` as above. The `import` stage row keeps
its times; `metrics` is `{imported, failed, skipped}` from the result as
today. A finished run shows no per-minute rate, since one would mix the
phases; it shows the elapsed time.

**Network timeout.** The job sets `socket.setdefaulttimeout` from
`LOAD_NETWORK_TIMEOUT_SECONDS` (default 600) before building the client,
as the CLI does. A request that times out raises in the patrol's stage, is
recorded as that patrol's failure, and the run moves on.

**Workers.** `LOAD_WORKERS` (default 1) is passed as `workers` with an
`api_factory` that builds a fresh `ERClient` per thread. Documented as "for
experiments; more than one is slower on today's EarthRanger".

### The load page

While live, the progress block names the phase: "Events: 720 of 2,761
patrols", then "Tracks: 300 of 2,761 patrols". The rate and the time left
are computed from `phase_started_at` and the phase's `done`, so the bar
restarts at the phase boundary and the estimate reads "about 3 h left in
this phase, then tracks" during phase one and "about 40 min left" during
phase two. A finished run reads "2,761 of 2,761 patrols, 8 failed · 25 h".
The dataset card's "N of M patrols" uses the same `done` and so reads the
phase's count while live and the whole run's when finished. The help page
replaces "roughly two patrols a minute" with the two phases and the
projection from `docs/load-performance.md`.

### Release and pin

er-smart-sync gets a release that includes the two-phase import, the points
ordering and the empty-attachment skip; `web/requirements-load.txt` pins it.

## Left to the builder

- Where the phase loop lives (a helper called twice, or a loop over phase
  specs) and how `_import_one` receives the phase's `want`.
- The exact progress keys, as long as the page and the CLI's summary
  (`format_result`) get what this design names.
- Test fixtures for the two-phase ordering (the existing FakeAPI records
  call order, which is enough to assert "no track points before the last
  event" and "points before assignment").
