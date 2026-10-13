# Data model export and migration bundle

Date: 2026-10-12. Status: draft for review.
Related: TASK2.md items 1 and 2; Jira epic ERA-14136 (SMART → ER patrol
migration) and spike ERA-14142; companion spec in earthranger-smart-utils,
`docs/superpowers/specs/2026-10-12-smart-patrol-migration-design.md`.

## Goal

Make a SMART backup or Conservation Area export zip sufficient, on its own,
to move a site to EarthRanger. smart-able already turns the zip into Parquet
and a browser. This adds two outputs per conservation area:

1. **Data model export.** The CA's DataModel and each ConfigurableModel as
   XML that matches what SMART Desktop itself exports, so
   `er-smart-sync datamodel --from-file` and SMART's own tooling accept it
   unchanged. A Data Model tab in the browser shows the same content.
2. **Migration bundle.** Patrol history and reference data as plainly named
   JSON files with a published JSON Schema. er-smart-sync reads the bundle
   instead of SMART Connect for patrol configuration and patrol import.

Decisions already taken (2026-10-12):

- Sites will supply a backup or export zip. SMART Connect is never required.
- The bundle is JSON, not Parquet, so er-smart-sync needs no DuckDB or Arrow
  dependency.
- The XML emitter aims for byte-level fidelity with SMART's export, verified
  against a reference export the user produces from SMART Desktop for a CA we
  hold as a backup.

## Non-goals

- Profiles and Entities (the `i_*` tables). Separate track, see
  `docs/profiles-to-er-entities.md`.
- Serving the new outputs from the Cloud Run web app. Follow-up: a download
  link per dataset once the files exist in the site directory.
- Patrol plans, missions, surveys, assets, and queries. Nothing in the epic
  needs them.
- Writing anything to EarthRanger. That is er-smart-sync's job.

## Inputs

Parquet tables in `work/parquet/`, produced by `smart-able extract` from a
backup or export. Backups may hold several CAs; everything below is per CA
and keyed by the CA's `uuid`.

| Output | Tables |
| --- | --- |
| DataModel XML | `dm_category`, `dm_attribute`, `dm_attribute_list`, `dm_attribute_tree`, `dm_cat_att_map`, `dm_aggregation`, `dm_att_agg_map`, `i18n_label`, `language`, `icon`, `iconfile`, `iconset` |
| ConfigurableModel XML | `configurable_model`, `cm_node`, `cm_attribute`, `cm_attribute_config`, `cm_attribute_list`, `cm_attribute_tree_node`, `cm_attribute_option`, `cm_ct_properties_profile`, `ct_properties_profile`, `connect_ct_properties`, plus the DataModel tables for keys and labels |
| Bundle | `patrol`, `patrol_leg`, `patrol_leg_day`, `patrol_leg_members`, `patrol_type`, `patrol_transport`, `patrol_mandate`, `patrol_attribute`, `patrol_attribute_list`, `patrol_attribute_value`, `station`, `employee`, `employee_team`, `employee_team_member`, `rank`, `agency`, `track`, `waypoint`, `wp_observation_group`, `wp_observation`, `wp_observation_attributes`, `wp_observation_attributes_list`, `wp_attachments`, `conservation_area`, `db_version`, `i18n_label`, `language` |

Labels: `i18n_label(element_uuid, language_uuid, value)` holds every
human-readable name for categories, attributes, list values, tree nodes,
configurable models, nodes, attribute configs, mandates, transports, and
stations (via `station.desc_uuid`). Verified on the Lawin backup: every
`dm_*` row has a label; `cm_attribute`, `cm_attribute_list`,
`cm_attribute_tree_node` and `cm_attribute_option` have none and take their
names from the DataModel element they reference.

## Command and layout

```
./smart-able export [ca_id ...]     work/parquet -> work/export/<ca_id>/
./smart-able all <backup>           extract + browse + export
```

`<ca_id>` is `conservation_area.id` (for Lawin: `050500`, `050504`, `SMART`).
With no argument every CA is exported except the all-zero
"Cross Conservation Area Analysis" row. Layout per CA:

```
work/export/<ca_id>/
  datamodel.xml
  configurable_model_<cm_uuid>.xml        one per configurable model
  datamodel.json                          browser view of the above
  bundle/
    manifest.json
    reference.json
    patrols.json
    tracks.json
    attachments/<waypoint_uuid>/<filename>
```

