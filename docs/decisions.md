# Design decisions

Choices that shaped smart-able, with what would reopen them. Newest first.

## 2026-10-06: Profiles are shown as a flow and on the map, not as a network

**Context.** SMART Profiles has native graph features: typed entity-to-entity
relationships (`i_entity_relationship`, `i_relationship_type`), a link-chart
style table (`i_diagram_*`), and patrol-to-record motivations
(`i_patrol_record_motivation`). The question was whether the browser should
draw entities and records as a network.

**What the data showed.** The only Profiles data available was from the
Philippine Lawin sites (Region 5, SMART 7.5.4). There, one Profile named
"Threat/Response Tracking" holds 674 entities that are individual threat
sightings, 173 records that are response actions, and 187 entity–record
links. Every native graph table is empty. The entity–record graph has 132
components, of which 121 are a single entity joined to a single record; the
largest, 37 nodes, is two coordination-meeting records that each tie 16 and
23 threats together. Attachments are never shared between nodes. What the
data does have is a workflow: 667 of 673 located entities sit on a patrol
waypoint, each carries a priority, a status, and a planned response from
small lists, and some have a record documenting the response.

**Options considered.**

1. A flow (Sankey) view: entity type → each list attribute the Profile's
   types share → the source of the latest record. Answers the manager's
   questions ("how many Level 0 threats have no action yet") and scales with
   entity count. **Built.** The stages are discovered from the data (LIST
   attributes defined by every entity type, with 2–12 values), so another
   Profile's lists work without code changes.
2. Ego graphs in the entity and record drawers, drawn with inline SVG: the
   opened item in the centre, its patrol, records, sibling entities, and any
   SMART relationships around it. Generalises to the designed use of Profiles
   (people and vehicles with relationships) but, on Lawin data, shows almost
   nothing for most items. **Deferred.**
3. A map layer: entities as squares on the existing map, coloured by type or
   by any shared list attribute, with the existing time filter on their
   creation date. Cheapest, since the map, markers, and drawers exist.
   **Built.** Positions come from a `POSITION` attribute (Lawin) or from
   `i_entity_location` (generic), so both styles of Profile draw.

**What would reopen option 2.** A backup whose Profiles data has rows in
`i_entity_relationship`, or records that routinely link several entities,
or a Profile that tracks persistent subjects rather than sightings. When one
arrives, `./smart-able extract` on it and the queries in this entry (entity–
record degree, component sizes, relationship counts) say whether an ego graph
would show anything. The record and entity drawers already have the data an
ego graph needs (`recs` on entities, `D.recEnts` for the reverse) and the
Back-button navigation it would use.

## 2026-10-06: Credentials are left out of the Parquet by default

SMART stores a bcrypt hash of each user's desktop password in
`employee.smartpassword` and SMART Connect logins in
`connect_account.connect_pass`. The Parquet is what gets shared with
analysts, so those columns are excluded unless `--keep-credentials` is
passed. The database copy and the CSV in `work/` are raw and keep them.
Reopen if a Load step needs to migrate logins, which the flag already allows.

## 2026-10-06: Conservation Area exports are read directly, typed from a schema snapshot

An export's table dumps carry column names but no types, so
`extract/smart_schema.tsv` (the 7.5.4 schema, from JDBC metadata) supplies
them, and `extract/check_schema.sh` warns about every table or column that
differs from the snapshot on any input. Reopen when an 8.x backup is
extracted: its warnings list the deltas, and the snapshot should then be
regenerated from it once the browser handles them.

## 2026-11-18: A bundle's tracks are one per line, read a patrol at a time

A load read the bundle's `tracks.json` whole, which takes about 4.5 times
the file in memory; an area with an 801 MiB file could not be planned in the
load job (GUNDI-5944). An import only ever needs the tracks of the patrol it
is on. So bundle version 2 writes the tracks one per line, a patrol's lines
together (`tracks.jsonl`), with each patrol's byte range and counts in
`tracks.index.json`, and er-smart-sync reads a patrol's lines when it
imports that patrol. Memory no longer grows with the area
(`docs/load-performance.md`).

One file per patrol was the simpler reader, but a large area would be tens
of thousands of small objects to upload, list and download. Parsing the one
`tracks.json` as a stream needed no new layout, but it cannot jump to a
patrol, so every worker and every retry would scan the file again.

er-smart-sync still reads version 1, with the memory it needed before, so a
dataset extracted earlier loads without being touched; re-extracting it
writes version 2. A track is now checked when its patrol is imported, so a
bad one fails that patrol and not the bundle. Reopen if `patrols.json`,
still read whole, becomes the next thing too big to hold.

## 2026-11-19: Conservation areas share event types by their configurable model's name

A country's SMART deployment is many conservation areas with one model per
region, all loaded into one site. Each area's copy of a configurable model
has its own uuid, and the uuid was part of every event type value and
choice list name, so two areas of one region each wrote 18 event types and
22 lists of the same content and no query spanned them: about 3,000 event
types for 168 areas (GUNDI-5946). Without a configurable model the areas did
share, but each load deactivated the options its own model lacked and moved
every event type into its own category.

