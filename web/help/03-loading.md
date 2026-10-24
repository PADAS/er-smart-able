# Loading a dataset

A load puts one conservation area from one dataset into one site. Start it from the dataset card with **Load**, choosing the conservation area, the site, what to load, the language of the labels, the roster group rangers are picked from, and the event category.

## Plan, then confirm

Every load starts as a **plan**: a dry run that talks to the site but writes nothing. It shows what the real run would create, update or deactivate, the findings it would stop on, and the patrols it would import. Read it, then press **Confirm and load**. If the plan already shows blocking findings the button says where the run will stop; the run still writes everything before that point, so confirming is the normal way to make progress.

## The four stages

A run works through the stages in order. Each is idempotent: a second run redoes it harmlessly and reaches whatever is left.

| Stage | What it writes to EarthRanger |
|---|---|
| **Event types** | The event category and one event type per SMART category, with their fields and dropdown choices, from the whole data model, or from one configurable model on a load of the data model only. Existing types are updated, not duplicated. |
| **Patrol setup** | Patrol types, the universal patrol fields, the ranger subjects (one per SMART employee who patrolled), their membership of the roster group, and the station choices. Anything the API cannot do becomes a finding: teams, icons, permissions. |
| **Preflight** | Writes nothing. Checks that the site has everything the patrols need: patrol types, teams, subjects, event types, fields. |
| **Patrols** | The patrols themselves, each with its legs, members, track and events from its waypoints. A ledger records every patrol as it lands, so a run can be resumed without duplicating anything. |

## The stop rule

After patrol setup and after preflight, the run stops if any finding is **blocking**. The load's status becomes `needs_attention` and the findings say what to do. Nothing written so far is undone. Fix the site, then press **Continue**: the run starts again from the first stage, which is quick because everything is already there, and reaches the patrols.

**Warnings** never stop a run. They record something worth knowing, such as a retired category or a waypoint whose events cannot be grouped.

Patrols that fail during the import do not stop the others. At the end they become one blocking finding listing each error; **Continue** retries only those patrols.

## Event category

The event category is the EarthRanger identifier the data model is pushed under. The default is `smart-<conservation area id>`. If a data model for this conservation area was already pushed to the site, for example with the command-line tool, use the identifier that push used, so the event types are updated rather than created a second time under a new category.

## Loading part of a dataset

**What to load** in the load dialog has two choices.

- **The data model and patrols**, the default. Leave **Patrols from** and **to** empty to load every patrol, or set one or both to load only the patrols that start on or between those days. A patrol's observations, photos and track come with it. Dates are the conservation area's own, as SMART recorded them. A patrol SMART stored without a start date is left out of any window. A window narrows only the patrols: the load still sets up the whole data model, so the steps it asks an admin to do, such as creating teams, cover every team in the conservation area, including teams only older patrols used.
- **The data model only**: the event types, the patrol types and their fields, the rangers as subjects, and the patrol roster. That is what a team needs to start patrolling and recording in EarthRanger without bringing its history across. It still stops on anything an admin must do on the site first, such as teams to create.

A later load into the same site can widen the window or add the patrols. Anything already imported is skipped. The load page and the dataset list name what each load wrote, such as "Data model only" or "Patrols from 2023-01-01 to 2024-12-31".

## Patrols, the whole data model and configurable models {#loading-models}

A SMART conservation area can have several **configurable models**: the forms its rangers carry on their phones, each a subset of the data model, such as one for ranger patrols and one for ecological monitoring. SMART does not record which form recorded a patrol observation, so on import there is no way to tell which form's event types an observation belongs to.

So a load with patrols always uses the **whole data model**. It contains every form's categories, so every observation has an event type, whichever form recorded it. Its event category is the home category, `smart-<conservation area id>` by default, and all patrol history lives there.

Each configurable model is then loaded on its own, as **the data model only**: pick it under **Configurable model** in the load dialog, or press its button on the page of a finished load. Its event types make only its categories and dropdown options active, under their own event category (`smart-<conservation area id>-<model name>` by default), and no historical observations are filed against them. They are there for teams to record with in EarthRanger from then on.

SMART's ecological surveys are different: each survey names the configurable model its observations were recorded with, so when smart-able migrates surveys, their observations can go to that model's event types. Surveys are not migrated yet.

## Long runs and continuation

A run imports every patrol with its observations and photos first, then every patrol's tracks. The progress bar shows the phase it is in, how fast it is going, and the time left in that phase.

How long a run takes depends on how fast the EarthRanger site writes, not on smart-able. Each observation takes about 0.8 seconds, and track points add a little, so a conservation area with 70,000 observations takes about a day. Two loads into two different sites run side by side at full speed; two into the same site would only slow each other.

A Cloud Run job may run for at most 24 hours, so at 22 hours the job stops taking new patrols, finishes the one in flight, saves its ledger, and starts a new execution of itself. The load's status is `continuing` while that happens and the page names the continuation it is timing. Nothing is lost and nothing is imported twice. A load may continue up to ten times before it is marked failed; that is far more than any dataset needs.

If a job is killed outright, by an outage for example, it cannot report. The load keeps its last status until its hold lapses, about 25 hours after the job started, and then the page offers **Continue**, which resumes from the ledger.

## Plan again and delete

**Plan again** runs a fresh plan for a load that is planned, stopped, failed or done, for example after fixing the site, to see what is left. **Delete this load** removes smart-able's record of the load, its ledger, plan and log. It removes nothing from EarthRanger.

Only one load of a given conservation area into a given site can be active at a time. Starting another is refused until the first finishes or stops.
