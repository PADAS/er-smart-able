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

SMART Profiles (internally `i2`, tables `i_*`) exists only if the plugin was
installed. It tracks persistent entities: people, vehicles, places, or case
files for recurring threats, depending on how a site uses it.

- `i_entity` rows are typed by `i_entity_type`. An entity's display name is
  the value of its type's `id_attribute_uuid` attribute.
- `i_entity_attribute_value (entity_uuid, attribute_uuid, string_value,
  double_value, list_item_uuid, employee_uuid)` holds its attributes.
- `i_record` rows are dated records (`title`, `primary_date`, `status`,
  `source_uuid` → `i_recordsource`), linked to entities many-to-many through
  `i_entity_record`.
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

## Version differences

From comparing the SMART source at releases 7.5.6 / 7.5.9 and 8.1.3. The
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