The browser's `work/site/data/` gets a copy of each `datamodel.json` so the
Data Model tab works when the site is served on its own.

Code lives in a new top-level `export/` directory, Python run through uv,
matching `browse/infer_timezones.py`:

| File | Role |
| --- | --- |
| `export/smartdb.py` | Opens the Parquet directory with the DuckDB Python package; label lookup by element UUID and language; UUID normalisation; CA listing. No output formatting. |
| `export/datamodel_xml.py` | Builds the DataModel and ConfigurableModel XML documents. Pure functions from query results to text. |
| `export/datamodel_json.py` | The browser-facing JSON for the Data Model tab. |
| `export/bundle.py` | Writes `manifest.json`, `reference.json`, `patrols.json`, `tracks.json`, copies attachments. |
| `export/bundle.schema.json` | JSON Schema (draft 2020-12) for the four bundle files. The contract er-smart-sync vendors. |
| `export/verify_xml.py` | Compares our XML against a reference export and prints the first differences. Used in development and as a release check. |
| `export/__main__.py` | CLI entry: `uv run python -m export [--work DIR] [ca_id ...]`. |

`pyproject.toml` gains `duckdb>=1.1` as a core dependency. The launcher's
`export` function calls the module; `all` runs extract, browse, export.

## DataModel XML

Root `<DataModel xmlns="http://www.smartconservationsoftware.org/xml/1.1/datamodel">`.
The namespace version comes from a table in the emitter keyed on the SMART
version in `db_version`; 7.5.x maps to `1.1`. Anything else emits a warning
and uses `1.1`.

Sections in order: `languages`, `attributes`, `categories`, `icons`.

**languages.** One `<languages code="…"/>` per `language` row of the CA,
default first. (SMART's DataModel export repeats the element name
`languages` for both the container and each entry.)

**attributes.** One `<attribute>` per `dm_attribute` row, ordered by `keyid`.
Attributes: `key`, `isrequired`, `type` (`att_type`), and `iconkey` when
`icon_uuid` is set (`icon.keyid`). Children, in this order, each only when
present:

1. `<aggregations aggregation="…"/>` from `dm_att_agg_map`, ordered by name.
2. `<qa_minmax>` with `<MinValue>` and `<MaxValue>` for NUMERIC when
   `min_value` or `max_value` is set; `<qa_regex>` for TEXT, empty when the
   regex is blank. Numbers print as Java `Double.toString` (`0.0`, `1.0E7`).
3. `<names language_code="…" value="…"/>` per language that has a label.
4. LIST and MLIST: `<values key isactive>` from `dm_attribute_list` ordered by
   `list_order`, each with its `names`.
   TREE: `<tree key isactive [iconkey]>` for roots and nested `<children>`
   from `dm_attribute_tree` ordered by `node_order` under each parent, each
   with its `names`.

**categories.** One `<category key ismultiple isactive [iconkey]>` per root
`dm_category` ordered by `cat_order`, children nested as `<category>` in the
same way. Under each: `names`, then `<attributes isactive attributekey/>` per
`dm_cat_att_map` row ordered by `att_order`, then child categories.

**icons.** One `<icons key issystem>` per `icon` referenced by any category,
attribute, list value, or tree node, with one `<icons iconset file/>` per
`iconfile` row and the icon's `names`. `issystem` is true when the stored
filename starts with `platform:/plugin/`. SMART's export names icon files
`<iconfile.uuid>.svg` (verified on the reference export). Custom icon files
are not copied next to the XML yet; the exporter warns when a CA uses them
(no dataset seen so far does), and copying is a follow-up once one appears.

Formatting: XML declaration with `standalone="yes"`, four-space indentation,
attributes in the order listed above, empty elements self-closed, and the
`&lt; &gt; &amp; &quot;` escapes Java's JAXB uses. The emitter writes text
directly rather than through `xml.etree`, so attribute order and whitespace
are under our control.

## ConfigurableModel XML

Root `<ConfigurableModel xmlns="http://www.smartconservationsoftware.org/xml/1.0/dataentry" displayMode instantGps photoFirst useEarthRanger iconSet>`
from `configurable_model` and `iconset.keyid`. The source of `useEarthRanger`
is not in the 7.5.4 schema snapshot; the emitter writes `false` and warns
until the reference export shows otherwise.

