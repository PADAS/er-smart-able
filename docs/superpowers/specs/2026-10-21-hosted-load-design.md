# Hosted load: migrate a dataset into EarthRanger from the web app

Date: 2026-10-21. Status: approved design, not yet implemented.

## Goal

An allowed user who has a `ready` dataset in the hosted smart-able app
points it at an EarthRanger site and has the app run the SMART patrol
migration there, unattended, with the plan, progress, outcome and every
place the site needs a human visible in the app. A support person can
migrate a conservation area without a checkout of smart-able or
er-smart-sync.

What "migrate" means today is what er-smart-sync can import: the event data
model, the patrol configuration, and the patrol history (patrols, legs,
members, waypoint observations as events, the leaders' tracks). Independent
incidents are not in the bundle or the importer yet; they are a separate
spec covering smart-able's extraction, browser and bundle and er-smart-sync's
importer. This design needs no change when they land.

## Constraints and facts the design rests on

- The hosted app (`web/`) is a FastAPI service plus one Cloud Run Job per
  extraction, with Firestore for metadata and a private GCS bucket for files,
  and a local backend that mirrors both for development and tests. The load
  follows the same shape.
- The extraction job already runs `./smart-able all`, which writes the
  migration bundle under `work/export/<ca_id>/bundle/`, but only `work/site/`
  is published. The bundle is lost with the job's disk.
- er-smart-sync's runbook is `datamodel`, `patrol-datamodel`, an admin
  checklist of steps its API cannot do today (enable the `patrol_schemas`
  preview feature, create teams, create the roster group, pick icons, grant
  permissions), `patrol-preflight`, then `import-patrols`. EarthRanger's API
  will later allow the checklist steps; until then the job must stop and
  report them. That stop-and-report shape is designed to be reused.
- The import is slow: about two patrols a minute per site, so 1,500 patrols
  take about 13 hours. It is resumable: `import-ledger.json` beside the
  bundle records what each patrol reached, and a re-run writes nothing twice.
  A Cloud Run Job task runs at most 24 hours.
- er-smart-sync pins pydantic 1.x; the web service needs pydantic 2. They
  cannot share a virtualenv.
- `patrol-preflight` already renders findings as JSON (`Finding.to_dict`).
  `patrol-datamodel`'s checklist is a list of typed `ChecklistItem` objects
  rendered only as Markdown. The dry-run client logs its writes as lines.

## Decisions taken in brainstorming

| Question | Decision |
| --- | --- |
| Scope of "load" | The whole runbook, in one run that stops and reports where a human is needed. |
| EarthRanger credentials | Sites are registered once in the app, token in Secret Manager, shared like datasets. |
| Writing to a customer site | Plan first (dry run), the operator confirms, then the real run. |
| Runs longer than a job task | Continue automatically, with a cap on continuations. |
| Dataset deleted | Its loads are deleted with it. The EarthRanger data stays. |
| Where er-smart-sync runs | A second Cloud Run Job, from the extraction image plus its own venv for er-smart-sync, calling it as a library. |

## Data

### `datasets`, one new field

`export`: a list written by the extraction job from each bundle's
`manifest.json`, one entry per conservation area:
`{ca_id, name, languages, configurable_models: [{uuid, label}], patrols,
timezone}`. Absent on datasets extracted before this change; the UI reads
that as "re-extract to enable loading" and the API refuses to load them.

### `sites`

One EarthRanger site an operator can load into.

| Field | Meaning |
| --- | --- |
| `name` | what the operator called it |
| `url` | normalized to the host, e.g. `phinney.staging.pamdas.org` |
| `owner_uid`, `owner_email`, `shared_with` | as on datasets |
| `secret_name` | the Secret Manager secret holding the token, `smart-able-site-<id>` |
| `token_hint` | the token's last four characters |
| `checked_at`, `checked_as` | when the token was last verified and the ER username it resolved to |
| `created_at`, `updated_at` | |

The token is never written to Firestore or to a log. The local backend keeps
it in `web-data/secrets/<secret_name>`, for development only.

### `loads`

One attempt to put one conservation area of one dataset into one site.

| Field | Meaning |
| --- | --- |
| `dataset_id`, `ca_id`, `site_id` | what is loaded where |
| `owner_uid`, `owner_email` | who created the load |
| `options` | `{language, configurable_model, roster_group, event_category}`; `configurable_model` is a uuid or null, `roster_group` a name or null, `event_category` the ER event-category identifier the data model is pushed under (2-30 characters of `[A-Za-z0-9_-]`, default `smart-<ca id>`; use the identifier an earlier CLI push used). The timezone comes from the bundle. |
| `status` | `planning`, `planned`, `queued`, `running`, `continuing`, `needs_attention`, `done`, `failed` |
| `stage` | `datamodel`, `patrol_datamodel`, `preflight`, `import`; the stage the job is in or stopped in |
| `stages` | one row per stage this execution has reached, keyed by stage name: `{status, started_at, finished_at, metrics}`. `status` is `running`, `done`, `stopped` (the stop rule) or `failed`. `metrics` is what the stage did: the datamodel stats, the patrol-datamodel stats, `{blocking, warnings, patrols}` for preflight, `{imported, failed, skipped}` or, for a plan, `{planned, already_done}` for the import. Reset when an execution starts. |
| `mode` | `plan` or `run`: what the latest execution did, so the page can word the stage metrics as "to create" or "created" |
| `plan` | the dry run's grouped write list (below) |
| `findings` | the list of findings (below), replaced on every execution |
| `progress` | `{patrols_total, done, failed, skipped, events, track_points, since}`; `since` is when the import stage started, for a rate |
| `execution`, `claimed_at`, `started_at`, `continuations` | the execution bookkeeping, as for extraction plus a continuation count |
| `log_tail`, `error` | as for extraction |
| `created_at`, `updated_at` | |

### Bucket layout, under the existing `datasets/<id>/`

- `export/<ca_id>/`: the bundle, the XML files and `datamodel.json`,
  published by the extraction job from `work/export/<ca_id>/`. The bundle's
  attachments duplicate photos already under `site/attachments/`; accepted
  for simplicity.
- `loads/<load_id>/`: `import-ledger.json`, `checklist.json`, every
  `patrol-datamodel-run-*.json` undo record and `segment-schema-before-*.json`,
  `plan.json`, `findings.json`, `log.txt`.

### The plan

`plan.json`, written by plan mode, grouped so the UI can show counts with
expandable lists:

```json
{
  "event_categories": {"create": [...], "update": [...], "unchanged": 3},
  "event_types": {"create": [...], "update": [...], "unchanged": 27},
  "patrol_types": {"create": [...], "update": [...]},
  "universal_patrol_fields": "write" | "merge" | "skip",
  "choices": {"create": [...], "update": [...]},
  "subjects": {"create": [...], "update": [...], "deactivate": [...]},
  "roster": {"group": "Rangers", "add": 12},
  "patrols": {"total": 1527, "first": "2019-03-04", "last": "2024-11-30",
              "already_done": 38, "events": 9870, "track_points": 412000}
}
```

Each list entry is `{value, label}` and lists are capped at 200 entries
with a `more` count, so a document stays well under Firestore's size limit.

### A finding

The reusable stop-and-report unit:

```json
{"stage": "patrol_datamodel", "code": "teams_missing", "severity": "blocking",
 "title": "7 teams need to be created",
 "detail": "...", "fix": "In EarthRanger, create these teams ...",
 "affected": {"count": 11, "patrols": ["e3f1...", "..."]}}
```

`severity` is `blocking`, `warning` or `info`. `fix` is what a human does on
the site, in the words er-smart-sync already uses in `checklist.md` and the
preflight report. `affected.patrols` holds at most 50 SMART uuids; the count
is exact. Checklist items map to findings with `stage: patrol_datamodel`;
preflight findings with `stage: preflight`; failed patrols at the end of an
import become one finding with `stage: import`, code `patrols_failed`, and
each patrol's error in `detail`.

## The load job

`web/load_job.py`. Runs as Cloud Run Job `smart-able-load` with `LOAD_ID`
in the environment, or as a local subprocess started by the service. It
runs in its own virtualenv, built into the job image, that holds
er-smart-sync (pinned) and the Google client libraries, and imports
`web/store.py`, which needs neither pydantic.

### Setup

1. Claim the load as the extraction job does (`running`, `started_at`).
2. Fetch `export/<ca_id>/` to the work directory, and `loads/<load_id>/`
   beside it, so the ledger and undo records are where er-smart-sync expects
   them.
3. Read the site token from Secret Manager. A token ER rejects on the first
   call ends the run as `needs_attention` with one blocking finding, code
   `site_token_rejected`, fix "register the site again with a working token".
4. Build er-smart-sync's ER client and, in plan mode, wrap it in the
   existing `DryRunERClient` with a plan collector attached.

### Stages

Each stage sets `stage` and its `stages` row on the load as it starts and
closes the row with its metrics when it ends; the outcome closes a row still
open as `stopped` or `failed`. Every one of those writes, and the periodic
progress write, carries the log tail so far, so the page shows the log while
the job runs. Each stage appends to `log.txt`.

1. **datamodel**: push `datamodel.xml` and, when `options.configurable_model`
   is set, that configurable model, with the bundle passed so inactive and
   parent categories old observations use get event types. Equivalent to
   the runbook's `datamodel --from-file --cm-from-file --bundle` call.
2. **patrol_datamodel**: patrol types, universal patrol fields, choices,
   subjects, roster. Writes `checklist.json` and the undo records. Its items
   become findings.
3. **preflight**: the report's findings are appended.
4. **import**: `import-patrols` over the whole bundle, one worker, with the
   ledger. A progress callback updates `progress` every thirty seconds or
   every ten patrols, whichever comes first, and pushes the ledger to the
   bucket at the same cadence and on every exit.

### Plan mode

`MODE=plan`. Runs stages 1 to 3 through the dry-run client and stage 4 as a
count from the bundle and the ledger. Writes `plan.json` and `findings.json`,
sets `status: planned`. Nothing is written to EarthRanger.

Because a plan writes nothing, its preflight (stage 3) reports as missing
whatever stages 1 and 2 would create. Those preflight findings, by code
(`event_types` with no active event type, `patrol_types`, `segment_schema`,
`subjects`, `choices`; `CREATED_BY_RUN` in `web/findings.py`), become
`info` with the title prefixed "Will be created by this load: ". Every other
finding keeps its severity: teams, the roster group, the preview feature,
permissions, the timezone, the collection type, and ambiguous or
variant-only event types are not created by a run. A `planned` load can be
confirmed even with blocking findings left: the run writes what the plan
lists, re-runs preflight for real after stages 1 and 2, and stops at what
is still blocking.

### Run mode

`MODE=run`. Runs all four stages for real. The stop rule applies after
stages 2 and 3: if any finding so far is blocking, save the findings, set
`needs_attention`, exit 0. What was written stays; every stage is
idempotent, so the next run redoes the cheap stages and reaches the import
when the site is ready. Warnings never stop the run. After stage 4, failed
patrols become one blocking finding and the load is `needs_attention`;
otherwise `done`.

An exception in any stage sets `failed` with the error and log tail.

### Continuation

The job records its start. If stage 4 is still running at the soft
deadline (`LOAD_SOFT_DEADLINE_SECONDS`, default 79200, 22 hours), it sets
er-smart-sync's stop event, waits for the running patrols, pushes the
ledger, sets `continuing` and `continuations + 1`, starts the next
execution of `smart-able-load` for the same load, and exits 0. The service
and the jobs share one runtime service account, which can already start
job executions. Above `LOAD_MAX_CONTINUATIONS` (default 10) the job sets
`failed` with "the import is not finishing after N continuations" instead.

A job killed outright (memory, the 24-hour cap) cannot record anything.
The hold lapses after `LOAD_STALE_AFTER_SECONDS` (default 90000, 25 hours)
as for extraction, and the load shows Continue. The ledger pushed at the
last checkpoint bounds the lost work to a few patrols.

### Required er-smart-sync additions

Each is small and lands in er-smart-sync before this feature is built. The
implementation plan verifies each against the current code first.

1. `patrol_datamodel`: return the checklist as a list of dicts (`code`,
   `title`, `detail`, `fix`, `affected`) alongside the Markdown it writes.
2. `patrol_import.run_import`: a `progress` callback called per patrol with
   the running totals, and a `stop` event checked before each new patrol.
3. The dry-run client: a collector that records each planned write as data
   (`kind`, `action`, `value`, `label`), so the plan is built from objects
   rather than parsed from log lines.
4. The from-file datamodel push (`datamodel --from-file --cm-from-file
   --bundle`) reachable as a function, not only through the Click command.
5. Pin a released version in smart-able's load venv.

## API

### Sites

| Route | Who | What |
| --- | --- | --- |
| `GET /api/sites` | any allowed user | sites the user owns or is shared on |
| `POST /api/sites` `{name, url, token}` | any allowed user | verifies the token with one `GET /api/v1.0/user/me` against the site, stores it in Secret Manager, creates the doc with `checked_as`. A rejected token is a 400 carrying ER's reason; nothing is stored. |
| `DELETE /api/sites/{id}` | owner | deletes the doc and the secret. Loads that reference the site remain readable; Continue on them is refused with 409 "the site was removed". |
| `POST /api/sites/{id}/share` `{email}`, `DELETE /api/sites/{id}/share/{email}` | owner | as for datasets |

### Loads

| Route | Who | What |
| --- | --- | --- |
| `POST /api/datasets/{id}/loads` `{ca_id, site_id, options}` | read on the dataset and on the site | creates the load as `planning` and starts a plan execution. 400 if the dataset has no `export` or the `ca_id` is not in it; 409 if a load for the same dataset, conservation area and site is active. |
| `GET /api/datasets/{id}/loads` | read on the dataset | the dataset's loads, newest first |
| `GET /api/loads/{id}` | read on the dataset | the load with plan, findings, progress and log tail |
| `POST /api/loads/{id}/run` | read on the dataset and on the site (403 without the site) | `planned` or `needs_attention` → `queued`, starts a run execution. Confirm and Continue are the same call. 409 if active, or if the site is gone. |
| `POST /api/loads/{id}/replan` | read on the dataset and on the site (403 without the site) | `needs_attention`, `failed` or `done` → `planning`, starts a plan execution |
| `DELETE /api/loads/{id}` | read on the dataset | when not active; removes the folder and the doc, never the EarthRanger data |
| `GET /api/loads/{id}/files/{name}` | read on the dataset | `checklist.json`, `plan.json`, `findings.json`, `log.txt`, any undo record |

"Active" means `planning`, `queued`, `running` or `continuing` with the
hold not yet lapsed, via the same claim transaction and stale rule as
extraction. The claim is for the target, not only the load: creating,
running or replanning a load is refused (409) while any other load of the
same dataset, conservation area and site is active, decided inside the
same transaction, so two planned loads for one target cannot both run.
The log tail goes to anyone who can read the dataset: it names the site
and the patrols, never the token.

Deleting a dataset deletes its loads and their folders; it is refused (409)
while any of its loads is active. As a backstop, a running import checks
every push cycle that its load still exists and stops if it does not.

## UI

All in the existing single page (`web/templates/index.html`,
`web/static/app.js`).

- **Sites panel** beside the dataset list: a table of name, host, "as
  <checked_as>", owner, shared with; an Add form (name, URL, token) with one
  line saying a shared site lets the other person write to it with your
  token; Share and Remove on sites you own.
- **Load into EarthRanger** on each `ready` dataset card. Opens a form:
  conservation area (preselected when there is one), site, label language
  from the bundle's languages, configurable model or none, roster group
  name (optional), event category (prefilled with the default). A dataset without `export` shows "re-extract this dataset
  to enable loading" in its place.
- **Loads on the card**, one line each: site, conservation area, status,
  and "412 of 1,527 patrols" while running. Clicking opens the load page.
- **The load page**, one view for every status:
  1. A stage table: one row per stage with its status (pending, running
     with a pulsing marker and elapsed time, done, stopped, failed, or
     interrupted when the hold lapsed), how long it took, and what it did
     from the row's metrics; during the import, the live counts with the
     rate and a rough time left. Under it, while active, a heartbeat line:
     how long the load has run and how long since the job last reported.
     Loads from before the table render it from `stage` and `status`.
  2. The plan, as grouped counts with expandable lists.
  3. Findings, blocking first, each with its title, detail and fix text, and
     the affected count. Beside the list: **Confirm and load** when
     `planned`, **Continue** when `needs_attention`, **Plan again** when
     `planned`, `needs_attention`, `failed` or `done`. When a `planned` load
     still has blocking findings the button reads "Confirm and load (stops
     at N blocking)", with one line saying the run will write what the plan
     lists and then stop at those findings until they are fixed.
  4. Progress as a bar with the counts, the log (open while the load is
     active, a collapsed tail afterwards), and downloads of the files.
