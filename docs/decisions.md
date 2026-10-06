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