Children in order:

1. `<languages>` with `<language code is_default/>` per CA language.
2. `<name language_code value source="CM"/>` per label on the model's UUID.
3. `<nodes>`: one `<node>` per root `cm_node` ordered by `node_order`,
   children nested as `<node>`. A node with `category_uuid` set carries
   `categoryKey`, `categoryHkey` (the category's `hkey`), `dmUuid` (category
   UUID, 32 hex), `photoAllowed`, `photoRequired`, `displayMode`, `id`
   (node UUID, hyphenated), `collectMultipleObs`, `useSingleGpsPoint`, and
   `imageFile`/`isCustomImage` when `imagetype` is set. A node without a
   category is a group and carries only `id`, order and image attributes.
   Names: the node's own label when one exists (groups), else the category's
   label with `source="DM"`.
   Under a category node, one `<attribute attributeKey dmUuid id configId type required [imageFile isCustomImage]>`
   per `cm_attribute` ordered by `attribute_order`, with the attribute's
   DataModel name (`source="DM"`) and one `<option id [doubleValue|stringValue]/>`
   per `cm_attribute_option` row. `required` comes from `dm_attribute`.
4. One `<attributeConfig id attributeKey displayMode isDefault attributeUuid>`
   per `cm_attribute_config`, with its own label (`source="CM"`) and either
   `<listItem keyRef dmUuid isActive id isCustomImage>` rows from
   `cm_attribute_list` ordered by `list_order`, or `<treeNode keyRef hkeyRef dmUuid isActive id isCustomImage>`
   with nested `<children>` from `cm_attribute_tree_node`. Each carries the
   DataModel name of the value it references.
5. `<extraData type="connect_ct_properties">` and `<extraData type="ct_profile">`
   from the profile linked through `cm_ct_properties_profile`, when any.
   The key set (`ping_alert_type`, `ping_frequency`, `data_frequence`, the
   profile name) is taken from the Botswana sample and confirmed against the
   reference export.

UUID forms follow SMART: `dmUuid`, `attributeUuid` and the like are the 32
hex characters as stored; `id` attributes are hyphenated.

## Fidelity verification

`export/verify_xml.py reference.xml ours.xml` parses both, walks the trees in
document order, and reports the first twenty differences in element name,
attribute set, attribute order, attribute value, text, or child order. It
exits non-zero on any difference. A second mode, `--loose`, ignores attribute
order and whitespace and reports only semantic differences, so progress is
visible while the strict diff still fails.

Acceptance, in increasing strength:

1. **Loads.** smartconnect-client's `DataModel.load` and
   `ConfigurableDataModel.load` accept the output and report the same
   category paths, attribute keys and option keys as they do for the
   reference file.
2. **Syncs.** `er-smart-sync --dry-run datamodel --from-file datamodel.xml --cm-from-file configurable_model_<uuid>.xml --ca-identifier <id>`
   runs clean and plans the same event types as the reference file.
3. **Matches.** `verify_xml.py` strict mode passes against the reference
   export of the same CA.

Levels 1 and 2 gate the merge. Level 3 is the target; any residual
differences are listed in RUNBOOK.md with their cause.

Reference data: the user exports the DataModel and configurable models from
SMART Desktop for a CA in the Lawin backup (Albay or Guinobatan both have
one configurable model). The Camarines Norte export zip is a different CA
and cannot serve as the reference for the backup, but once the user exports
its XML too it becomes a second fixture that exercises the export-zip input.

## Browser: Data Model tab

A new top-level view beside Observations, Patrols, Profiles and Map. Data
source is `datamodel.json`, one per CA, merged by the CA picker the browser
already has:

```json
{ "ca": "…uuid…", "default_language": "en",
  "languages": [{ "code": "en", "default": true, "labels": 6375, "missing": 0 },
                { "code": "en_PH", "default": false, "labels": 7, "missing": 6368 }],
  "categories": [{ "key", "hkey", "labels": { "en": "…", "en_PH": "…" }, "label", "multiple", "active", "icon",
                   "attributes": [{ "key", "active", "order" }], "children": [...] }],
  "attributes": { "<key>": { "labels", "label", "type", "required", "icon", "min", "max", "regex",
                             "options": [{ "key", "labels", "label", "active", "children": [...] }] } },
  "configurable_models": [{ "uuid", "label", "file": "configurable_model_<uuid>.xml",
                            "nodes": [{ "label", "category", "children", "attributes": [{ "key", "config", "options" }] }] }],
  "files": { "datamodel": "datamodel.xml" } }
```