- Polling every few seconds while a load is active, like the dataset list
  during extraction.

## Infrastructure

- Cloud Run Job `smart-able-load`, deployed by `deploy.yml` beside the
  extract job from the same image, with a 24-hour task timeout and 2 GiB of
  memory. The job's entrypoint is the load venv's Python running
  `web/load_job.py`.
- `web/Dockerfile.job` builds the load venv: `uv venv /opt/load && uv pip
  install --python /opt/load er-smart-sync==<pinned> google-cloud-firestore
  google-cloud-storage google-cloud-secret-manager google-cloud-run`.
- `main.tf`: enable Secret Manager; grant the runtime service account
  `roles/secretmanager.admin` restricted by IAM condition to secrets whose
  name starts with `smart-able-site-`, so it can create, read and delete
  site tokens and nothing else. It already has `roles/run.developer`, which
  the load job uses to start its continuation.
- New service and job env vars: `LOAD_JOB` (default `smart-able-load`),
  `LOAD_SOFT_DEADLINE_SECONDS`, `LOAD_STALE_AFTER_SECONDS`,
  `LOAD_MAX_CONTINUATIONS`.
- The extraction job's memory and timeout are unchanged. Its one new duty
  is publishing `work/export/` and writing `export` on the dataset.

## Error handling summary

