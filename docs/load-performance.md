# Load performance: where the time goes when writing to EarthRanger

Measured 2026-10-22 and 2026-10-23 against phinney.staging.pamdas.org
(das release-2.148.1) and smart-migrations.dev.pamdas.org (das develop), with
er-smart-sync 0.9.0. Kept as the reference for why a load takes as long as it
does and what would change that. Numbers are server time per request as seen
by the client; the client itself is idle almost the whole run.

## Summary

- A load spends nearly all its time waiting for EarthRanger to write. The
  client's own work is a few percent.
- **Events are the floor.** Creating one event costs 0.7 to 0.9 seconds of
  server time on both sites, and das serializes event creation per site, so
  running more workers does not help. A region's load time is roughly its
  event count times 0.8 seconds, plus its track points times 0.005 to 0.1
  seconds.
- Region 05 Camarines Norte (2,761 patrols, 73,021 events, 1,153,038 track
  points) projects to about 25 hours on the dev site. Its rate per unit of
  work was flat for the whole run; it only looked like it slowed because the
  later patrols carry five times more events each.
- Getting a mid-size region into a few hours needs a bulk ingest path in das.
  Client-side changes can trim the rest and make runs predictable, but not
  change the order of magnitude.

## How it was measured

Every HTTP call er-smart-sync makes was timed (method, path, items, seconds)
by wrapping `ERClient._call`, `_get` and `_post_form`, and the CLI was run on
small samples of the Lawin Guinobatan bundle (16 waypoints and 376 track
points per patrol) into phinney staging with `--limit` and `--allow-blocking`.
The dev site's rate came from the Cloud Run job log (one "starting" line per
patrol) joined to the bundle's per-patrol event and point counts. The das
read-through is of the `das` repository at `aec9082c9` (2026-10).

## What one patrol costs

Phinney staging, one worker, site otherwise idle, 10 Guinobatan patrols,
26 seconds per patrol:

| Call | Share | Server cost |
| --- | --- | --- |
| `POST activity/events`, 20 events per request | 67% | 0.9 s per event, nearly constant |
| `POST observations`, up to 1,000 points per request | 24% | 0.015 to 0.17 s per point, batch to batch |
| `POST activity/patrols` | 2% | 0.5 s |
| `POST subject/<id>/sources`, `PATCH subject/<id>`, `GET activity/patrols/<id>`, `GET sources` | 5% | 0.2 to 0.3 s each |
| `POST activity/event/<id>/files` (photos) | about 1 s each, few per patrol | |

Dev site, the live Camarines Norte load, per half hour, with the time
normalized by work (one event, or thirty track points, is one unit):

| UTC | Patrols | Events | Points | Seconds per patrol | Seconds per unit |
| --- | --- | --- | --- | --- | --- |
| 19:00 | 20 | 202 | 74,445 | 74 | 0.55 |
| 20:00 | 151 | 463 | 43,348 | 12 | 0.94 |
| 21:00 | 82 | 816 | 32,786 | 22 | 0.96 |
| 22:00 | 101 | 1,228 | 30,924 | 18 | 0.80 |
| 23:00 | 50 | 1,411 | 26,938 | 36 | 0.78 |
| 23:30 | 35 | 1,730 | 17,472 | 54 | 0.81 |

The seconds per patrol tripled while the cost per unit of work stayed
between 0.5 and 1.0. The bundle's later patrols simply carry far more events.

## What das does per request

File references are into the `das` repository.

**One event** (`activity/views/events/base.py:815`, the list POST): the whole
list runs in one transaction, and the list serializer calls the single-event
create once per item. Each item: `full_clean()` with a query per foreign key
(`activity/models.py:1083`); a revision row (`revision/manager.py:254`); the
event-details row, notes and related subjects
(`activity/serializers/events.py:422`); for a collection child, a lookup of
the parent and a relationship row; the patrol-segment link, whose receiver
runs a patrol query per event (`activity/signals.py:159`); and, after commit,
a realtime publish, an alert-rules Celery task and a webhook flush per event
(`activity/signals.py:52`). The response then serializes every event again
with its relationships, notes, files and revision history.

**The per-site lock.** `Event` and `Patrol` take a serial number through
`SerialNumberModelMixin` (`core/mixins.py:82`): each insert runs
`pg_advisory_xact_lock` keyed on the site and the model, then `MAX+1`. A
transaction-level advisory lock is released only when the outermost
transaction commits, and the list view holds one transaction for the whole
list, so the first event of a 20-event request takes the site's event lock
and holds it until all 20 are written. Every other event write to that site,
from another import worker or from a ranger's phone, waits. The event
throttle, when a site has it enabled, charges a list of N events as N units
for exactly this reason (`activity/throttles.py:222`).

