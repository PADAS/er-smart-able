# SMART data quirks

What to know when reading data out of a SMART conservation area backup or
export. Each section is linked from the place in smart-able where it
matters, and from the warnings `./smart-able export` prints. Verified on
SMART 7.5.4–7.5.6 data (the Lawin backups and the Camarines Norte export)
unless a section says otherwise. `./smart-able browse` publishes this page
as `quirks.html` next to the browser.

## Timezones

SMART stores every date and time as a local wall-clock value with no zone:
`waypoint.datetime`, `patrol_leg_day.start_time` and `end_time`, patrol and
leg dates, and the Profiles creation times (SMART 7; SMART 8 stores those in
UTC). Nothing in the database says which zone the clock was in.

smart-able infers a zone per conservation area from the median waypoint
position (`browse/infer_timezones.py`, written to `timezones.json`) and
uses it in the browser and in the migration bundle. Set
`SMART_ABLE_TIMEZONE=<IANA name>` before `./smart-able export` to override
the inference; the bundle manifest records which zone was used and whether
it was configured or inferred. Every timestamp in the bundle carries its
UTC offset, so er-smart-sync never has to guess.

Track points are the one place SMART stores a timestamp (see Tracks), and
they are local wall-clock too, so they cannot validate the zone. A site
that patrols across two zones gets one zone for everything.

## Patrol times

A SMART patrol has no timestamps of its own: `patrol` and `patrol_leg`
carry dates only. Times come from three places, in this order of precision:

1. The leg day's track, whose points carry a per-point timestamp (see
   Tracks). Lawin: 2,648 of 3,597 leg days have a track.
2. `patrol_leg_day.start_time` and `end_time`, local wall-clock, present on
   most leg days. An end time earlier than the start time means the day
   crossed midnight; the bundle advances the end by one day.
3. The times of the waypoints recorded on that leg day
   (`waypoint.datetime`, local), which bound the day's activity even when
   nothing else was recorded.

EarthRanger needs a start and an end on every patrol segment, so the
importer sets each segment's range from the earliest and latest of those
sources per leg day, falls back to the whole calendar day when none exists,
and records which source it used in the segment's provenance. The bundle
manifest's `time_coverage` block counts leg days by their best source, and
the export summary prints the same numbers, so you know before importing
how precise the result will be. Track points become ER location
observations on the leader with their real times; waypoints become events
at their own times.

Two things to watch. First, the leg-day start time and the track's first
point should agree to the hour, since both are local wall-clock; on Lawin
they do on 1,296 of 1,573 leg days, and the rest (early 2017 data) are
eight hours apart, which looks like an older SMART Mobile writing the
leg-day time in a different frame. The export warns when the majority
disagree, which would mean a different SMART version stores tracks in true
UTC. Second, SMART stores an unset leg start date as 1970-01-01 and then
generates a leg-day row for every day up to the end date: the Camarines
Norte export has 13 such legs carrying 93,697 leg days, each with made-up
start and end times. The bundle keeps those rows as stored, marks the leg
`placeholder_dates: true`, and warns; the importer clamps such legs to the
days that have a track or a waypoint.

## Tracks

`track.geometry` is one line per leg day, stored as extended WKB in hex:
`0x80000002` (LineString with Z) or `0x80000005` (MultiLineString with Z,
one part per recording session). `track.distance` is in kilometres.

The Z coordinate of every point is a timestamp: the local wall-clock time
encoded as Unix epoch milliseconds as if the local clock were UTC. Decoded
that way, track starts cluster between 05:00 and 10:00 and match the
leg-day start times; decoded as true UTC they would put Philippine patrols
in the afternoon. smart-able decodes Z as a naive time and anchors it to
the bundle timezone like every other SMART time. There is no per-point
speed, accuracy or source.

GPX imports and InReach feeds land in the same table and are
indistinguishable from SMART Mobile tracks; there is no source column on
`track`, and the waypoints they create carry `source = PATROL` like any
other. Some GPX tools put elevation in Z instead of a time; the export
detects Z values that cannot be timestamps, writes that track without
times, and warns.

