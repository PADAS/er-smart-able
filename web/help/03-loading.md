# Loading a dataset

A load puts one conservation area from one dataset into one site. Start it from the dataset card with **Load**, choosing the conservation area, the site, the language of the labels, an optional configurable model, the roster group rangers are picked from, and the event category.

## Plan, then confirm

Every load starts as a **plan**: a dry run that talks to the site but writes nothing. It shows what the real run would create, update or deactivate, the findings it would stop on, and the patrols it would import. Read it, then press **Confirm and load**. If the plan already shows blocking findings the button says where the run will stop; the run still writes everything before that point, so confirming is the normal way to make progress.

## The four stages

A run works through the stages in order. Each is idempotent: a second run redoes it harmlessly and reaches whatever is left.

| Stage | What it writes to EarthRanger |
|---|---|
| **Event types** | The event category and one event type per SMART category, with their fields and dropdown choices, from the data model (and the configurable model, if one was chosen). Existing types are updated, not duplicated. |
| **Patrol setup** | Patrol types, the universal patrol fields, the ranger subjects (one per SMART employee who patrolled), their membership of the roster group, and the station choices. Anything the API cannot do becomes a finding: teams, icons, permissions. |
| **Preflight** | Writes nothing. Checks that the site has everything the patrols need: patrol types, teams, subjects, event types, fields. |
| **Patrols** | The patrols themselves, each with its legs, members, track and events from its waypoints. A ledger records every patrol as it lands, so a run can be resumed without duplicating anything. |

## The stop rule

After patrol setup and after preflight, the run stops if any finding is **blocking**. The load's status becomes `needs_attention` and the findings say what to do. Nothing written so far is undone. Fix the site, then press **Continue**: the run starts again from the first stage, which is quick because everything is already there, and reaches the patrols.

**Warnings** never stop a run. They record something worth knowing, such as a retired category or a waypoint whose events cannot be grouped.

Patrols that fail during the import do not stop the others. At the end they become one blocking finding listing each error; **Continue** retries only those patrols.

## Event category

The event category is the EarthRanger identifier the data model is pushed under. The default is `smart-<conservation area id>`. If a data model for this conservation area was already pushed to the site, for example with the command-line tool, use the identifier that push used, so the event types are updated rather than created a second time under a new category.

## Long runs and continuation

A run imports roughly two patrols a minute. A Cloud Run job may run for at most 24 hours, so at 22 hours the job stops taking new patrols, finishes the one in flight, saves its ledger, and starts a new execution of itself. The load's status is `continuing` while that happens and the page names the continuation it is timing. Nothing is lost and nothing is imported twice. A load may continue up to ten times before it is marked failed; that is far more than any dataset needs.

If a job is killed outright, by an outage for example, it cannot report. The load keeps its last status until its hold lapses, about 25 hours after the job started, and then the page offers **Continue**, which resumes from the ledger.

## Plan again and delete

**Plan again** runs a fresh plan for a load that is planned, stopped, failed or done, for example after fixing the site, to see what is left. **Delete this load** removes smart-able's record of the load, its ledger, plan and log. It removes nothing from EarthRanger.

Only one load of a given conservation area into a given site can be active at a time. Starting another is refused until the first finishes or stops.