Layout: category tree on the left (search box, inactive items greyed), the
selected category's attributes on the right with type, required flag and
option list; a configurable-model picker above the tree that swaps the tree
for the model's node tree and marks which options the model keeps. A
language picker beside it lists the CA's languages with the default
preselected and, for each, how many labels it is missing; every label in
the tab switches with it. This is where a user decides which language
er-smart-sync should populate EarthRanger with (its `--smart-language`
flag), so the picker shows the exact code to pass. Download
links for each XML file at the top. Counts in the tab header
(categories, attributes, models). Same single-file, no-build approach as the
rest of `browse/index.html`; the help drawer gets a page explaining data
model versus configurable model.

## Migration bundle

All four files are UTF-8 JSON, objects at the top level, keys in
`snake_case`, SMART UUIDs in hyphenated canonical form, timestamps in
RFC 3339 with a UTC offset, coordinates as WGS 84 `[longitude, latitude]`.
Labels are objects keyed by language code, with a `label` convenience field
in the CA's default language. The bundle always carries every language the
CA defines; choosing the language that populates EarthRanger is the
importer's job (er-smart-sync `--smart-language`), not the exporter's.

**manifest.json**

```json
{ "bundle_schema_version": 1,
  "generated_at": "2026-10-12T18:04:00Z",
  "generator": { "name": "smart-able", "version": "<git describe>" },
  "source": { "kind": "backup" | "export", "file": "<zip name>", "smart_version": "7.5.6" },
  "conservation_area": { "uuid", "id", "name", "designation", "country", "organization", "owner" },
  "timezone": { "name": "Asia/Manila", "source": "inferred" | "configured" },
  "default_language": "en",
  "languages": [{ "code": "en", "default": true, "labels": 6375, "missing": 0 },
                { "code": "en_PH", "default": false, "labels": 7, "missing": 6368 }],
  "counts": { "patrols": 1527, "legs": …, "leg_days": …, "waypoints": …, "observations": …, "track_points": …, "employees": …, "attachments": … },
  "time_coverage": { "leg_days": 3597, "track": 2648, "leg_day_times": 900, "waypoints": 40, "date_only": 9 },
  "warnings": ["…"] }
```

SMART stores patrol dates and waypoint times as local, zone-less values.
The timezone comes from `browse/infer_timezones.py` (already derived from
waypoint positions), overridable with `SMART_ABLE_TIMEZONE=<IANA name>`.
Every timestamp in the bundle is written with that zone's offset. The
manifest says which it was and where it came from so the importer can show
it in the preflight report. `languages` lists each language with its label
count and how many labelled elements lack a value in it, so the importer can
validate a requested language and warn about its coverage without scanning
the files.

`time_coverage` counts leg days by the best time source they have: a timed
track, else `start_time`/`end_time`, else a timed waypoint on the day, else
the date alone. SMART patrols and legs carry no timestamps themselves; the
importer derives each ER segment's time range with that same precedence
(see the er-smart-sync spec, "Patrol times"), so this block tells the user
before an import how precise the result will be. A warning is written when
any leg day is date-only.

**reference.json**

```json
{ "patrol_types":     [{ "key": "GROUND", "active": true, "max_speed": … }],
  "transports":       [{ "uuid", "key", "labels", "label", "patrol_type": "GROUND", "active" }],
  "mandates":         [{ "uuid", "key", "labels", "label", "active" }],
  "stations":         [{ "uuid", "labels", "label", "active" }],
  "patrol_attributes":[{ "uuid", "key", "type", "active", "options": [{ "uuid", "key", "labels", "label", "active" }] }],
  "agencies":         [{ "uuid", "key" }],
  "ranks":            [{ "uuid", "agency_uuid", "labels", "label" }],
  "teams":            [{ "uuid", "labels", "label", "member_uuids": [] }],
  "employees":        [{ "uuid", "id", "given_name", "family_name", "agency_uuid", "rank_uuid",
                         "employment_start": "2017-01-01", "employment_end": null, "active": true }] }
```