| Situation | What happens |
| --- | --- |
| Token rejected at run time | `needs_attention`, one blocking finding `site_token_rejected`; no retries |
| Site deleted while a load exists | the load stays readable; run and replan refused with 409 |
| Dataset has no bundle | the form is not offered; the API refuses with 400 |
| ER rate limits or 5xx during import | er-smart-sync's per-patrol retry; survivors recorded in the ledger as failed; the run ends `needs_attention` with the `patrols_failed` finding; Continue retries only those |
| Blocking finding after stage 2 or 3 | `needs_attention`, stage recorded; Continue reruns from stage 1 |
| Soft deadline in stage 4 | graceful stop, ledger pushed, next execution started |
| Too many continuations | `failed` with the reason |
| Job killed outright | hold lapses after the stale window; Continue offered |
| Exception anywhere | `failed` with error and log tail |

## Testing

- Store tests, both backends, with a fake Secret Manager: create, share and
  delete sites; secrets created and deleted with them; load claims and the
  stale hold; dataset deletion cascading to loads and their folders.
- Load job tests against a fake er-smart-sync layer: stage order; the stop
  rule on a blocking finding after stage 2 and after stage 3; warnings not
  stopping; continuation at the soft deadline and the cap; findings and plan
  shapes; ledger push cadence.
- API tests: permissions on every new route; the 409 on a duplicate active
  load and on a removed site; the 400s; token verification on site
  registration against a fake ER.
- One end-to-end test on the local backend with the synthetic SMART
  database in `tests/`: extract publishes `export` and the bundle, a plan
  execution runs through er-smart-sync's dry-run client for real, and the
  plan has the expected counts.
- A manual check against phinney staging with Guinobatan's bundle, which is
  partially imported there: the hosted plan reports the already-done count
  from a ledger seeded with the CLI's, and a run skips those patrols.

## Out of scope

- Independent incidents (separate spec).
- Undo from the app. The undo records are downloadable; undoing stays a
  documented manual procedure in er-smart-sync.
- More than one worker. The measured gain is at most 1.2×, and the hosted
  job runs in the site's cloud region already.
- Scheduling or recurring sync. A load is one migration.