A load with a configurable model now has a set name, the model's name
unless the operator changes it, and a key made from that name stands where
the uuid stood (`findings.set_key`). Areas with one name write one set.
Every push is additive (er-smart-sync's `additive`): nothing is
deactivated, an existing event type keeps its category, and new ones join
it.

Not a hash of the model's content: one edited option in one area would
start a new set, and the operator could not see why. Not one set for the
whole site: regions keep different species lists. Sets written under a
model's uuid before this change are left as they are, and a load that
finds one keeps using it, so events already imported stay valid; merging
them into a shared set is not done.

Reopen if two regions give different models the same name and the plan's
warning (`shared_set_changes`) proves too easy to miss.

## 2026-11-19: A load leaves the event types a site already has

After a first load an administrator changes the migrated event types on
the site, then loads more patrols or another conservation area. Every load
pushes the data model, and the push replaced the name and the whole schema
of an event type that differed from SMART, so a field added on the site was
gone after the next load, with nothing in the plan to say so (GUNDI-5949).

A load now has a choice for event types the site already has, and the
default is to leave them: the push runs in er-smart-sync's `create-only`
mode, which creates the event types and options the site lacks and writes
nothing to the rest, their active state included. The other choice updates
them from SMART, as every load did. In both, the plan lists each event type
that differs with the fields on each side, and warns: before an update,
that those event types are replaced; before a keep, when SMART has a field
the site's event type lacks. A load made before the choice existed runs as
an update, which is what its plan showed.

Not a merge of SMART's fields with the site's: the push cannot tell a field
added on the site from one removed in SMART, and guessing would either
bring back what SMART dropped or drop what the administrator added. Not a
load of patrols alone: a load that leaves existing event types does that
and still creates the ones that are missing. Patrol types and the
universal patrol fields are outside the choice.

Not established: whether a site accepts an event whose details carry a
field its event type lacks, which a keep load can import. It is checked by
hand on a test site before release; if the site refuses such events,
`event_types_missing_fields` becomes blocking.

Reopen if operators need SMART's new fields and the site's added fields in
one event type often enough that adding fields by hand does not do.

## 2026-11-20: One sidebar for the app and the data browser

Getting from a dataset back to the list was clumsy and different in each
place: a breadcrumb line on the dataset page, one "Back to dataset" link on
the browse pages. The two are separate documents with separate navigation,
so a dataset's data and its migration read as two applications.

A left sidebar replaces the app's top band, its breadcrumb line and the
dataset's tabs, and the browser's band and list of views. Outside a dataset
it lists Datasets and Sites. Inside one it shows only that dataset: a link
back to the datasets, its Overview, then two groups, Data (the browser's
eight views) and Migration (Loads, Match rangers, Backup). Theme, language,
help and the account sit at its foot. Sites became a page of its own, and
the browser's "Overview" is named Summary so the dataset has one Overview.

The browser stays its own self-contained document, because it also opens
from a local folder with no server. The sidebar's entries and markup are
one file, `web/static/nav.js`, with `nav.css`; the app loads them and the
browser carries a copy between markers, written by `scripts/sync_nav.py`
and compared byte for byte by a test. From a folder the browser shows the
Data group and the fold control and asks no server for anything. The
browser's pages stay in English; only its sidebar follows the reader's
language, and says so beside the Data heading. `quirks.html` keeps a plain
band with a link back: it is a reference page opened in its own tab.

Not the top band with Datasets and Sites links added and a breadcrumb in
the browser: small, but the tabs and the browser's views would stay two
separate things. Not a sidebar only inside a dataset: two styles of
navigation in one app. Not the browser's views nested under a "Browse"
entry: three levels deep, and "Rangers" twice. Not the browser moved into
the app: a much larger change that ends its use from a folder.

The app has a slim band again above the sidebar, with the EarthRanger
lockup, the app's name and its version. With the band gone the version was
only in the account menu, where nobody looked for it. The band holds
nothing to do: navigation, theme, language, help and the account stay in
the sidebar, whose own lockup and name are hidden. The browser carries the
same band, so the two read as one application: served by the app its
lockup leads back to the datasets and it names the app's version; from a
folder it shows the lockup and the name only.

Reopen if the copy in the browser drifts despite the test, or if the page
load between a Data view and a Migration page is felt in use; then the
browser moves into the app.

## 2026-11-20: A migrated patrol's track belongs to its leader only

SMART records one track for a patrol leg, not one for each person on it.
The import gives that track to the leg's leader, or to the first member
when the leg has no leader, and writes the leader, the members and the
team on the leg. EarthRanger's team patrol view computes each tracked
subject's distance from that subject's own track, so on a migrated leg
the leader has a distance and the other members have none (GUNDI-5947,
checked on a staging site: 6 of 8 sampled leaders had track points in the
leg's time range, and none of 29 other members).

Tracking the leader only is enough. The import does not copy the leg's
track to every member.

Not a copy for each member: it multiplies the track points by the size of
the team (about four times for LAWIN), slows every load, needs a backfill
of the areas already loaded, and shows as recorded movement what SMART
never recorded for that person.

A report that needs distance for each member takes it from the leg: its
leader's track, credited to the members the leg names. Which fields the
EcoScope effort report reads is not established (GUNDI-5962).

Reopen if a report or the web app can only credit a member from that
member's own track and neither can be changed.