Employees carry what ER needs to create a ranger subject and nothing else:
no SMART login, password hash, birth date or gender. `active` is derived
from `employment_end` being null or in the future.

**patrols.json**

```json
{ "patrols": [
  { "uuid", "id": "LAW-2019-0001", "patrol_type": "GROUND",
    "station_uuid", "team_uuid", "mandate": null,
    "objective": "…", "comment": "…", "armed": false,
    "start_date": "2019-03-04", "end_date": "2019-03-05",
    "attributes": [{ "attribute_uuid", "key", "value": … }],
    "legs": [
      { "uuid", "id", "transport_uuid", "mandate_uuid",
        "start_date", "end_date", "placeholder_dates": false,
        "members": [{ "employee_uuid", "leader": true, "pilot": false }],
        "days": [{ "uuid", "date": "2019-03-04", "start_time": "06:10:00", "end_time": "14:35:00",
                   "rest_minutes": 0, "start": "2019-03-04T06:10:00+08:00", "end": "2019-03-04T14:35:00+08:00",
                   "has_track": true }],
        "waypoints": [
          { "uuid", "id", "time": "2019-03-04T08:12:31+08:00", "location": [123.9, 14.1],
            "comment": "…", "source": "…", "last_modified_by_uuid": null,
            "attachments": [{ "uuid", "filename", "path": "attachments/<wp_uuid>/<filename>" }],
            "observation_groups": [
              { "uuid", "observations": [
                  { "uuid", "category_key": "animals.liveanimals", "category_hkey": "animals.liveanimals.",
                    "employee_uuid": null,
                    "attributes": [
                      { "key": "species", "type": "TREE", "value": "mammals.elephant", "label": "Elephant" },
                      { "key": "count", "type": "NUMERIC", "value": 3 },
                      { "key": "threats", "type": "MLIST", "value": ["snare", "fire"], "labels": ["Snare", "Fire"] },
                      { "key": "notes", "type": "TEXT", "value": "…" } ] } ] } ] } ] } ] } ] }
```

Waypoints are tied to leg days by the `patrol_waypoint(wp_uuid,
leg_day_uuid)` link table, so each waypoint lands on exactly one leg; the
emitter adds `leg_day_uuid` to every waypoint and reports waypoints whose
link points at a missing leg day under `warnings`.
`last_modified_by_uuid` is the employee who last edited the waypoint, which
SMART records; the observer, when known, is on each observation as
`employee_uuid`. Attribute values are typed by `dm_attribute.att_type`: LIST values are the
option `keyid`, TREE values are the node `hkey` without the trailing dot,
MLIST is an array, NUMERIC a number, BOOLEAN true/false, DATE an ISO date,
TEXT a string. `end_time` earlier than `start_time` on a leg day means the
day crossed midnight; `end` is advanced one day in that case.

**tracks.json**

```json
{ "tracks": [ { "leg_day_uuid", "leg_uuid", "patrol_uuid", "distance_km": 12.3,
                "start": "2023-06-19T13:46:45+08:00", "end": "2023-06-19T15:58:09+08:00",
                "parts": [ { "coordinates": [[lon, lat], …], "times": ["2023-06-19T13:46:45+08:00", …] } ] } ] }
```

`track.geometry` is big-endian extended WKB in hex with the Z flag set:
`0x80000002` LineString Z (504 rows in Lawin) or `0x80000005`
MultiLineString Z (2,144 rows), parsed with `struct`, no GIS dependency.
The Z coordinate is the point's timestamp as epoch milliseconds of the
**local wall-clock time read as if it were UTC**, not true UTC. Verified on
Lawin (2026-10-12): on 1,296 of 1,573 leg days with both a track and a
start time, the track's first point equals the leg day's `start_time` to
the minute when Z is decoded as a naive clock time, and the first-point
hours cluster at 05:00–10:00 local; decoded as UTC they would put patrols
in the afternoon. The exporter therefore decodes Z as a naive datetime and
anchors it to the bundle timezone like every other SMART time. Each part
keeps its coordinates and the matching ISO timestamps, so the importer
gets real per-point times rather than interpolated ones. `start` and `end`
are the first and last timestamps across parts. As a consistency check the
exporter compares each leg day's `start_time` with its track's first point
and warns when the majority disagree by an hour or more, which would mean
the tracks are in true UTC (another SMART version) or the leg-day times
are wrong; Lawin has a minority of 2017 leg days that are 8 hours off.

