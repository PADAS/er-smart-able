# How SMART stores data

A reference for working with the Parquet output of `./smart-able extract`, and
for building the Export and Load stages. Table and column names are from a
SMART 7.5.4 database (SMART Desktop 7.5.6) unless noted. What changes in SMART
8.x is listed under [Version differences](#version-differences). To see a
table's actual columns:
`duckdb -c "describe select * from 'work/parquet/<table>.parquet'"`.

## Storage

- **Engine.** SMART Desktop keeps all data for all conservation areas (CAs) in
  one embedded Apache Derby database (`data/database/smartdb/`), accessed
  through Hibernate. Every table lives in schema `smart`.
- **Keys.** Primary keys are random UUIDs stored as `CHAR(16) FOR BIT DATA`
  (16 raw bytes). The dump writes them as 32-character lowercase hex.
- **Scoping.** Almost every table has a `ca_uuid` column linking it to
  `conservation_area`. A database usually also contains SMART's demo CA (id
  `SMART`, "Example Conservation Area") and the `CCAA` pseudo-CA used for
  cross-CA analysis.
- **Schema version.** `db_version (version, plugin_id)` holds one row per SMART
  plugin; the core version is the row with `plugin_id = 'org.wcs.smart'`.
- **Attachments are not in the database.** Only filenames are stored; the files
  live in the backup's `filestore/` folder, encrypted (see
  [Attachments](#attachments)).

## Core entities

```
conservation_area ─┬─ employee ── agency, rank
                   ├─ team, station
                   ├─ language ── i18n_label (all display names)
                   ├─ dm_category (tree) ⇄ dm_cat_att_map ⇄ dm_attribute
                   │                                └─ dm_attribute_list / dm_attribute_tree
                   └─ patrol ─ patrol_leg ─┬─ patrol_leg_members ── employee
                                           └─ patrol_leg_day ─┬─ track (GPS line)
                                                              └─ patrol_waypoint ── waypoint

waypoint ─┬─ wp_attachments (filenames)
          └─ wp_observation_group ── wp_observation ─┬─ dm_category  (what was observed)
                                                     ├─ employee     (observer)
                                                     └─ wp_observation_attributes (values)
```

### Waypoints

`waypoint` is the shared location-and-time record for every data source.

| Column | Meaning |
| --- | --- |
| `x`, `y` | Longitude and latitude, WGS84 decimal degrees. `0,0` means no GPS fix. |
| `datetime` | Local wall-clock time, **no timezone** (see [Time](#time)). |
| `source` | Which tool recorded it: `PATROL`, `INDINC` (independent incident), `SMARTCOLLECT`, `ASSET`, `SURVEY`. |
| `direction`, `distance` | Optional offset from the observer's position to the observed thing. The stored `x`/`y` are the observer's position. |
| `id`, `wp_comment` | Display id and free-text comment. |

### Patrols

A `patrol` has one or more `patrol_leg` rows (each with a transport type,
mandate, and members in `patrol_leg_members`, one of them `is_leader`). Each
leg has one `patrol_leg_day` per day, and each leg-day has:

- **Waypoints**, through the join table `patrol_waypoint (wp_uuid, leg_day_uuid)`.
- **A GPS track**, in `track (patrol_leg_day_uuid, geometry, distance)`.
  `geometry` is a WKB LineString or MultiLineString. Track points have **no
  timestamps**; the only time context is the leg-day's date and its
  `start_time`/`end_time`.

Through SMART 8.0, `patrol.patrol_type` is a code (`GROUND`, `MARINE`,
`AIR`); SMART 8.1 replaced it (see [Version differences](#version-differences)).
Team, station, mandate, and transport are references to named rows.

### Observations

An observation is "this category was seen here, with these attribute values":

- `wp_observation_group (uuid, wp_uuid)` groups observations at a waypoint.
- `wp_observation (uuid, wp_group_uuid, category_uuid, employee_uuid)` names the
  category and the observer.
- `wp_observation_attributes` holds the values, one row per attribute
  (entity–attribute–value).

### The data model (categories and attributes)

Each CA defines its own observation vocabulary:

- `dm_category` is a tree (`parent_category_uuid`). `keyid` is the node's key
  and **`hkey` is the full dotted path**, e.g. `threats.cuttingoftrees.`. The
  `hkey` is stable across exports and is the natural key for mapping to
  EarthRanger event types.
- `dm_attribute` defines a field: `keyid`, `att_type`, `is_required`, numeric
  `min_value`/`max_value`, and an optional `regex`.
- `dm_cat_att_map` says which attributes belong to which categories.
- `dm_attribute_list` holds the options of LIST attributes, and
  `dm_attribute_tree` the nodes of TREE attributes (also with an `hkey`).

Where each attribute type keeps its value in `wp_observation_attributes`:

| `att_type` | Value column |
| --- | --- |
| `NUMERIC` | `number_value` |
| `BOOLEAN` | `number_value` (1.0 = true, 0.0 = false) |
| `TEXT` | `string_value` |
| `DATE` | `string_value` (`yyyy-MM-dd`)\* |
| `TIME` (8.1+) | `string_value` (`HH:mm:ss`)\* |
| `LIST` | `list_element_uuid` → `dm_attribute_list` |
| `TREE` | `tree_node_uuid` → `dm_attribute_tree` |
| multi-select list | rows in `wp_observation_attributes_list`\* |
| `LINE` (8.0+) | `geom` (WKB), `number_value` = length in km, `string_value` = how it was captured (`MANUAL_DRAW`, `MANUAL_POINT`, `GPS_MANUAL`, `GPS_AUTO`, `UNKNOWN`)\* |
| `POLYGON` (8.0+) | `geom` (WKB), `number_value` = perimeter in km, `number_value_2` = area in km², `string_value` = how it was captured\* |

\* From the SMART source (`WaypointObservationAttribute`,
`GeometryAttributeValue`); the 7.5.4 backup this was checked against has no
values of these kinds.

**Exporting it.** `./smart-able export` rebuilds SMART's own DataModel and
ConfigurableModel XML from these tables (`export/datamodel_xml.py`), byte
for byte where a reference export has been checked, so `er-smart-sync
datamodel --from-file` can run without SMART Connect. The mapping and the
ordering rules are in the spec,
`docs/superpowers/specs/2026-10-12-datamodel-export-and-migration-bundle-design.md`.

### Where the "conditional logic" is: the tree is the rule

People who know SMART forms talk about their conditional logic. There is
none in the sense of "if attribute X has value Y, show or require Z": no
table or XML element in a 7.5.x database declares a condition on another
field's value. The `is_visible` columns that exist are static switches:
`screen_option` (which patrol-screen fields such as station, armed or
comment a CA shows), `ct_metadata_value` (Connect/CyberTracker metadata
packages) and the Profiles working-set tables. What SMART has instead is
*branch-time* logic: a ranger taps down a tree of categories before
entering any value, and the leaf they land on decides which attributes the
form asks for, which options each list offers, and whether a photo is
required. Anything another tool would write as a rule, SMART writes as a
different node at the end of a different path. Two layers do this.

**Layer 1, the DataModel tree: what the CA can record.** A child category
inherits its parent's attributes and adds its own (`dm_cat_att_map`; in the
XML, `<attributes attributekey isactive>` under each `<category>`). From
Lawin's `datamodel.xml`:

```xml
<category key="threats">
    <attributes isactive="true"  attributekey="actiontaken"/>
    <attributes isactive="true"  attributekey="levelofresponserequired"/>
    <attributes isactive="true"  attributekey="note"/>
    <category key="hunting">
        <attributes isactive="true"  attributekey="approximatedistance"/>
        <attributes isactive="false" attributekey="levelofresponserequired"/>
        <attributes isactive="true"  attributekey="species"/>
        <attributes isactive="true"  attributekey="unit"/>
        <attributes isactive="true"  attributekey="volumeorcount"/>
    </category>
    <category key="annualandperennialfarming">
        <attributes isactive="true"  attributekey="approximatedistance"/>
        <attributes isactive="false" attributekey="levelofresponserequired"/>
        <attributes isactive="true"  attributekey="sizeoffarminha"/>
    </category>
```

"Hunting" records action taken, level of response and note from Threats
plus distance, species, unit and count of its own; "Annual and Perennial
Farming" shares the Threats three and adds distance and farm size. The
difference between threat types is which attributes each adds, fixed by
where it sits in the tree.

The `isactive="false"` rows need care. All 16 Lawin threat types carry one
for `levelofresponserequired`, an attribute they also inherit from Threats,
yet both Lawin forms ask for it on every threat type and the recorded
observations hold it (139 Farming, 523 Cutting of Trees and 4 Hunting
observations have a value). So in SMART a child's inactive row for an
inherited attribute does **not** hide that attribute.

`er-smart-sync datamodel` reads it the other way. The child's row wins, and
the field is marked `deprecated: true` in a v2 event type (`readOnly: true`
in v1); ER's web client leaves deprecated fields out of the report form. On
phinney, a data-model-only push left "Level of response required" off the
form of every Lawin threat type, although the imported events keep their
recorded values. A push with the configurable model keeps the field active,
because the form's `IS_VISIBLE` of 1.0 decides (checked by dry run,
2026-10-16). Do not read these rows as switch-offs without checking the
forms and the observations.

Attributes themselves carry only unconditional validation: `is_required`,
`regex`, `min_value`/`max_value` (`isrequired`, `<qa_regex>`, `<qa_minmax>`
in the XML).

**Layer 2, the ConfigurableModel tree: what one form shows.** A configurable
model (one `configurable_model_<uuid>.xml` each) is a hand-built navigation
tree over the DataModel for one SMART Mobile form. Its tables: `cm_node`
(the tree and per-node settings), `cm_attribute` (an attribute placed on a
node), `cm_attribute_option` (per-placement options), `cm_attribute_config`
(a curated option list), and `cm_attribute_list` / `cm_attribute_tree_node`
(which list values and tree nodes that config shows). It can:

- *Add grouping nodes that are not DataModel categories.* Botswana's form
  has Animal Records → Animal with Problem → Snared Animal → Large Predator
  Snared Animal; only the last node has a `categoryKey`
  (`cm_node.category_uuid` is null for the others).
- *Point several nodes at the same category, each with its own settings.*
  Botswana defines ten carcass nodes ("Large Predator Carcass", "Small
  Predator Carcass", "Herbivore Carcass", "Domestic Animal Carcass", "Other
  Species Carcass", and a second set of five), all with
  `categoryKey="carcass"`. Each has its own `photoRequired` (true for large
  predators, false for small predators and other species) and its own
  `<attributeConfig>` per attribute. This is how SMART says "the photo rule
  and the species list depend on the kind of carcass": not a dependency, a
  branch per case.
- *Hide an attribute on one node.* Every `<attribute>` placed on a node
  carries per-placement options in `cm_attribute_option`, keyed by
  `option_id`: `IS_VISIBLE`, `MULTISELECT`, `FLATTEN_TREE`, `ENTER_ONCE`,
  `DEFAULT_VALUE`, `NUMERIC`, `IMAGE`. `IS_VISIBLE` at 0.0 hides that
  attribute on that node only. Of Botswana's 889 attribute placements, 620
  are 1.0, 246 are 0.0 (hidden), and 23 are 2.0, a value whose meaning is
  not established yet; both Lawin forms show all 108 of theirs (1.0). This
  is the form-level switch-off that Layer 1's inactive rows are not.
- *Narrow the options a list shows.* Each `<attributeConfig>` lists the
  DataModel's values as `<listItem>`/`<treeNode>` with `isActive`
  (`cm_attribute_list.is_active` and `cm_attribute_tree_node.is_active`).
  In Botswana 26 configs hide options: `smallcarnivore` shows 9 of 15
  species (genets and mongooses hidden), `affiliationofcommunitymember` 21
  of 26, `activityundertaken` 6 of 11. Configs are per node, so two branches
  can offer different subsets of one list: "Other Species Carcass" offers a
  different `otherspecies` list (9 of 15, with Ostrich and Baboon, Chacma)
  than the other carcass nodes (7 of 15).
- *Set per-node collection behaviour:* `photoAllowed`, `photoRequired`,
  `collectMultipleObs`, `useSingleGpsPoint` (same column names on
  `cm_node`).

The Lawin backup holds two conservation areas, Albay (050500) and Guinobatan
(050504), each with one configurable model named "R05 Lawin" (different
uuids). Both are shallow (Forest Condition; Indicator Species; Threats → 16
threat types), show every attribute and every option, and so add nothing to
Layer 1; Botswana leans on Layer 2. The browser's Data Model tab shows both
layers: pick a configurable model to see which options each form keeps.

**What this means for EarthRanger.**

1. Flattening keeps Layer 1's structure, with one exception.
   `er-smart-sync datamodel` creates one ER event type per leaf category
   with its inherited and own attributes, and needs no conditional schema
   for that. The exception is an inherited attribute that a child marks
   inactive: the event type deprecates it even where the SMART form still
   asks for it (see Layer 1 above). Check those attributes against the
   forms before a data-model-only push.
2. Layer 2 has two translations, and the choice is a product decision.
   `--cm-variant-mode split` (the default) makes one ER event type per CM
   node, so Botswana gets ten carcass report types, each with its own
   narrowed lists. Per-node photo rules do not transfer: neither the SMART
   client nor the event-type builders read `photoRequired` or
   `photoAllowed`, so ER does not require a photo where the SMART node
   did. When it reads a configurable model, the
   SMART client maps each placement's `IS_VISIBLE` onto the attribute's
   active flag (`smartconnect/models.py`, `generate_category_attributes`),
   so attributes a form hides are inactive in its event type. It treats
   only 1.0 as visible, so Botswana's 23 placements at 2.0 also come out
   inactive; check what 2.0 means in SMART before trusting that. `--cm-variant-mode consolidate` makes one
   event type per DataModel category and uses ER's v2 conditional sections
   with a `variant` discriminator dropdown, the one place where SMART's
   tree becomes real *value-time* logic in ER. See
   [CM variant groups](https://padas.github.io/earthranger-smart-utils/concepts/cm-variants/)
   in the er-smart-sync docs.
3. Historical data records the leaf, not the path. `wp_observation` carries
   the DataModel category and the values; the CM node used to collect them
   is not stored anywhere. That is why `import-patrols` can map every old
   observation to an event type by category alone, and why CM variants such
   as Botswana's carcass types can only be told apart for data collected in
   ER from now on, not for migrated history.

   As of er-smart-sync 0.8.0 the import therefore supports only categories
   with **one** event type on the site (a `datamodel --from-file` push, or a
   CM push whose variant groups have one member). After a *split* push,
   `patrol-preflight` reports the affected categories as a blocking finding
   ("exist only as configurable model variants"), and `import-patrols
   --allow-blocking` imports the other patrols and skips these; a variant
   mapping is a listed follow-up. After a *consolidate* push the event type
   has the plain `<prefix>_<category path>` value, so preflight matches it
   like any other type and does **not** warn, but the import writes the
   SMART attribute keys (`species`, `sex`) while the consolidated schema
   expects `section_N_<key>` names and a `variant` discriminator value, so
   the events land with details the form does not render. For a site whose
   history includes a variant category, push the data model without the
   configurable model (or with `--cm-variant-mode split` and accept the
   skips) until the mapping exists.

   That advice is only for sites with variant categories, and it costs
   something: a data-model-only push deprecates the inherited attributes
   described under Layer 1. Push a site without variant groups, such as
   Lawin, with its configurable model. If both pushes end up on one site,
   `patrol-preflight` reports those categories as matching more than one
   event type; pass `--event-type-prefix` to pick the push to import
   against.

The tree can always be expanded into value-time rules (consolidate mode does
that). The reverse is not true: a rule such as "ask for the number of
snares only when the method is snaring" has no place in a SMART data model
or configurable model, so a SMART form never contains one.

### Display names (i18n)

Named rows (categories, attributes, list options, teams, stations, …) have no
name column. Names live in `i18n_label (language_uuid, element_uuid, value)`,
where `element_uuid` is the named row's uuid. Each CA has its languages in
`language (ca_uuid, code, isdefault)`; use the default language's label, and
fall back to `keyid`.

```sql
-- observations with their category's display name
select w.datetime, w.x as lon, w.y as lat, l.value as category, c.hkey
from 'parquet/wp_observation.parquet' o
join 'parquet/wp_observation_group.parquet' g on o.wp_group_uuid = g.uuid
join 'parquet/waypoint.parquet' w on g.wp_uuid = w.uuid
join 'parquet/dm_category.parquet' c on o.category_uuid = c.uuid
left join 'parquet/i18n_label.parquet' l
  on l.element_uuid = c.uuid
 and l.language_uuid in (select uuid from 'parquet/language.parquet' where isdefault);
```

## Profiles (optional plugin)

SMART Profiles (internally `i2`, the successor of the SMART Intelligence
plugin; tables `i_*`, attachments under `intelligence2/`) exists only if the
plugin was installed. Its vocabulary is easy to misread, so from the top:

| Level | Table | What it is |
| --- | --- | --- |
| Plugin | — | SMART Profiles itself. |
| **Profile** | `i_profile_config` | A configured tracker inside the plugin, not a dossier on one thing. It has a name (`i18n_label`), a colour, the main-menu label a SMART user sees (`i_config_option` with `keyid = 'mainmenu'`, per CA), its own entity types (`i_profile_entity_type`), its own record sources (`i_profile_record_source`), and per-employee permissions (`i_permission`). A CA can define several Profiles side by side. |
| Entity type | `i_entity_type` | A category within a Profile, with its attributes (`i_entity_type_attribute` → `i_attribute`, grouped by `i_entity_type_attribute_group`) and the attribute that serves as display name (`id_attribute_uuid`). |
| Entity | `i_entity` | One instance of a type; `profile_uuid` says which Profile it belongs to. |
| Record | `i_record` | A dated event about one or more entities, typed by a record source. |
| Relationship | `i_entity_relationship` | A typed link between two entities (`i_relationship_type`, which may span two Profiles). |

What a Profile tracks is up to the site. The designed use is persistent
subjects, people, vehicles, or places, linked by relationships. The
Philippine Lawin sites instead define one Profile with the menu label
"Threat/Response Tracking", whose entity types are the kinds of threat a
patrol can find, whose entities are individual threat sightings, and whose
record sources are kinds of response; they use no relationships. See
[docs/decisions.md](decisions.md) for how that shaped the browser.

- `i_entity` rows are typed by `i_entity_type`. An entity's display name is
  the value of its type's `id_attribute_uuid` attribute.
- `i_entity_attribute_value (entity_uuid, attribute_uuid, string_value,
  double_value, double_value2, list_item_uuid, employee_uuid)` holds its
  attributes. `i_attribute.type` is `TEXT`, `NUMERIC`, `DATE`, `LIST`,
  `POSITION` (x in `double_value`, y in `double_value2`), or an employee
  reference. An entity can also carry points through `i_entity_location` →
  `i_location (geometry WKB, datetime)`.
- `i_record` rows are dated records (`title`, `primary_date`, `status`,
  `description`, `comment`, `source_uuid` → `i_recordsource`), linked to
  entities many-to-many through `i_entity_record`. `created_by` is an
  `employee` uuid.
- A record's attributes are defined by its record source:
  `i_recordsource_attribute (source_uuid, attribute_uuid, seq_order,
  is_multi)` → `i_attribute (keyid, type)`, with `type` one of `TEXT`,
  `NUMERIC`, `DATE`, `LIST`. Values are in `i_record_attribute_value
  (record_uuid, attribute_uuid, string_value, double_value, double_value2)`,
  where `attribute_uuid` is the **`i_recordsource_attribute`** uuid, not the
  `i_attribute` one. List values are rows of `i_record_attribute_value_list
  (value_uuid, element_uuid)` pointing at `i_attribute_list_item`; a
  multi-select attribute has several. Labels for attributes and list items
  come from `i18n_label` as usual.
- Files: `i_attachment`, linked through `i_entity_attachment` and
  `i_record_attachment`.

Profiles entities are not keyed to observations. Any connection is by
convention (matching type names, copied coordinates), not by a foreign key.

## Time

SMART stores `waypoint.datetime` and similar timestamps as **local wall-clock
time with no timezone**, so a patrol in Kenya and one in Peru both record
plain `08:30`. To get real instants (which EarthRanger needs), assign each CA
a timezone. `./smart-able browse` infers one per CA from the median of its
waypoint coordinates (Python `timezonefinder`) and writes
`work/site/data/timezones.json`.

## Geometry

- Waypoints: plain `x`/`y` doubles.
- Tracks (`track.geometry`) and area boundaries (`area_geometries.geom`, typed
  by `area_type`: `CA`, `ADMIN`, `MNGT`, …) are JTS **WKB** in BLOB columns. In
  the Parquet they are hex strings; parse with DuckDB spatial:
  `ST_GeomFromWKB(unhex(geometry))`.

## Attachments

Filenames are in `wp_attachments (wp_uuid, filename)` for waypoint photos and
`i_attachment (ca_uuid, filename)` for Profiles. The files are at:

| Kind | Path in the backup |
| --- | --- |
| Waypoint photo | `filestore/<ca_uuid>/patrol/<patrol_uuid>/<filename>` |
| Profiles attachment | `filestore/<ca_uuid>/intelligence2/attachments/<filename>` |

They are encrypted with **AES-128-CBC**: the key is the 16 raw bytes of the CA
uuid (which is also the folder name), and the IV is the first 16 bytes of the
file. To decrypt one file by hand:

```sh
IV=$(od -An -tx1 -N16 file.jpg | tr -d ' \n')
tail -c +17 file.jpg | openssl enc -d -aes-128-cbc -K <ca_uuid_hex> -iv "$IV" -out out.jpg
```

`extract/decrypt_filestore.sh` does this for the whole filestore. Old
backups often have photo filenames in the database whose files are missing
from the filestore.

## How the Parquet output represents values

- One file per table: `work/parquet/<table>.parquet` (lowercase table name).
- Column types come from Derby's JDBC metadata (no type guessing), so text ids
  such as `000123` keep their leading zeros.
- UUIDs and other binary columns are lowercase hex strings; geometries are
  hex-encoded WKB.
- `NULL` stays `NULL`; an empty string stays `''`.

## Conservation Area exports

SMART Desktop's File → Export Conservation Area writes a `.zip` that holds one
conservation area without a Derby database:

| Path | Contents |
| --- | --- |
| `conservationarea.dat` | Five lines, CRLF: the CA uuid, the CA id (e.g. `051600`), the CA name, a blank line, the schema version (e.g. `7.5.4`). |
| `database/smart.<table>.<Entity>.def` | Line 1 `SMART.<TABLE>`, line 2 the column names, comma-separated. CRLF, no newline after the last line. No types. |
| `database/smart.<table>.<Entity>.dat` | The rows, as Derby's table export writes them: RFC-4180 CSV, no header, strings quoted, NULL as an unquoted empty field, booleans `true`/`false`, dates and timestamps ISO, binary (uuids, WKB geometry) as lowercase hex. UTF-8, LF line endings. |
| `database/db_versions.dat` | `plugin_id,version` rows (the `db_version` table, columns swapped; it has no `.def`). |
| `filestore/` | The CA's attachments, encrypted as in [Attachments](#attachments), but without the `<ca_uuid>/` level: `patrol/` and `intelligence2/` sit at the top. The key is the uuid from `conservationarea.dat`. |

The export carries the tables SMART considers part of a conservation area: in
a 7.5.4 export, 216 tables, which is every table the browser uses. Left out
are the install-wide ones (`connect_*`, `login_log`, `dm_aggregation_i18n`).
`extract/export_to_csv.sh` turns the dumps into the same CSV-plus-types layout
`DumpSmartDb` produces, taking the types from
`extract/smart_schema.tsv`.

## Version differences

From comparing the SMART source at releases 7.5.6 / 7.5.9 and 8.1.3; not yet
checked against a real 8.x backup. `./smart-able extract` compares every
backup's tables and columns with `extract/smart_schema.tsv`, the 7.5.4 schema,
and warns about the differences, so an 8.x backup lists its own deltas. The
things that did **not** change matter as much: the database credentials, the
`smart` schema, the backup zip layout (`smartdb/` and `filestore/` at the
root), the attachment encryption and filestore paths, WKB geometry, and
`waypoint.datetime` being local time.

| Change | Since | How smart-able handles it |
| --- | --- | --- |
| Derby 10.15 → 10.17, Java 21 | 8.0.0 | Bundles Derby 10.17, which also reads 7.5 databases. Needs Java 19+. |
| `patrol.patrol_type` (code) dropped; `patrol.patrol_type_uuid` → `patrol_type (uuid, keyid)` added. The old GROUND/MARINE/AIR codes moved to `patrol_transport_group`, reached through `patrol_leg.transport_uuid → patrol_transport.patrol_transport_group_uuid`. | 8.1.0 | The browser shows the code when present, otherwise the new type's label. |
| New attribute types `POLYGON`, `LINE` with columns `wp_observation_attributes.geom` and `number_value_2` | 8.0.0 | Shown as area/perimeter or length. |
| New attribute type `TIME` | 8.1.0 | Shown as its text value. |
| `waypoint.source` values `INTEGRATE`, `INTEGRATEPLLINK`, `INTEGRATEPATROL` rewritten to `INDINC`; new `waypoint.incident_type_uuid` → `incident_type` tells them apart | 8.1.0 | Not used by the browser (it shows patrol waypoints). Relevant for Export. |
| Audit timestamps stored in UTC: `waypoint.last_modified`, and in Profiles `i_entity.date_created`/`date_modified`, `i_record.date_created`/`last_modified_date`. The upgrade rewrote existing values using a timezone chosen in a dialog, which isn't recorded. | 8.0.0 | Profiles creation dates are converted from UTC to the CA's timezone when the database is 8.0 or later. `waypoint.datetime` and `i_record.primary_date` stay local. |
| New tables, e.g. `attachment_tag`, `attachment_tag_link` (8.0); `patrol_transport_group`, `patrol_attribute_tree`, `incident_type` (8.1). Dropped: `entity*` (8.0), `paws_*` (8.1). | 8.0 / 8.1 | The dump copies whatever tables exist. |
| Backup zips written with Zip64 and uncompressed (stored) entries | 8.1.2 | Handled by standard `unzip` 6.0. |
| The shared employee record has uuid `…0001` instead of all zeros (fixed by the 8.0.1 upgrade) | 8.0.0 only | No effect on joins. |

`db_version` for `org.wcs.smart` reads `8.0.0`, `8.0.1`, or `8.1.0`; SMART
8.1.1 through 8.1.3 still report `8.1.0` because their schema is unchanged.