## Waypoints and legs

`patrol_waypoint(wp_uuid, leg_day_uuid)` ties each waypoint to exactly one
leg day, which gives it its leg and patrol; a waypoint whose leg day is
missing is left out of the bundle and reported. Legs carry dates only
(`patrol_leg.start_date`, `end_date`), leg days carry the date plus start
and end times and `rest_minutes`.

`waypoint.x` is longitude and `y` latitude in WGS 84, with a missing GPS
fix stored as `0,0` rather than NULL; the browser and the exporter treat a
position within 0.01 degrees of `0,0` as missing. `waypoint.source` says
which tool recorded it: `PATROL`, `INDINC` (independent incident),
`SMARTCOLLECT`, `ASSET`, `SURVEY`; smart-able handles `PATROL` waypoints.
`last_modified_by` is the employee who last edited the record, not
necessarily the observer; the observer, when recorded, is
`wp_observation.employee_uuid`.

## Labels and languages

Every display name lives in `i18n_label(language_uuid, element_uuid,
value)`, keyed by the UUID of the row it names: categories, attributes,
list values, tree nodes, configurable models and their nodes, transports,
mandates, stations (through `station.desc_uuid`), ranks and teams. The
tables themselves hold only keys.

A conservation area can declare languages that have almost no labels:
Lawin's Guinobatan CA has `en` with 2,707 labels and `en_PH` with 7. When
a label is missing in the requested language, smart-able falls back to the
CA's default language, then to any language that has one. The bundle
carries every language's labels; the Data Model tab's language picker
shows each language's code and how many labels it lacks, and that code is
the value to give `er-smart-sync --smart-language` when populating
EarthRanger.

## Observation values

An observation (`wp_observation`) points at a category and holds one row
per attribute value in `wp_observation_attributes`. Which column holds the
value depends on `dm_attribute.att_type`:

| Type | Where the value is |
| --- | --- |
| LIST | `list_element_uuid` (a `dm_attribute_list` row; the bundle writes its `keyid` and label) |
| MLIST | one or more rows in `wp_observation_attributes_list` (the bundle writes an array of keys and labels) |
| TREE | `tree_node_uuid` (a `dm_attribute_tree` row; the bundle writes its `hkey` without the trailing dot) |
| NUMERIC | `number_value` |
| BOOLEAN | `number_value`, 1.0 or 0.0 |
| TEXT | `string_value` |
| DATE | not seen in real data yet; the bundle reads `string_value`, then `number_value` as epoch milliseconds |

Attribute types in `dm_attribute.att_type` are padded `CHAR` values in a
Conservation Area export (`'LIST    '`); smart-able trims them.

## Data model export

`./smart-able export` rebuilds SMART's DataModel XML from `dm_category`,
`dm_attribute`, `dm_attribute_list`, `dm_attribute_tree`, `dm_cat_att_map`,
`dm_att_agg_map`, `i18n_label` and the icon tables. Compared with SMART
Desktop's own export of the Camarines Norte CA (2026-10-12) the output is
byte-identical except the icon file names.

Rules learned from that comparison: attributes are ordered by their
default-language label, not by key; inside an attribute the order is
aggregations, then `qa_minmax` or `qa_regex`, then names, then list
values or tree nodes; categories follow `cat_order` within their parent;
numbers print the way Java prints doubles (`0.0`, `1.0E7`); the namespace
is `xml/1.1/datamodel` for SMART 7.5. Only icons referenced by the CA's
elements appear, with one file per icon set.

Icon file names are the exporting install's `iconfile` row UUIDs
(`<uuid>.svg`), and system icons have a separate row per conservation area
per install, so the same icon is named differently in an export made on
another SMART installation. smart-able's names match an export made on the
install the backup came from; `verify_xml --ignore-icon-files` sets the
difference aside. System icon files are stored in the database as
`platform:/plugin/...` paths and are not in the backup; custom icons are.

## Configurable models