**One track point** (`observations/views/observations.py:199`): one
transaction for the list, one row insert per point, no `bulk_create`. For
each point the `post_save` receiver (`observations/signals.py:71`) runs a
subject-source range query and, for a point older than a week, queues a
subject-status Celery task per matching assignment, after commit, from the
request thread. A list with one duplicate point is rolled back and redone
one row at a time in savepoints; 409 means nothing was new.

**One photo** (`activity/views/events/files.py:85`): the upload to storage
is synchronous; thumbnails are a Celery task. Saving the file row also
re-saves the event, which repeats its validation, writes another revision and
fires the update signals, including a save of each collection parent.

**Not there**: no bulk, import or silent mode on any of these endpoints; no
flag to skip history or notifications. The CSV observation import
(`observations/views/csv_import.py`) only moves the same row-by-row inserts
onto Celery. No DRF throttle is on by default; the event throttle
(`EVENTS_CREATE_THROTTLE_ENABLED`) defaults to 600 events a minute and ten
POSTs in flight per site when on. The API runs gunicorn with 4 workers and 2
threads per pod, 2 to 16 pods, so HTTP concurrency is available; the event
lock is what serializes.

## What was tried from the client

Each on phinney staging, alternating with a baseline where possible.

| Change | Result |
| --- | --- |
| Four workers, one connection each | Slower than one: 84 s per patrol against 26. Event requests queued on the lock (16 to 340 s each) and point batches slowed to 0.19 s a point. |
| Slimmer event response (`include_updates`, `include_notes`, `include_related_events`, `include_files` false) | No measurable gain: 0.67 to 0.9 s per event against 0.78 to 0.83 in the two paired runs. `include_details=false` must never be sent on a POST: it drops `event_details` from the serializer, and das rejected those lists. |
| Track points posted before the source is assigned to the subject | Once 20 times faster (0.005 against 0.1 s a point); once no change (0.066 against 0.08). It removes the per-point lookup and queued task, and das recomputes status and segments for the range when the assignment lands (`observations/signals.py:153,234`), so it is correct; the gain depends on what else the server is doing. |
| Bigger or smaller event lists | The cost is per event; 20 keeps a request under the 30 s gateway timeout. |

Two observations about phinney staging itself: after a large point batch,
the event writes that followed slowed 10 to 20 times (0.7 s to 13 s each)
for tens of minutes, and reads stayed fast; and one `POST observations`
hung for many hours, which the hosted load job, having no HTTP timeout,
would also have waited through. The dev site showed neither.

## Projection

Hours for a load at today's rates, with a healthy site:

    (events × 0.8 s + track points × 0.03 s) / 3600

| Bundle | Patrols | Events | Points | Projected |
| --- | --- | --- | --- | --- |
| Region 05 Albay | 1,527 | 13,763 | 285,181 | about 5 h |
| Region 05 Guinobatan | 1,038 | 16,796 | 391,031 | about 7 h |
| Region 05 Camarines Norte | 2,761 | 73,021 | 1,153,038 | about 26 h |

A Cloud Run job execution ends at 22 hours and the load continues in a new
one; that path is designed for this and was exercised by Camarines Norte.

## Options

1. **A bulk ingest path in das.** For a historical import: insert a list of
   events in one statement with serial numbers assigned under one lock
   acquisition, bulk revisions, one follow-up task per batch instead of per
   event; the same for observations, with one status and segment recompute
   per source and range at the end. This is the only route to a few hours
   per region. It is a das change, owned by that team.
2. **Client-side ordering and hygiene** (er-smart-sync and the load job):
   points before the assignment, all patrols and events in one phase and all
   tracks in a second so point batches never sit between event writes, an
   HTTP timeout, and clear per-phase progress. A modest gain on a healthy
   site and predictable rates. Designed in
   `docs/superpowers/specs/2026-10-23-load-phases-and-hygiene-design.md`.
3. **Parallel loads across sites.** The lock is per site, so two regions into
   two sites at once already run at full speed each.
4. **Set expectations** with the projection above; the page shows the
   measured rate and the time left.

Decision as of 2026-10-23: build option 2 now; the team decides on option 1.