**attachments/.** Waypoint attachments copied from the decrypted filestore;
missing files are listed under `warnings` with the waypoint UUID.

**bundle.schema.json.** One schema document with `$defs` for each file and a
`oneOf` on the file name so a single validator call covers all four. The
schema is the contract: a change that removes or renames a field bumps
`bundle_schema_version`; additions do not. er-smart-sync copies the file
into its own tree and validates at load time.

## SMART data quirks document

Reading SMART data has enough non-obvious behaviour (zone-less times,
timestamps hidden in track Z coordinates, label fallbacks, value
encodings, export ordering rules) that users need it written down where
they work. `docs/smart-data-quirks.md` is the source, one `##` section per
quirk with a stable heading slug. `./smart-able browse` renders it to
`work/site/quirks.html` (Python-Markdown with the `toc` extension) so it
ships with every browser, including datasets served by the web app.
The app deep-links to sections: the Overview timezone line, the Patrols
view and patrol drawer (patrol times, tracks), the Data Model tab
(labels and languages, data model export), the Schema notes, exporter
warnings (`see quirks.html#…`), and the RUNBOOK warnings table. A test
checks every linked anchor exists.

## Multi-CA backups and the export zip

Backups: one `work/export/<ca_id>/` per CA; CAs with no categories and no
patrols (the cross-CA analysis row) are skipped. Export zips: exactly one CA.
`conservation_area.id` is not guaranteed filesystem-safe; the emitter keeps
`[A-Za-z0-9._-]` and replaces the rest with `_`.

## Warnings

In keeping with RUNBOOK.md's warnings table, the exporter warns (to stderr
and into `manifest.warnings`) when: the SMART version is outside 7.5.x; an
icon has no file for a referenced icon set; a label is missing in the
default language; a waypoint cannot be placed on a leg; an attachment file
is missing; a coordinate is outside WGS 84 range; the timezone was inferred
rather than configured; track times disagree with leg-day start times by
an hour or more on most leg days; `useEarthRanger` or any other XML attribute was
defaulted because the source column is unknown.

## Testing

smart-able has no test suite yet. This adds `tests/` with pytest, run with
`uv run pytest`:

- Unit tests for `datamodel_xml.py` and `bundle.py` on a tiny in-memory
  SMART database built with DuckDB in a fixture (two categories, one of each
  attribute type, one configurable model, two patrols, one track, one
  waypoint with two observations). Golden-file assertions for the XML and
  JSON.
- A schema test that validates every bundle file the fixture produces
  against `bundle.schema.json` with the `jsonschema` package (dev extra).
- An integration test, skipped unless `SMART_ABLE_REFERENCE_DIR` is set,
  that runs the exporter on the Lawin Parquet and `verify_xml.py` against
  the reference exports.
- The browser tab gets the same headless-Chrome click-through used for the
  other views, scripted under `/tmp/claude-smart-able` as before.

## Risks and open items

| Item | Resolution |
| --- | --- |
| Exact icon file naming in the export | Read from the reference export; until then icons section is emitted with stored filenames and a warning. |
| `useEarthRanger`, `extraData` keys, element and attribute ordering in CM XML | Confirm against the reference export; Botswana sample is the interim guide. |
| Namespace version for SMART 8.x backups | Table in the emitter; 8.1 backup expected later will show whether the DataModel format changed. |
| Icon file names in the export | They are the exporting install's `iconfile` row UUIDs: our output matches an export made on the source install, and `verify_xml --ignore-icon-files` sets them aside when the reference came from another install. Verified on Camarines Norte, 2026-10-12. |
| Legs starting 1970-01-01 | SMART's placeholder for an unset start date; it generates a leg-day row per day up to the end date. The bundle keeps the rows, marks the leg `placeholder_dates: true`, and warns; the importer clamps to days with evidence. |
| Track Z timestamps on older SMART versions | Lawin (7.5.x) stores epoch milliseconds in Z. If a backup has Z values outside 1990–2100 when read as milliseconds, the exporter omits `times` for that track and warns, and the importer falls back to spreading points across the leg day. |

## Follow-ups (not in this spec)

- Web app: download links for the XML files and a zipped bundle per dataset.
- Profiles and Entities in the bundle, once the ER-side model is decided.
