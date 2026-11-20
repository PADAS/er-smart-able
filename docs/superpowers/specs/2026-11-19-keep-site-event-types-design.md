# A later load keeps the event types the site has

Ticket: GUNDI-5949. Builds on GUNDI-5946 (several conservation areas on
one site, `2026-11-19-shared-event-type-sets-design.md`), which made every
push additive but still writes SMART's name and fields over an event type
that differs.

## Purpose

After the first load, an administrator works on the site: adds a field to
an event type, renames one, reorders or renames dropdown options. Then
more patrols or another conservation area are loaded. Today that load
pushes the data model again, and where an event type on the site differs
from SMART the push replaces its name and its whole schema. A field added
on the site is gone, and nothing in the plan says so.

## What was decided

- A load has a choice for event types the site already has: **leave them
  as they are** (the default) or **update them from SMART** (what every
  load does today).
- Either way the load creates the event types, dropdown options and event
  categories the site lacks.
- The plan names every event type on the site that differs from SMART,
  and says what the load will do about it.
- No merge of the two (SMART's fields plus the site's). The push cannot
  tell a field added on the site from a field removed in SMART.
- No load of patrols alone. A load that leaves existing event types alone
  does that job and still creates what is missing.

## The option

`options.existing_event_types` on `POST /api/datasets/{id}/loads`:

| Value | Meaning |
| --- | --- |
| `keep` | The default when the option is absent or null |
| `update` | Today's behaviour |

Anything else is `400 existing_event_types_invalid`. The value is stored
with the load's options and shown on the load page.

A load document made before this change has no value. It runs as
`update`: that is what its plan showed.

The load form has a select, "Event types already on the site", with
"Leave them as they are" chosen. It is shown for every load, with or
without a configurable model.

## What "leave them as they are" means

For everything in the load's event type set that the site already has,
the load makes no write:

| On the site | The load |
| --- | --- |
| An event type with this value | Not written: name, fields, active state and category stay. An event type an administrator turned off stays off |
| An option of a dropdown list | Not written: display text, order and active state stay |
| An event category | Not written |
| No event type with this value | Created from SMART, in the category the set is in (the rule of GUNDI-5946) |
| A list without this option | The option is created |

"Update them from SMART" is the push of GUNDI-5946, unchanged: additive,
and SMART's name and fields replace the site's where they differ.

The patrol side of a load (patrol types, the universal patrol fields,
ranger subjects, teams) is not part of this choice and behaves as today.

## What the plan says

The library reports, for each event type the site has that differs from
this load's model, what differs:

| Key | Meaning |
| --- | --- |
| `value`, `display` | The event type; `display` is the site's name |
| `name` | True when the names differ |
| `active` | True when the active states differ |
| `site_only` | Field keys the site's schema has and SMART's lacks |
| `smart_only` | Field keys SMART's schema has and the site's lacks |
| `changed` | Field keys both have, with different definitions |
| `other` | True when the schemas differ outside their fields (layout, read-only flag) |

Field keys are the keys of the schema's `json.properties`.

The plan carries the list under `event_types.differ` (capped like the
plan's other lists) and the load's choice under `existing_event_types`.
The plan page shows the list under the event types: each event type with
what differs, headed "left as they are" or "updated from SMART".

Two warnings, neither of which stops a load:

| Code | When | Says |
| --- | --- | --- |
| `event_types_overwritten` | `update`, and at least one event type differs | The event types that get SMART's name and fields, and how many of them lose fields the site has and SMART lacks. Fix: plan again with "Leave them as they are" |
| `event_types_missing_fields` | `keep`, and at least one event type has `smart_only` fields | The event types whose form on the site has no field for something this area records. Fix: add the fields on the site, or plan again with "Update them from SMART" |

`shared_set_changes` (GUNDI-5946) named the event types a load would
change and counted the options it would add. The event types now belong
to `event_types_overwritten`, so `shared_set_changes` reports only
options added to a set the site already has, and its text changes to
say that.

## Where the work is

| Repository | What changes |
| --- | --- |
| `PADAS/earthranger-smart-utils` | `upsert_choices` takes `create_only: bool = False`: an existing option gets no write and is counted in `skipped_by_mode`; orphans are not deactivated. The synchronizer passes it when `sync_mode` is `create-only`, and adds `choices_skipped_by_mode` to its stats. The synchronizer records the differences above for version 2 event types, in both modes, and the stats carry them as `event_type_differences`. No new argument on `push_datamodel_files`: `mode="create-only"` is already there. Changelog: `--mode create-only` now leaves existing options alone too. A release. |
| `PADAS/er-smart-able` | The option (API, load form, load page). The load job passes `mode="create-only"` for `keep`, takes the differences out of the stats before they are logged or stored with the stage, and puts them in the plan. The two warnings and the narrower `shared_set_changes`. Interface text in five languages. Help: the loads page gets "Changes made on the site"; the stops page gets the two warnings. `docs/decisions.md`. The load image's pin of the library. |

The library is released first; the app then pins it.

`create-only` already leaves legacy version 1 event types unconverted. A
`keep` load into a site that still has version 1 SMART event types skips
the colliding values, as the library does today for that mode.

## Not in this work

- Merging SMART's fields with the site's.
- Telling which side made a difference. The plan says the two differ, not
  who changed what.
- Keeping site edits to patrol types or the universal patrol fields.
- A choice per event type.

## Not known

Whether EarthRanger accepts an event whose details carry a key its event
type's schema lacks, and how the web form shows it. A `keep` load can
import such events (the `event_types_missing_fields` case). The import
itself does not change. The check by hand below settles it; if the site
refuses such events, `event_types_missing_fields` becomes blocking, which
is a one-line change and a text change.

## Tests

Library, against the fake site:

- A `create-only` push into a site that has an option with another
  display text, order and active state writes nothing to it, creates a
  missing option, and deactivates no orphan.
- A `create-only` push leaves an existing event type's name, schema and
  active state, and creates a missing one.
- A push in the default mode behaves as before (the existing tests).
- The differences: a site event type with one field added and one removed
  gives `site_only` and `smart_only` with those keys; a renamed one gives
  `name`; an equal one gives no entry; the list is the same in both
  modes.

App:

- The option: absent gives `keep`; `update` is stored; another value is
  refused; an old load document reads as `update`.
- A load with `keep` into a fake site where an event type has a field
  added: after the run the field is there, and a missing event type and a
  missing option were created. The same load with `update` removes the
  field. This is the ticket's test and fails on today's code.
- The plan of each lists the event type under `event_types.differ` with
  the added field in `site_only`; `update` carries
  `event_types_overwritten`, `keep` does not.
- A `keep` plan where SMART has a field the site lacks carries
  `event_types_missing_fields`.
- `shared_set_changes` fires for options added to a set on the site and
  no longer for event type updates.
- The stage's stored stats and the log do not contain the differences
  list.

By hand, before release, on a test site of the user's choosing: add a
field to a migrated event type, load with "Leave them as they are", and
confirm the field is still there; then import one event whose details
carry a key the site's event type lacks and record what the site does.

## Acceptance (from the ticket)

- A load can import patrols and leave existing event types unchanged.
- A field added to an event type on the site is still there after that
  load.
- The plan names each event type whose site changes a data model push
  removes.
- The help page for loads says how to keep changes made on the site.
