# Loading a dataset

A load puts one conservation area from one dataset into one site. Start it from the dataset page with **Load into EarthRanger** (on the Overview or Loads tab), choosing the conservation area, the site, the language of the labels, an optional configurable model, the roster group rangers are picked from, and the event category.

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

The event category is the EarthRanger category that the event types this load creates go into. The default is `smart-<conservation area id>`, or `smart-<event type set name>` for a load with a configurable model. When the site already has this load's event types, they stay in the category they are in and new ones join them there, whatever is entered here. The load page names that category once the plan is made.

## Several conservation areas in one site

Conservation areas that use the same data model share its event types on a site, so one query covers all of them.

- **Without a configurable model**, every load into the site writes the same set of event types and dropdown lists.
- **With a configurable model**, loads with the same **event type set** name share one set. The name is the configurable model's name unless you change it. Give it another name to keep a model's event types apart from another model with the same name. Give two models one name to put them together.

A load only adds to a set. It creates the event types and dropdown options the site lacks and updates the fields of those it has. It never deactivates an option or an event type, and never moves an event type to another category. So an option or event type removed from SMART stays active on the site until an administrator turns it off there.

If this conservation area's model differs from what the site already has under the same name, the plan says so in a warning that lists the event types the load would change.

A conservation area loaded before event types were shared keeps its own event types on that site. The load page says so, and the set name does not apply.

## Loading part of a dataset

**What to load** in the load dialog has two choices.

- **The data model and patrols**, the default. Leave **Patrols from** and **to** empty to load every patrol, or set one or both to load only the patrols that start on or between those days. A patrol's observations, photos and track come with it. Dates are the conservation area's own, as SMART recorded them. A patrol SMART stored without a start date is left out of any window. A window narrows only the patrols: the load still sets up the whole data model, so the steps it asks an admin to do, such as creating teams, cover every team in the conservation area, including teams only older patrols used.
- **The data model only**: the event types, the patrol types and their fields, the rangers as subjects, and the patrol roster. That is what a team needs to start patrolling and recording in EarthRanger without bringing its history across. It still stops on anything an admin must do on the site first, such as teams to create.

A later load into the same site can widen the window or add the patrols. Anything already imported is skipped. The load page and the dataset's Loads tab name what each load wrote, such as "Data model only" or "Patrols from 2023-01-01 to 2024-12-31".

## Long runs and continuation

A run imports every patrol with its observations and photos first, then every patrol's tracks. The progress bar shows the phase it is in, how fast it is going, and the time left in that phase.

How long a run takes depends on how fast the EarthRanger site writes, not on smart-able. Each observation takes about 0.8 seconds, and track points add a little, so a conservation area with 70,000 observations takes about a day. Two loads into two different sites run side by side at full speed; two into the same site would only slow each other.

A Cloud Run job may run for at most 24 hours, so at 22 hours the job stops taking new patrols, finishes the one in flight, saves its ledger, and starts a new execution of itself. The load's status is `continuing` while that happens and the page names the continuation it is timing. Nothing is lost and nothing is imported twice. A load may continue up to ten times before it is marked failed; that is far more than any dataset needs.

If a job is killed outright, by an outage for example, it cannot report. The load keeps its last status until its hold lapses, about 25 hours after the job started, and then the page offers **Continue**, which resumes from the ledger.

## Giving rangers accounts {#rangers-accounts}

Patrol setup creates one subject per SMART employee who appears on a patrol or is still employed, and the import puts their patrols, tracks and reports on it. A ranger who then uses EarthRanger Mobile needs a user account **linked to that subject**: a user's tracks go to its linked subject, and the events they report carry it as *reported by*. Without the link, their first login creates a second subject and the history splits.

The load page's **Rangers** section, and the dataset's **Rangers** tab (which shows the most recent load that reached patrol setup), list every one of those people, with the name exactly as it is on the site, whether the person is still active in SMART, and two patrol counts: on the patrols this load imports (its date window, if one was set) and in the whole dataset. A still-employed ranger with no patrols shows 0, and a data-model-only load, which imports no patrols, shows only the whole-dataset count. The CSV download has the same rows plus an empty email column.

A row marked *employee record deleted in SMART* is a patrol member whose employee record no longer exists; its subject is named by an identifier. Nobody can sign in as it, so it needs no account.

To give a ranger an account, in Django admin open **Users › add**, enter the name as listed, and in the **linked subject** field pick their subject by that name. Do this before they sign in. The link can only be made from the user side today, and only by an admin.

If accounts are created another way, make sure the user's first and last name match the subject name exactly and that the ER Track source provider's subject setting is "use existing": EarthRanger then links the subject on the ranger's first login by matching the name. A name that differs by a letter gets a new, empty subject instead.

## Plan again and delete

**Plan again** runs a fresh plan for a load that is planned, stopped, failed or done, for example after fixing the site, to see what is left. **Delete this load** removes smart-able's record of the load, its ledger, plan and log. It removes nothing from EarthRanger.

Only one load of a given conservation area into a given site can be active at a time. Starting another is refused until the first finishes or stops.