A configurable model (`configurable_model`) is a curated overlay of the
data model for a mobile form: `cm_node` rows form the tree (a node with a
`category_uuid` is a category, one without is a group with its own label),
`cm_attribute` lists the attributes each node shows, and
`cm_attribute_config` holds the curated option lists (`cm_attribute_list`,
`cm_attribute_tree_node`) that several nodes can share through
`cm_attribute.config_uuid`. Per-attribute display options live in
`cm_attribute_option` (`IS_VISIBLE`, `MULTISELECT`, `NUMERIC`,
`FLATTEN_TREE`, ...). A conservation area can have several models; Lawin's
CAs have one each.

smart-able writes SMART's ConfigurableModel XML (`xml/1.0/dataentry`)
following the one sample export we hold (Botswana Guardians). Two things in
that format have no known source column and are written with defaults, with
a warning: the root's `useEarthRanger` attribute (`false`) and the
CyberTracker profile options behind `extraData` (only the profile name and
the `connect_ct_properties` keys are written). The output has not yet been
compared with an export of the same CA; the Data Model tab shows which
options each model keeps, which is what the EarthRanger sync uses.

## Patrol metadata

`patrol.patrol_type` is the coarse class, `GROUND`, `AIR`, `MARINE` or
`MIXED`, from `patrol_type`. The transport (foot, vehicle, boat, ...) is
per leg (`patrol_leg.transport_uuid` into `patrol_transport`), as is the
mandate (`patrol_leg.mandate_uuid`); station and team are per patrol.
Transports can share a label: Lawin's Albay CA has "Others" twice, once
`GROUND` and once `MARINE`, distinguished only by key (`others`,
`others1`). Mandates and stations are optional and often NULL. Custom patrol
attributes (`patrol_attribute`, `patrol_attribute_value`) exist in the
schema but are empty in every dataset seen so far. Teams
(`employee_team`) can be empty while every leg still lists its members
(`patrol_leg_members`, with `is_leader` and `is_pilot`), so the members are
the reliable roster.

## Staff and credentials

`employee` holds each staff member's SMART login name and password hash
(`smartuserid`, `smartpassword`), birth date and gender alongside the
name, agency, rank and employment dates. `connect_account` holds SMART
Connect logins. `./smart-able extract` drops `employee.smartpassword` and
`connect_account.connect_pass` from the Parquet unless `--keep-credentials`
is given, and the migration bundle never includes the login name, birth
date or gender. An employee's `active` flag in the bundle is derived from
`endemploymentdate` being empty or in the future.

## Attachments

Waypoint photos (`wp_attachments`) and Profiles attachments are files in
the filestore, encrypted per conservation area with AES-128-CBC using the
CA's UUID as the key; the database holds only file names. Backups and
exports can lack files the database refers to (Lawin: 265 of 585 for one
CA), so both the browser and the export warn and carry on. Export zips lay
the filestore out without the `<ca_uuid>/` level that backups have.

## Backups versus exports

A SMART system backup zip holds the whole install: a Derby database with
every conservation area, the filestore, and SMART's own configuration.
Multi-CA backups also include the all-zero "Cross Conservation Area
Analysis" placeholder row and often SMART's demo "Example Conservation
Area" (in Gabon); `export` skips the placeholder. A Conservation Area
export zip holds one CA as `.def`/`.dat` files (one pair per table, no
column types, binary as hex) plus the filestore and `conservationarea.dat`;
install-wide tables (`connect_*`, `login_log`) are absent, which is normal.
smart-able's schema snapshot is SMART 7.5.4; `check_schema.sh` warns about
tables and columns that differ (the Camarines Norte export, for instance,
adds six `paws_*` tables). See RUNBOOK.md for the warning texts.

## Profiles

Profiles (the `i2` plugin, tables `i_*`) are configured trackers of
persistent entities with dated records. The Lawin sites use them in an
unusual way, to track individual threat sightings as entities with
responses as records. See [docs/profiles-to-er-entities.md](profiles-to-er-entities.md)
and the browser's Profiles tab help for what that means for an EarthRanger
migration.
