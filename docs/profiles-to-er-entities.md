# SMART Profiles → EarthRanger Entities

Notes from 2026-10-06 on whether the Profiles data in a SMART conservation
area can migrate into EarthRanger's upcoming Entities feature, checked
against the Lawin (Philippines, Region 5) backups. Parked for a later pass;
see [Follow-up questions](#follow-up-questions) and [Next steps](#next-steps).

## The discussion

**Question put to Joshua** (EarthRanger product, owns the Entities feature):
can SMART Profiles data, as seen in the Lawin sample, migrate into Entities?

**Joshua's reply** (Slack, quoted):

> profiles maps to "phase 2" of entities, whereby you can define and connect
> specific arbitrary relationships. "phase 1" (this quarter) of entities is
> inferred relationship semantics by way of an event field. profiles defines
> very specific conditions, triggers, and outcomes in a way that we're hoping
> to avoid entirely.
>
> ideally, good data semantics and setup and capture preclude the need for
> all the manual initiation and management of profiles.
>
> we're warming into proving that out by this first quarter's efforts.
>
> i hypothesize that a lot of the "profiles use cases" that take so much
> manual config will be the natural state/outcome of simple subject entities
> in ER.

**A separate analysis** (Claude, desktop) argued that Joshua answered a
roadmap question rather than the migration question, and that:

- A Profile is an entity record with a per-type attribute schema, instances
  with values, and links from observations through a profile-typed
  observation attribute; the "conditions, triggers, outcomes" framing
  describes configuration burden, not the data structure.
- Phase 1 covers a sighting pointing at a known individual, vehicle, or
  camp. It plausibly does not cover entity-to-entity relationships, per-type
  attribute schemas, attribute value history, or lifecycle state; any of
  those present in the data is lossy under phase 1 or waits for phase 2.
- "Good semantics preclude manual profile management" is a product bet,
  weaker for curated law-enforcement style records where an analyst, not
  the field collector, decides identity.
- Recommended: enumerate the constructs from the backup, stage the Profiles
  data in an intermediate schema now, and label anything phase-2-only as
  unsupported-pending in what goes to FMB.

## What the Lawin data actually contains

From the SMART 7.5.4 backup of two Region 5 conservation areas (050500,
050504; 674 entities) and the Camarines Norte export (051600; 396 entities).
The vocabulary is in [smart-data-model.md](smart-data-model.md#profiles-optional-plugin).

- One Profile per CA, menu label "Threat/Response Tracking". Sixteen entity
  types, all kinds of threat (Cutting of Trees, Charcoal Making, Landslide,
  …), every one with the same six attributes: Threat ID (text), Status
  (Addressed / No action yet / Invalid observation), Priority (Level 0
  immediately / 1 within a week / 2 within a month), Main response,
  Additional response (lists of response kinds), Point location. One type
  adds a hectares field.
- Entities are individual threat sightings, named by hand ("Cutting of
  Trees # 130"), created by three users. 667 of 673 located entities sit on
  a patrol waypoint and 559 were created within 30 days of it. Yet SMART
  stores no link from entity to observation: zero entity types are bound to
  a data-model attribute, zero entities to a list item, and the Threat ID
  matches nothing in the observation tables. The link exists only as copied
  coordinates.
- Records are response actions: 173 records across nine sources
  (Coordination with LGU, Garbage cleanup, Education, Administrative
  proceedings, Prosecution, …), with 57 per-source attributes defined and
  448 values filled, statuses PROCESSING / COMPLETE, 739 photos. 187
  entity–record links: 507 entities have no record, 149 have one, 18 have
  two or three; 141 records link one entity, 30 link several, two
  coordination-meeting records link 16 and 23.
- Status versus records: 559 Addressed (157 with a record), 92 No action
  yet (none), 23 Invalid observation.
- Empty in every Lawin backup: `i_entity_relationship`,
  `i_relationship_type`, `i_diagram_*`, `i_patrol_record_motivation`,
  `i_observation`, `i_working_set`. No attribute references an employee or
  an entity type.
- No attribute history exists in the schema; only `date_modified`. 582 of
  674 entities were modified after creation, so statuses did change, but
  nothing records what they were.
- Attachments: 1,542 on entities (545 entities have a primary photo), 739
  on records, never shared between two things.

## Assessment

**Where the desktop analysis misreads this data.** The observation-to-entity
link it assumes does not exist here; the dominant Profiles use case it
describes (sighting points at a known subject) is not what Lawin does.
There is no attribute history to lose. The "per-type custom schemas" are
one schema with a type column.

**Where Joshua is right for Lawin.** "Conditions, triggers, and outcomes"
fits uncannily: Priority is a trigger with a deadline, Main response a
planned outcome, Status the realised one. They are list attributes, not an
engine, but the configuration is a workflow. His hypothesis holds for most
of the data: 507 of 674 entities carry nothing beyond the observation plus
three triage fields, and every entity is a manual copy of an observation,
exactly the manual initiation he wants to make unnecessary. An ER event
with status and priority fields is the natural state of three quarters of
these entities.

**Where his framing is thin.** The other quarter accumulates: 167 entities
have response records, with their own attributes, statuses and photos.
That is a case file, and it is the threat follow-up gap already on the FMB
list, with a data model behind it.

**Construct by construct**

| Construct | In Lawin | Phase 1 fit |
| --- | --- | --- |
| Entity as threat sighting (type, point, date) | 674 | Safe: an event, or an entity, with status and priority as fields |
| Six shared entity attributes | all | Safe as fields |
| Entity photos | 1,542 files | Safe as attachments |
| Response records with per-source attributes | 173 records, 448 values | Safe as events of a response type |
| Record linked to one entity | 141 records | Safe via the phase-1 event field |
| Record linked to several entities | 30 records, up to 23 entities | Only if the event field is multi-valued; otherwise phase 2 |
| Entity → originating observation | not stored | Reconstructable by proximity and date, better than source |
| Entity-to-entity relationships | 0 rows | Not needed for Lawin |
| Attribute history, lifecycle | not kept | Nothing to migrate |

The one phase-2-dependent construct for this site is the many-to-many
record link. Everything else lands in phase 1 or needs no entity at all.

**The caveat that stands.** This is one site type. A Profiles deployment
tracking people or vehicles with relationships would be a phase-2
migration, and no such backup has been seen. [decisions.md](decisions.md)
says what dataset would settle it.

**Staging.** Already done in effect: `work/parquet/` holds every Profiles
table typed, and `site/data/profiles.json` holds entities with attribute
keys, positions and record links in the shape a loader would want.

## Follow-up questions

For Joshua:

1. Does the phase-1 event field accept several entities on one event? The
   coordination-meeting records (16 and 23 threats each) need that, or
   phase 2.
2. Can an event type carry the Lawin lifecycle, status and priority with
   deadlines, as event fields or states? If so, Lawin needs nothing from
   phase 2.
3. Is he describing the Profiles data model or the SMART UX around it? His
   "conditions, triggers, outcomes" matches Lawin's configuration, not the
   generic model; worth knowing which he has in mind before generalising.
4. Phase 2 timing, even roughly, for the FMB mapped / approximated /
   unsupported breakdown.

For us:

5. Does FMB want threats as ER events with triage fields (simplest, loses
   nothing Lawin keeps) or as entities that accumulate (closer to the
   SMART shape, needs phase 1 at least)?
6. Should the migration create the entity-to-observation link SMART never
   stored, from the 667 proximity matches? It is an inference and should be
   labelled as one.
7. Where does a response record go: an event update on the threat, or a
   linked event of its own type? The 57 record attributes and 739 photos
   argue for its own type.

## Next steps

- Send questions 1–4 to Joshua.
- When a non-Lawin Profiles backup arrives, re-run the enumeration above
  (entity types, link counts, relationship rows) before extending this.
- When an 8.1 backup arrives, `./smart-able extract` prints the schema
  deltas; check `i_*` changes against this note.
- Sort the construct table into the FMB breakdown: everything above the
  many-to-many row as mapped, that row as unsupported-pending.
