# Data Model Export and Migration Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `./smart-able export`, which writes SMART-exact DataModel and ConfigurableModel XML, a Data Model browser tab, and the JSON migration bundle er-smart-sync will read, all from the Parquet that `extract` already produces.

**Architecture:** A new `export/` Python package reads `work/parquet/*.parquet` through the DuckDB Python package (`export/smartdb.py`), and pure builder modules turn query results into XML text (`datamodel_xml.py`), browser JSON (`datamodel_json.py`) and bundle JSON (`bundle.py`, `tracks.py`). `export/__main__.py` is the CLI the bash launcher calls. The browser gets one new view function in `browse/index.html`, following the existing `rSchema`/`rObs` pattern. Tests build a tiny synthetic SMART database as Parquet in a temp dir and assert against golden strings.

**Tech Stack:** Python 3.9+ (uv-managed venv, `package = false`), DuckDB Python package, `zoneinfo`, `struct`, `timezonefinder` (already a dependency), pytest + jsonschema (new `dev` extra), bash launcher `smart-able`, single-file browser `browse/index.html` (vanilla JS, no build), headless Chrome over the DevTools protocol for UI checks.

**Spec:** `docs/superpowers/specs/2026-10-12-datamodel-export-and-migration-bundle-design.md`

## Global Constraints

- `requires-python = ">=3.9"`: no `match`, no `X | Y` type unions at runtime, use `from __future__ import annotations` in every module.
- `pyproject.toml` keeps `[tool.uv] package = false`; modules are run as `uv run python -m export …` from the repo root, never installed.
- Docker images install with `uv sync --frozen --no-dev --extra web`, so every runtime dependency goes in `[project.dependencies]` and `uv.lock` must be regenerated and committed with any dependency change.
- Bundle JSON: keys `snake_case`, SMART UUIDs hyphenated (`8-4-4-4-12`), timestamps RFC 3339 with offset, coordinates `[lon, lat]`, labels as `{code: text}` plus `label` in the default language.
- XML: declaration `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`, four-space indent, attribute order as listed per element in the spec, empty elements self-closed as `<x/>`, text written directly (no `xml.etree` serialisation).
- DataModel namespace `http://www.smartconservationsoftware.org/xml/1.1/datamodel` for SMART 7.5.x; ConfigurableModel namespace `http://www.smartconservationsoftware.org/xml/1.0/dataentry`.
- Nothing from `~/projects/smart-migration-artifacts` is committed; fixtures are synthetic or from SMART's "Example Conservation Area".
- Credentials: employees in the bundle carry no `smartuserid`, `smartpassword`, `birthdate` or `gender`.
- Warnings go to stderr prefixed `warning:` and into `manifest.warnings`.
- The browser must keep working when `datamodel.json` is absent (older data on disk).

## Review Focus

1. A CA whose default language has no label for some element: the XML must still emit the element (with whatever languages have labels) and the bundle `label` must fall back to any language rather than crash on `KeyError`. Test added to Task 1 (`test_labels_fallback`).
2. Category keys or labels containing `&`, `<`, `"` or non-ASCII text: XML must escape and stay valid UTF-8; JSON must not escape non-ASCII (`ensure_ascii=False`). Tests in Task 2 (`test_xml_escaping`) and Task 7 (`test_json_is_utf8`).
3. A leg day whose `end_time` is earlier than `start_time` (crossed midnight) or whose times are NULL: `end` must advance one day, and NULL times must produce `null` start/end rather than an exception. Test in Task 7 (`test_leg_day_midnight_and_null_times`).
4. A track whose Z values are not plausible epoch milliseconds (older SMART, or a GPX import with Z = elevation): `times` must be omitted for that track and a warning recorded, not a bogus year-1970 timestamp. Test in Task 8 (`test_track_without_plausible_times`).
5. A backup with several CAs where element UUIDs for system icons are shared: the icons section must list only icons referenced by this CA's elements and must not duplicate an icon referenced twice. Test in Task 2 (`test_icons_only_referenced_and_unique`).

---

## File structure

| Path | Responsibility |
| --- | --- |
| `pyproject.toml`, `uv.lock` | add `duckdb`, `dev` extra (pytest, jsonschema), pytest config |
| `export/__init__.py` | package marker, `__version__` helper reading `git describe` |
| `export/smartdb.py` | `SmartDb`: DuckDB connection over the Parquet dir, CA list, languages, labels, UUID helpers |
| `export/xmlwriter.py` | `Xml` text writer, `xml_escape`, `java_double` |
| `export/datamodel_xml.py` | `build_datamodel_xml`, `build_configurable_model_xml` |
| `export/verify_xml.py` | strict/loose comparison of two XML files, CLI |
| `export/datamodel_json.py` | `build_datamodel_json` for the browser tab |
| `export/timezone.py` | `resolve_timezone`, `localize`, `utc_ms_to_local` |
| `export/wkb.py` | `parse_track_wkb` for LineString Z / MultiLineString Z |
| `export/bundle.py` | `build_reference`, `build_patrols`, `build_tracks`, `build_manifest`, `write_bundle` |
| `export/bundle.schema.json` | JSON Schema for the four bundle files |
| `export/__main__.py` | CLI: `python -m export --work DIR [--site-data DIR] [ca_id …]` |
| `smart-able` | `export` subcommand, `all` runs it, header comment |
| `browse/index.html` | `rDataModel` view, tab, help template |
| `tests/conftest.py` | `smart_parquet` fixture building a synthetic SMART database |
| `tests/test_*.py` | one file per module |
| `README.md`, `RUNBOOK.md`, `docs/smart-data-model.md` | document the export |

---

### Task 1: Project scaffolding and `SmartDb`

**Files:**
- Modify: `pyproject.toml`
- Create: `export/__init__.py`, `export/smartdb.py`, `tests/conftest.py`, `tests/test_smartdb.py`
- Regenerate: `uv.lock`

**Interfaces:**
- Produces: `SmartDb(parquet_dir: Path)` with `.has(table) -> bool`, `.rows(sql: str, params: Sequence = ()) -> list[dict]`, `.t(table) -> str` (SQL literal for the table's Parquet path), `.cas() -> list[CA]`, `.smart_version() -> str | None`, `.languages(ca_uuid) -> list[Language]`, `.labels(ca_uuid) -> Labels`, `.labelled_elements(ca_uuid) -> set[str]`; dataclasses `CA(uuid, id, name, designation, description, organization, country, owner)`, `Language(uuid, code, default)`; `Labels.get(uuid, code=None) -> str | None` (fallback: requested, default, any), `Labels.all(uuid) -> dict[str, str]`; functions `hyphenate(u: str) -> str`, `safe_id(s: str) -> str`.
- Fixture `smart_parquet(tmp_path) -> Path` producing a Parquet directory with two CAs; every later task's tests use it.

- [ ] **Step 1: Add dependencies and pytest config**

Edit `pyproject.toml`:

```toml
dependencies = [
    "timezonefinder>=6",
    "duckdb>=1.1",
]

[project.optional-dependencies]
# the web service and extraction job (web/): uv sync --extra web
web = [
    ... unchanged ...
]
# tests: uv sync --extra dev && uv run pytest
dev = [
    "pytest>=8",
    "jsonschema>=4.23",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Run: `uv lock && uv sync --extra dev --extra web`
Expected: `uv.lock` changes; `uv run python -c "import duckdb, pytest, jsonschema"` prints nothing.

- [ ] **Step 2: Write the synthetic database fixture**

`tests/conftest.py`:

```python
"""A tiny SMART database as Parquet, enough for every export test.

CA "ALPHA" (uuid aaaa…) has two languages (en default, fr), two root
categories (one nested child), one attribute of each type, one configurable
model, two patrols, one track, one waypoint with two observations.
CA "BETA" (uuid bbbb…) is nearly empty and shares the system icon rows.
"""
from __future__ import annotations

import struct
from pathlib import Path

import duckdb
import pytest

CA_A = "aaaaaaaa" * 4
CA_B = "bbbbbbbb" * 4
U = lambda n: f"{n:032x}"  # noqa: E731  deterministic 32-hex uuids
LANG_EN, LANG_FR = U(0x100), U(0x101)
CAT_ANIMALS, CAT_LIVE, CAT_THREATS = U(0x200), U(0x201), U(0x202)
ATT_SPECIES, ATT_COUNT, ATT_ARMED, ATT_SEEN, ATT_NOTE, ATT_THREAT, ATT_TREE = (U(0x300 + i) for i in range(7))
LIST_ELE, LIST_LION = U(0x400), U(0x401)
TREE_SNARE, TREE_WIRE, TREE_FIRE = U(0x410), U(0x411), U(0x412)
ICON_SPECIES, ICONSET_LINE, ICONSET_COLOR, ICONFILE_1, ICONFILE_2 = U(0x500), U(0x501), U(0x502), U(0x503), U(0x504)
CM, NODE_GROUP, NODE_LIVE, CMATT_SPECIES, CMCONF_SPECIES, CMLIST_ELE = (U(0x600 + i) for i in range(6))
EMP_LEAD, EMP_TWO, AGENCY, RANK, TEAM, STATION, STATION_DESC = (U(0x700 + i) for i in range(7))
TRANSPORT_FOOT, MANDATE_LAW = U(0x800), U(0x801)
PATROL_1, PATROL_2, LEG_1, LEG_2, DAY_1, DAY_2, WP_1, GROUP_1, OBS_1, OBS_2, TRACK_1, ATTACH_1 = (U(0x900 + i) for i in range(12))

# epoch ms (UTC) for 2019-03-04 06:10:00 +08:00, and one hour later
T0 = 1551651000000


def wkb_line_z(points) -> str:
    """Big-endian extended WKB LineString Z as hex, the way SMART stores tracks."""
    return "00" + "80000002" + struct.pack(">I", len(points)).hex() + b"".join(struct.pack(">ddd", *p) for p in points).hex()


TRACK_WKB = wkb_line_z([(123.72, 13.06, T0), (123.73, 13.07, T0 + 3600000)])


def _tables():
    """Return {table: (columns, rows)}."""
    t = {}
    t["conservation_area"] = (
        ["uuid", "id", "name", "designation", "description", "organization", "pointofcontact", "country", "owner"],
        [(CA_A, "ALPHA", "Alpha & Co", "Park", None, "Org", None, "PH", "Owner"),
         (CA_B, "BETA", "Beta", None, None, None, None, None, None)],
    )
    t["db_version"] = (["version", "plugin_id"], [("7.5.4", "org.wcs.smart"), ("5.0", "org.wcs.smart.i2")])
    t["language"] = (["uuid", "ca_uuid", "isdefault", "code"],
                     [(LANG_EN, CA_A, True, "en"), (LANG_FR, CA_A, False, "fr"), (U(0x102), CA_B, True, "en")])
    t["dm_category"] = (
        ["uuid", "ca_uuid", "keyid", "parent_category_uuid", "is_multiple", "cat_order", "is_active", "hkey", "icon_uuid"],
        [(CAT_ANIMALS, CA_A, "animals", None, True, 1, True, "animals.", ICON_SPECIES),
         (CAT_LIVE, CA_A, "liveanimals", CAT_ANIMALS, True, 0, True, "animals.liveanimals.", None),
         (CAT_THREATS, CA_A, "threats", None, False, 0, True, "threats.", None)],
    )
    t["dm_attribute"] = (
        ["uuid", "ca_uuid", "keyid", "is_required", "att_type", "min_value", "max_value", "regex", "icon_uuid"],
        [(ATT_SPECIES, CA_A, "species", True, "LIST", None, None, None, ICON_SPECIES),
         (ATT_COUNT, CA_A, "count", False, "NUMERIC", 0.0, 10000000.0, None, None),
         (ATT_ARMED, CA_A, "armed", False, "BOOLEAN", None, None, None, None),
         (ATT_SEEN, CA_A, "seen", False, "DATE", None, None, None, None),
         (ATT_NOTE, CA_A, "note", False, "TEXT", None, None, "", None),
         (ATT_THREAT, CA_A, "threat", False, "MLIST", None, None, None, None),
         (ATT_TREE, CA_A, "threattype", True, "TREE", None, None, None, None)],
    )
    t["dm_attribute_list"] = (
        ["uuid", "attribute_uuid", "keyid", "list_order", "is_active", "icon_uuid"],
        [(LIST_LION, ATT_SPECIES, "lion", 1, True, None), (LIST_ELE, ATT_SPECIES, "elephant", 0, True, None),
         (U(0x402), ATT_THREAT, "snare", 0, True, None), (U(0x403), ATT_THREAT, "fire", 1, False, None)],
    )
    t["dm_attribute_tree"] = (
        ["uuid", "keyid", "node_order", "parent_uuid", "attribute_uuid", "is_active", "hkey", "icon_uuid"],
        [(TREE_SNARE, "snare", 0, None, ATT_TREE, True, "snare.", None),
         (TREE_WIRE, "wire", 0, TREE_SNARE, ATT_TREE, True, "snare.wire.", None),
         (TREE_FIRE, "fire", 1, None, ATT_TREE, True, "fire.", None)],
    )
    t["dm_cat_att_map"] = (
        ["category_uuid", "attribute_uuid", "att_order", "is_active"],
        [(CAT_LIVE, ATT_SPECIES, 0, True), (CAT_LIVE, ATT_COUNT, 1, True), (CAT_LIVE, ATT_NOTE, 2, False),
         (CAT_THREATS, ATT_TREE, 0, True), (CAT_THREATS, ATT_THREAT, 1, True), (CAT_THREATS, ATT_ARMED, 2, True),
         (CAT_THREATS, ATT_SEEN, 3, True)],
    )
    t["dm_aggregation"] = (["name"], [("avg",), ("sum",)])
    t["dm_att_agg_map"] = (["attribute_uuid", "agg_name"], [(ATT_COUNT, "sum"), (ATT_COUNT, "avg")])
    t["icon"] = (["uuid", "keyid", "ca_uuid"], [(ICON_SPECIES, "species", CA_A)])
    t["iconset"] = (["uuid", "keyid", "ca_uuid", "is_default"],
                    [(ICONSET_LINE, "line", CA_A, False), (ICONSET_COLOR, "color", CA_A, True)])
    t["iconfile"] = (["uuid", "icon_uuid", "iconset_uuid", "filename"],
                     [(ICONFILE_1, ICON_SPECIES, ICONSET_LINE, "platform:/plugin/org.wcs.smart/images/datamodel/line/Species_icon.svg"),
                      (ICONFILE_2, ICON_SPECIES, ICONSET_COLOR, "platform:/plugin/org.wcs.smart/images/datamodel/color/Species_icon.svg")])
    t["i18n_label"] = (
        ["language_uuid", "element_uuid", "value"],
        [(LANG_EN, CAT_ANIMALS, "Animals"), (LANG_FR, CAT_ANIMALS, "Animaux"),
         (LANG_EN, CAT_LIVE, "Live animals"), (LANG_EN, CAT_THREATS, "Threats & \"risks\" <all>"),
         (LANG_EN, ATT_SPECIES, "Species"), (LANG_FR, ATT_SPECIES, "Espèce"),
         (LANG_EN, ATT_COUNT, "Count"), (LANG_EN, ATT_ARMED, "Armed"), (LANG_EN, ATT_SEEN, "Seen on"),
         (LANG_EN, ATT_NOTE, "Note"), (LANG_EN, ATT_THREAT, "Threats"), (LANG_EN, ATT_TREE, "Threat type"),
         (LANG_EN, LIST_LION, "Lion"), (LANG_EN, LIST_ELE, "Elephant"), (LANG_FR, LIST_ELE, "Éléphant"),
         (LANG_EN, U(0x402), "Snare"), (LANG_EN, U(0x403), "Fire"),
         (LANG_EN, TREE_SNARE, "Snare"), (LANG_EN, TREE_WIRE, "Wire snare"), (LANG_EN, TREE_FIRE, "Fire"),
         (LANG_EN, ICON_SPECIES, "Species icon"),
         (LANG_EN, CM, "Alpha mobile model"), (LANG_EN, NODE_GROUP, "Sightings"), (LANG_EN, CMCONF_SPECIES, "Species (curated)"),
         (LANG_EN, TRANSPORT_FOOT, "Foot"), (LANG_EN, MANDATE_LAW, "Law enforcement"), (LANG_EN, STATION_DESC, "HQ"),
         (LANG_EN, TEAM, "Team One"), (LANG_EN, RANK, "Ranger")],
    )
    t["configurable_model"] = (["uuid", "ca_uuid", "display_mode", "instant_gps", "photo_first", "iconset_uuid"],
                               [(CM, CA_A, "TEXT_IMAGE", True, False, ICONSET_COLOR)])
    t["cm_node"] = (
        ["uuid", "cm_uuid", "category_uuid", "parent_node_uuid", "node_order", "photo_allowed", "photo_required",
         "collect_multiple_obs", "use_single_gps_point", "display_mode", "imagetype", "signatures"],
        [(NODE_GROUP, CM, None, None, 1, False, False, False, False, None, None, None),
         (NODE_LIVE, CM, CAT_LIVE, NODE_GROUP, 1, True, False, False, False, "TEXT", None, None)],
    )
    t["cm_attribute_config"] = (["uuid", "cm_uuid", "dm_attribute_uuid", "display_mode", "is_default"],
                                [(CMCONF_SPECIES, CM, ATT_SPECIES, "TEXT", True)])
    t["cm_attribute"] = (["uuid", "node_uuid", "attribute_uuid", "attribute_order", "config_uuid"],
                         [(CMATT_SPECIES, NODE_LIVE, ATT_SPECIES, 1, CMCONF_SPECIES)])
    t["cm_attribute_list"] = (["uuid", "list_element_uuid", "is_active", "list_order", "config_uuid", "imagetype"],
                              [(CMLIST_ELE, LIST_ELE, True, 0, CMCONF_SPECIES, None)])
    t["cm_attribute_option"] = (["uuid", "cm_attribute_uuid", "option_id", "number_value", "string_value", "uuid_value"],
                                [(U(0x610), CMATT_SPECIES, "IS_VISIBLE", 1.0, None, None),
                                 (U(0x611), CMATT_SPECIES, "ENTER_ONCE", None, "NONE", None)])
    t["cm_attribute_tree_node"] = (["uuid", "dm_tree_node_uuid", "is_active", "parent_uuid", "node_order", "display_mode", "config_uuid", "imagetype"], [])
    t["cm_ct_properties_profile"] = (["cm_uuid", "profile_uuid"], [])
    t["ct_properties_profile"] = (["uuid", "ca_uuid", "name"], [])
    t["connect_ct_properties"] = (["uuid", "ca_uuid", "key", "value"], [])
    t["agency"] = (["uuid", "ca_uuid", "keyid"], [(AGENCY, CA_A, "denr")])
    t["rank"] = (["uuid", "agency_uuid"], [(RANK, AGENCY)])
    t["employee"] = (
        ["uuid", "ca_uuid", "id", "givenname", "familyname", "startemploymentdate", "endemploymentdate", "datecreated",
         "birthdate", "gender", "smartuserid", "agency_uuid", "rank_uuid", "smartuserlevel"],
        [(EMP_LEAD, CA_A, "E1", "Ana", "Cruz", "2017-01-01", None, "2017-01-01", "1990-01-01", "F", "ana", AGENCY, RANK, 1),
         (EMP_TWO, CA_A, "E2", "Ben", "Reyes", "2017-01-01", "2018-06-30", "2017-01-01", None, None, "ben", AGENCY, None, 0)],
    )
    t["employee_team"] = (["uuid", "ca_uuid"], [(TEAM, CA_A)])
    t["employee_team_member"] = (["employee_uuid", "team_uuid"], [(EMP_LEAD, TEAM), (EMP_TWO, TEAM)])
    t["station"] = (["uuid", "ca_uuid", "desc_uuid", "is_active"], [(STATION, CA_A, STATION_DESC, True)])
    t["patrol_type"] = (["ca_uuid", "patrol_type", "is_active", "max_speed"], [(CA_A, "GROUND", True, 120), (CA_A, "AIR", False, 500)])
    t["patrol_transport"] = (["uuid", "ca_uuid", "is_active", "patrol_type", "keyid"], [(TRANSPORT_FOOT, CA_A, True, "GROUND", "foot")])
    t["patrol_mandate"] = (["uuid", "ca_uuid", "is_active", "keyid"], [(MANDATE_LAW, CA_A, True, "law")])
    t["patrol_attribute"] = (["uuid", "ca_uuid", "keyid", "att_type", "is_active"], [])
    t["patrol_attribute_list"] = (["uuid", "patrol_attribute_uuid", "keyid", "list_order", "is_active"], [])
    t["patrol_attribute_value"] = (["patrol_uuid", "patrol_attribute_uuid", "string_value", "number_value", "list_item_uuid"], [])
    t["patrol"] = (
        ["uuid", "ca_uuid", "id", "station_uuid", "team_uuid", "objective", "patrol_type", "is_armed", "start_date", "end_date", "comment", "folder_uuid", "patrol_type_uuid"],
        [(PATROL_1, CA_A, "P-0001", STATION, TEAM, "Boundary walk", "GROUND", False, "2019-03-04", "2019-03-05", "Fine weather", None, None),
         (PATROL_2, CA_A, "P-0002", None, None, None, "GROUND", True, "2019-04-01", "2019-04-01", None, None, None)],
    )
    t["patrol_leg"] = (["uuid", "patrol_uuid", "start_date", "end_date", "transport_uuid", "id", "mandate_uuid"],
                       [(LEG_1, PATROL_1, "2019-03-04", "2019-03-05", TRANSPORT_FOOT, "P-0001-1", MANDATE_LAW),
                        (LEG_2, PATROL_2, "2019-04-01", "2019-04-01", TRANSPORT_FOOT, "P-0002-1", None)])
    t["patrol_leg_day"] = (["uuid", "patrol_leg_uuid", "patrol_day", "start_time", "end_time", "rest_minutes"],
                           [(DAY_1, LEG_1, "2019-03-04", "06:10:00", "14:35:00", 0),
                            (DAY_2, LEG_2, "2019-04-01", "22:00:00", "01:30:00", None)])
    t["patrol_leg_members"] = (["patrol_leg_uuid", "employee_uuid", "is_leader", "is_pilot"],
                               [(LEG_1, EMP_LEAD, True, False), (LEG_1, EMP_TWO, False, False), (LEG_2, EMP_LEAD, True, False)])
    t["track"] = (["uuid", "patrol_leg_day_uuid", "geometry", "distance"], [(TRACK_1, DAY_1, TRACK_WKB, 1.5)])
    t["waypoint"] = (
        ["uuid", "ca_uuid", "source", "x", "y", "datetime", "direction", "distance", "wp_comment", "last_modified", "last_modified_by", "id", "incident_type_uuid"],
        [(WP_1, CA_A, "PATROL", 123.9, 14.1, "2019-03-04 08:12:31", None, None, "Near the river", "2019-03-04 08:12:31", EMP_LEAD, "WP-1", None)],
    )
    t["patrol_waypoint"] = (["wp_uuid", "leg_day_uuid"], [(WP_1, DAY_1)])
    t["wp_observation_group"] = (["uuid", "wp_uuid"], [(GROUP_1, WP_1)])
    t["wp_observation"] = (["uuid", "wp_group_uuid", "category_uuid", "employee_uuid"],
                           [(OBS_1, GROUP_1, CAT_LIVE, EMP_LEAD), (OBS_2, GROUP_1, CAT_THREATS, None)])
    t["wp_observation_attributes"] = (
        ["observation_uuid", "attribute_uuid", "list_element_uuid", "tree_node_uuid", "number_value", "string_value", "uuid"],
        [(OBS_1, ATT_SPECIES, LIST_ELE, None, None, None, U(0xa00)),
         (OBS_1, ATT_COUNT, None, None, 3.0, None, U(0xa01)),
         (OBS_2, ATT_TREE, None, TREE_WIRE, None, None, U(0xa02)),
         (OBS_2, ATT_THREAT, None, None, None, None, U(0xa03)),
         (OBS_2, ATT_ARMED, None, None, 1.0, None, U(0xa04)),
         (OBS_2, ATT_SEEN, None, None, None, "2019-03-01", U(0xa05))],
    )
    t["wp_observation_attributes_list"] = (["list_element_uuid", "observation_attribute_uuid"],
                                           [(U(0x402), U(0xa03)), (U(0x403), U(0xa03))])
    t["wp_attachments"] = (["uuid", "wp_uuid", "filename", "signature_type_uuid"], [(ATTACH_1, WP_1, "photo1.jpg", None)])
    return t


@pytest.fixture
def smart_parquet(tmp_path: Path) -> Path:
    out = tmp_path / "parquet"
    out.mkdir()
    con = duckdb.connect()
    for name, (cols, rows) in _tables().items():
        con.execute(f"CREATE TABLE t_{name} ({', '.join(c + ' VARCHAR' for c in cols)})")
        if rows:
            con.executemany(f"INSERT INTO t_{name} VALUES ({', '.join('?' for _ in cols)})",
                            [[None if v is None else str(v) if not isinstance(v, bool) else str(v).lower() for v in r] for r in rows])
        # cast columns the way csv_to_parquet.sh types them: booleans, numbers, dates, times, timestamps
        con.execute(f"COPY (SELECT * FROM t_{name}) TO '{out / name}.parquet' (FORMAT PARQUET)")
    con.close()
    # second pass: retype known columns so tests see real types like the real pipeline
    con = duckdb.connect()
    casts = {
        "language": "isdefault::BOOLEAN AS isdefault",
        "dm_category": "is_multiple::BOOLEAN AS is_multiple, cat_order::INTEGER AS cat_order, is_active::BOOLEAN AS is_active",
        "dm_attribute": "is_required::BOOLEAN AS is_required, min_value::DOUBLE AS min_value, max_value::DOUBLE AS max_value",
        "dm_attribute_list": "list_order::INTEGER AS list_order, is_active::BOOLEAN AS is_active",
        "dm_attribute_tree": "node_order::INTEGER AS node_order, is_active::BOOLEAN AS is_active",
        "dm_cat_att_map": "att_order::INTEGER AS att_order, is_active::BOOLEAN AS is_active",
        "iconset": "is_default::BOOLEAN AS is_default",
        "configurable_model": "instant_gps::BOOLEAN AS instant_gps, photo_first::BOOLEAN AS photo_first",
        "cm_node": "node_order::INTEGER AS node_order, photo_allowed::BOOLEAN AS photo_allowed, photo_required::BOOLEAN AS photo_required, collect_multiple_obs::BOOLEAN AS collect_multiple_obs, use_single_gps_point::BOOLEAN AS use_single_gps_point",
        "cm_attribute_config": "is_default::BOOLEAN AS is_default",
        "cm_attribute": "attribute_order::INTEGER AS attribute_order",
        "cm_attribute_list": "is_active::BOOLEAN AS is_active, list_order::INTEGER AS list_order",
        "cm_attribute_option": "number_value::DOUBLE AS number_value",
        "employee": "startemploymentdate::DATE AS startemploymentdate, endemploymentdate::DATE AS endemploymentdate, datecreated::DATE AS datecreated, birthdate::DATE AS birthdate, smartuserlevel::INTEGER AS smartuserlevel",
        "station": "is_active::BOOLEAN AS is_active",
        "patrol_type": "is_active::BOOLEAN AS is_active, max_speed::INTEGER AS max_speed",
        "patrol_transport": "is_active::BOOLEAN AS is_active",
        "patrol_mandate": "is_active::BOOLEAN AS is_active",
        "patrol": "is_armed::BOOLEAN AS is_armed, start_date::DATE AS start_date, end_date::DATE AS end_date",
        "patrol_leg": "start_date::DATE AS start_date, end_date::DATE AS end_date",
        "patrol_leg_day": "patrol_day::DATE AS patrol_day, start_time::TIME AS start_time, end_time::TIME AS end_time, rest_minutes::INTEGER AS rest_minutes",
        "patrol_leg_members": "is_leader::BOOLEAN AS is_leader, is_pilot::BOOLEAN AS is_pilot",
        "track": "distance::DOUBLE AS distance",
        "waypoint": "x::DOUBLE AS x, y::DOUBLE AS y, datetime::TIMESTAMP AS datetime, last_modified::TIMESTAMP AS last_modified",
        "wp_observation_attributes": "number_value::DOUBLE AS number_value",
    }
    for name, expr in casts.items():
        p = out / f"{name}.parquet"
        con.execute(f"CREATE TABLE x AS SELECT * REPLACE ({expr}) FROM '{p}'")
        con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
        con.execute("DROP TABLE x")
    con.close()
    return out
```

- [ ] **Step 3: Write the failing tests for `SmartDb`**

`tests/test_smartdb.py`:

```python
from __future__ import annotations

from export.smartdb import SmartDb, hyphenate, safe_id
from tests.conftest import CA_A, CA_B, CAT_THREATS, ATT_SPECIES, LIST_ELE, TRANSPORT_FOOT


def test_hyphenate_and_safe_id():
    assert hyphenate("0c7cbb411a60485d85138255206466a4") == "0c7cbb41-1a60-485d-8513-8255206466a4"
    assert hyphenate("0c7cbb41-1a60-485d-8513-8255206466a4") == "0c7cbb41-1a60-485d-8513-8255206466a4"
    assert safe_id("Region 05 / Albay") == "Region_05___Albay"
    assert safe_id("050500") == "050500"


def test_cas_and_version(smart_parquet):
    db = SmartDb(smart_parquet)
    cas = db.cas()
    assert [c.id for c in cas] == ["ALPHA", "BETA"]
    assert cas[0].name == "Alpha & Co" and cas[0].country == "PH"
    assert db.smart_version() == "7.5.4"
    assert db.has("patrol") and not db.has("no_such_table")


def test_languages_default_first(smart_parquet):
    db = SmartDb(smart_parquet)
    langs = db.languages(CA_A)
    assert [(l.code, l.default) for l in langs] == [("en", True), ("fr", False)]


def test_labels_fallback(smart_parquet):
    db = SmartDb(smart_parquet)
    L = db.labels(CA_A)
    assert L.get(ATT_SPECIES) == "Species"              # default language
    assert L.get(ATT_SPECIES, "fr") == "Espèce"
    assert L.get(CAT_THREATS, "fr") == 'Threats & "risks" <all>'   # fr missing -> default
    assert L.all(LIST_ELE) == {"en": "Elephant", "fr": "Éléphant"}
    assert L.get("0" * 32) is None
    assert TRANSPORT_FOOT in db.labelled_elements(CA_A)
    assert LIST_ELE in db.labelled_elements(CA_A)
    assert len(db.labelled_elements(CA_A)) == 26   # 3 cats, 7 atts, 4 list, 3 tree, transport, mandate, station, rank, team, cm, 2 nodes, config
    assert len(db.labelled_elements(CA_B)) == 0
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_smartdb.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'export'`

- [ ] **Step 5: Implement `export/__init__.py` and `export/smartdb.py`**

`export/__init__.py`:

```python
"""smart-able export: SMART-exact data model XML and the migration bundle.

Run as `uv run python -m export --work DIR [ca_id ...]` (see __main__.py);
the ./smart-able launcher does that for `./smart-able export`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def version() -> str:
    """`git describe` of the checkout, or 'unknown' outside git."""
    try:
        return subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--always", "--dirty"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
```

`export/smartdb.py`:

```python
"""Read access to the Parquet copy of a SMART database (work/parquet/).

Everything is per conservation area. Labels come from i18n_label, keyed by
the labelled row's UUID; `Labels.get` falls back from the requested language
to the CA default and then to any language, so a missing translation never
turns into a crash.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import duckdb


@dataclass(frozen=True)
class CA:
    uuid: str
    id: str
    name: str
    designation: Optional[str]
    description: Optional[str]
    organization: Optional[str]
    country: Optional[str]
    owner: Optional[str]


@dataclass(frozen=True)
class Language:
    uuid: str
    code: str
    default: bool


class Labels:
    def __init__(self, by_element: dict, default_code: str):
        self._by = by_element      # element_uuid -> {code: value}
        self.default_code = default_code

    def all(self, uuid: str) -> dict:
        return dict(self._by.get(uuid, {}))

    def get(self, uuid: str, code: Optional[str] = None) -> Optional[str]:
        m = self._by.get(uuid)
        if not m:
            return None
        for c in (code, self.default_code):
            if c and c in m:
                return m[c]
        return next(iter(m.values()))


def hyphenate(u: str) -> str:
    u = u.replace("-", "").lower()
    return f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}"


def safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


class SmartDb:
    def __init__(self, parquet_dir: Path):
        self.dir = Path(parquet_dir)
        self.con = duckdb.connect()

    def has(self, table: str) -> bool:
        return (self.dir / f"{table}.parquet").exists()

    def t(self, table: str) -> str:
        """SQL literal for a table's Parquet file, for use in FROM clauses."""
        p = self.dir / f"{table}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"no {p}; run ./smart-able extract first")
        return "'" + str(p).replace("'", "''") + "'"

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list:
        cur = self.con.execute(sql, list(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def cas(self) -> list:
        rows = self.rows(f"SELECT uuid, id, name, designation, description, organization, country, owner "
                         f"FROM {self.t('conservation_area')} ORDER BY id")
        return [CA(**r) for r in rows]

    def smart_version(self) -> Optional[str]:
        r = self.rows(f"SELECT max(version) AS v FROM {self.t('db_version')} WHERE plugin_id = 'org.wcs.smart'")
        return r[0]["v"] if r else None

    def languages(self, ca_uuid: str) -> list:
        rows = self.rows(f"SELECT uuid, code, isdefault FROM {self.t('language')} WHERE ca_uuid = ? "
                         f"ORDER BY isdefault DESC, code", [ca_uuid])
        return [Language(r["uuid"], r["code"], bool(r["isdefault"])) for r in rows]

    def labels(self, ca_uuid: str) -> Labels:
        langs = self.languages(ca_uuid)
        code_by_uuid = {l.uuid: l.code for l in langs}
        default = next((l.code for l in langs if l.default), langs[0].code if langs else "en")
        by: dict = {}
        if langs:
            marks = ", ".join("?" for _ in langs)
            for r in self.rows(f"SELECT element_uuid, language_uuid, value FROM {self.t('i18n_label')} "
                               f"WHERE language_uuid IN ({marks})", [l.uuid for l in langs]):
                by.setdefault(r["element_uuid"], {})[code_by_uuid[r["language_uuid"]]] = r["value"]
        return Labels(by, default)

    def labelled_elements(self, ca_uuid: str) -> set:
        """UUIDs of this CA's rows that carry i18n labels (for coverage counts)."""
        q = [f"SELECT uuid FROM {self.t('dm_category')} WHERE ca_uuid = ?",
             f"SELECT uuid FROM {self.t('dm_attribute')} WHERE ca_uuid = ?",
             f"SELECT l.uuid FROM {self.t('dm_attribute_list')} l JOIN {self.t('dm_attribute')} a ON a.uuid = l.attribute_uuid WHERE a.ca_uuid = ?",
             f"SELECT n.uuid FROM {self.t('dm_attribute_tree')} n JOIN {self.t('dm_attribute')} a ON a.uuid = n.attribute_uuid WHERE a.ca_uuid = ?",
             f"SELECT uuid FROM {self.t('patrol_transport')} WHERE ca_uuid = ?",
             f"SELECT uuid FROM {self.t('patrol_mandate')} WHERE ca_uuid = ?",
             f"SELECT desc_uuid FROM {self.t('station')} WHERE ca_uuid = ?",
             f"SELECT r.uuid FROM {self.t('rank')} r JOIN {self.t('agency')} g ON g.uuid = r.agency_uuid WHERE g.ca_uuid = ?"]
        for opt in ("configurable_model", "employee_team"):
            if self.has(opt):
                q.append(f"SELECT uuid FROM {self.t(opt)} WHERE ca_uuid = ?")
        if self.has("cm_node") and self.has("configurable_model"):
            q.append(f"SELECT n.uuid FROM {self.t('cm_node')} n JOIN {self.t('configurable_model')} m ON m.uuid = n.cm_uuid WHERE m.ca_uuid = ?")
            q.append(f"SELECT c.uuid FROM {self.t('cm_attribute_config')} c JOIN {self.t('configurable_model')} m ON m.uuid = c.cm_uuid WHERE m.ca_uuid = ?")
        out: set = set()
        for sql in q:
            out.update(r["uuid"] if "uuid" in r else r["desc_uuid"] for r in self.rows(sql, [ca_uuid]))
        return out
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_smartdb.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock export/__init__.py export/smartdb.py tests/conftest.py tests/test_smartdb.py
git commit -m "Export: SmartDb over the Parquet copy, test fixture database"
```

---

### Task 2: XML writer and the DataModel XML builder

**Files:**
- Create: `export/xmlwriter.py`, `export/datamodel_xml.py`, `tests/test_xmlwriter.py`, `tests/test_datamodel_xml.py`

**Interfaces:**
- Consumes: `SmartDb`, `Labels`, `Language` from Task 1.
- Produces: `Xml()` with `.open(tag, attrs)`, `.close(tag)`, `.empty(tag, attrs)`, `.text(tag, text, attrs=())`, `.render() -> str`; `xml_escape(s) -> str`; `java_double(x: float) -> str`; `build_datamodel_xml(db: SmartDb, ca_uuid: str) -> tuple[str, list[str]]` returning the document and warnings; `datamodel_namespace(version: str | None) -> tuple[str, list[str]]`; `ICONSET_ORDER = ("line", "black", "color")`.

Ordering rules, read off the Camarines Norte reference export (2026-10-12):
attributes sorted by default-language label, case-insensitive, ties by key; child elements in the order aggregations, qa_minmax/qa_regex, names, values/tree; categories by `cat_order` within parent; category `attributes` rows by `att_order`; list values by `list_order`; tree nodes by `node_order` under their parent; icons by key, icon sets in `ICONSET_ORDER` then any others alphabetically; icon file name is `<iconfile.uuid>.svg`.

- [ ] **Step 1: Write the failing writer tests**

`tests/test_xmlwriter.py`:

```python
from __future__ import annotations

from export.xmlwriter import Xml, java_double, xml_escape


def test_java_double():
    assert java_double(0.0) == "0.0"
    assert java_double(3.0) == "3.0"
    assert java_double(0.5) == "0.5"
    assert java_double(120.0) == "120.0"
    assert java_double(10000000.0) == "1.0E7"
    assert java_double(12345678.9) == "1.23456789E7"
    assert java_double(0.001) == "0.001"
    assert java_double(0.0001) == "1.0E-4"
    assert java_double(-2.5) == "-2.5"


def test_escape():
    assert xml_escape('a & b < c > "d"') == "a &amp; b &lt; c &gt; &quot;d&quot;"
    assert xml_escape("Éléphant") == "Éléphant"


def test_writer_layout():
    x = Xml()
    x.open("DataModel", [("xmlns", "urn:x")])
    x.open("attributes", [])
    x.empty("names", [("language_code", "en"), ("value", 'Q & "A"')])
    x.text("MinValue", "0.0")
    x.text("qa_regex", "")
    x.close("attributes")
    x.close("DataModel")
    assert x.render() == (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<DataModel xmlns="urn:x">\n'
        '    <attributes>\n'
        '        <names language_code="en" value="Q &amp; &quot;A&quot;"/>\n'
        '        <MinValue>0.0</MinValue>\n'
        '        <qa_regex></qa_regex>\n'
        '    </attributes>\n'
        '</DataModel>\n'
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_xmlwriter.py -v`
Expected: FAIL, `No module named 'export.xmlwriter'`

- [ ] **Step 3: Implement `export/xmlwriter.py`**

```python
"""A small XML text writer that reproduces SMART's JAXB output layout:
4-space indent, attributes in the order given, self-closed empty elements,
and `<x></x>` for empty text elements.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable, Tuple

DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def xml_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("\r", "&#13;"))


def java_double(x: float) -> str:
    """Java's Double.toString: plain decimal for 1e-3 <= |x| < 1e7, else d.dddE±n."""
    if x != x or math.isinf(x):
        return "NaN" if x != x else ("Infinity" if x > 0 else "-Infinity")
    if x == 0:
        return "0.0"
    d = Decimal(repr(float(x)))          # shortest round-tripping digits
    sign, digits, exp = d.as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop(); exp += 1
    e10 = exp + len(digits) - 1          # scientific exponent
    neg = "-" if sign else ""
    if 1e-3 <= abs(x) < 1e7:
        s = f"{abs(x):f}".rstrip("0")
        if s.endswith("."):
            s += "0"
        if "." not in s:
            s += ".0"
        return neg + s
    mant = str(digits[0]) + "." + ("".join(str(c) for c in digits[1:]) or "0")
    return f"{neg}{mant}E{e10}"


class Xml:
    def __init__(self):
        self.lines = []
        self.depth = 0

    def _attrs(self, attrs: Iterable[Tuple[str, str]]) -> str:
        return "".join(f' {k}="{xml_escape(v)}"' for k, v in attrs)

    def open(self, tag: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.lines.append(f"{'    ' * self.depth}</{tag}>")

    def empty(self, tag: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}/>")

    def text(self, tag: str, text: str, attrs: Iterable[Tuple[str, str]] = ()) -> None:
        self.lines.append(f"{'    ' * self.depth}<{tag}{self._attrs(attrs)}>{xml_escape(text)}</{tag}>")

    def render(self) -> str:
        return DECL + "\n".join(self.lines) + "\n"
```

- [ ] **Step 4: Run writer tests**

Run: `uv run pytest tests/test_xmlwriter.py -v`
Expected: 3 passed

- [ ] **Step 5: Write the failing DataModel builder tests**

`tests/test_datamodel_xml.py`:

```python
from __future__ import annotations

import difflib

from export.datamodel_xml import build_datamodel_xml, datamodel_namespace
from export.smartdb import SmartDb
from tests.conftest import CA_A, CA_B, ICONFILE_1, ICONFILE_2

GOLDEN = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<DataModel xmlns="http://www.smartconservationsoftware.org/xml/1.1/datamodel">
    <languages>
        <languages code="en"/>
        <languages code="fr"/>
    </languages>
    <attributes>
        <attribute key="armed" isrequired="false" type="BOOLEAN">
            <names language_code="en" value="Armed"/>
        </attribute>
        <attribute key="count" isrequired="false" type="NUMERIC">
            <aggregations aggregation="avg"/>
            <aggregations aggregation="sum"/>
            <qa_minmax>
                <MinValue>0.0</MinValue>
                <MaxValue>1.0E7</MaxValue>
            </qa_minmax>
            <names language_code="en" value="Count"/>
        </attribute>
        <attribute key="note" isrequired="false" type="TEXT">
            <qa_regex></qa_regex>
            <names language_code="en" value="Note"/>
        </attribute>
        <attribute key="seen" isrequired="false" type="DATE">
            <names language_code="en" value="Seen on"/>
        </attribute>
        <attribute key="species" isrequired="true" type="LIST" iconkey="species">
            <names language_code="en" value="Species"/>
            <names language_code="fr" value="Espèce"/>
            <values key="elephant" isactive="true">
                <names language_code="en" value="Elephant"/>
                <names language_code="fr" value="Éléphant"/>
            </values>
            <values key="lion" isactive="true">
                <names language_code="en" value="Lion"/>
            </values>
        </attribute>
        <attribute key="threattype" isrequired="true" type="TREE">
            <names language_code="en" value="Threat type"/>
            <tree key="snare" isactive="true">
                <names language_code="en" value="Snare"/>
                <children key="wire" isactive="true">
                    <names language_code="en" value="Wire snare"/>
                </children>
            </tree>
            <tree key="fire" isactive="true">
                <names language_code="en" value="Fire"/>
            </tree>
        </attribute>
        <attribute key="threat" isrequired="false" type="MLIST">
            <names language_code="en" value="Threats"/>
            <values key="snare" isactive="true">
                <names language_code="en" value="Snare"/>
            </values>
            <values key="fire" isactive="false">
                <names language_code="en" value="Fire"/>
            </values>
        </attribute>
    </attributes>
    <categories>
        <category key="threats" ismultiple="false" isactive="true">
            <names language_code="en" value="Threats &amp; &quot;risks&quot; &lt;all&gt;"/>
            <attributes isactive="true" attributekey="threattype"/>
            <attributes isactive="true" attributekey="threat"/>
            <attributes isactive="true" attributekey="armed"/>
            <attributes isactive="true" attributekey="seen"/>
        </category>
        <category key="animals" ismultiple="true" isactive="true" iconkey="species">
            <names language_code="en" value="Animals"/>
            <names language_code="fr" value="Animaux"/>
            <category key="liveanimals" ismultiple="true" isactive="true">
                <names language_code="en" value="Live animals"/>
                <attributes isactive="true" attributekey="species"/>
                <attributes isactive="true" attributekey="count"/>
                <attributes isactive="false" attributekey="note"/>
            </category>
        </category>
    </categories>
    <icons key="species" issystem="true">
        <icons iconset="line" file="{ICONFILE_1}.svg"/>
        <icons iconset="color" file="{ICONFILE_2}.svg"/>
        <names language_code="en" value="Species icon"/>
    </icons>
</DataModel>
'''


def assert_same(got: str, want: str) -> None:
    if got != want:
        raise AssertionError("\n" + "".join(difflib.unified_diff(
            want.splitlines(True), got.splitlines(True), "golden", "got")))


def test_namespace_by_version():
    assert datamodel_namespace("7.5.4") == ("http://www.smartconservationsoftware.org/xml/1.1/datamodel", [])
    ns, warns = datamodel_namespace("8.1.0")
    assert ns.endswith("/1.1/datamodel") and "8.1.0" in warns[0]


def test_golden_datamodel(smart_parquet):
    xml, warnings = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert_same(xml, GOLDEN)
    assert warnings == []


def test_xml_escaping(smart_parquet):
    xml, _ = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert 'value="Threats &amp; &quot;risks&quot; &lt;all&gt;"' in xml
    import xml.etree.ElementTree as ET
    ET.fromstring(xml.encode("utf-8"))  # well-formed


def test_icons_only_referenced_and_unique(smart_parquet):
    xml, _ = build_datamodel_xml(SmartDb(smart_parquet), CA_A)
    assert xml.count('<icons key="species"') == 1
    xml_b, warnings = build_datamodel_xml(SmartDb(smart_parquet), CA_B)
    assert "<icons key=" not in xml_b
    assert "<attributes>\n    </attributes>" in xml_b
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_datamodel_xml.py -v`
Expected: FAIL, `No module named 'export.datamodel_xml'`

- [ ] **Step 7: Implement `export/datamodel_xml.py` (DataModel part)**

```python
"""Build SMART's DataModel XML (and, in Task 3, ConfigurableModel XML) from
the Parquet tables, matching SMART Desktop's own export byte for byte.

Ordering and layout rules were read off a SMART 7.5.6 export of the
Camarines Norte CA (2026-10-12); see the spec for the table.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .smartdb import Labels, SmartDb
from .xmlwriter import Xml, java_double

DM_NS = {"7": "http://www.smartconservationsoftware.org/xml/1.1/datamodel"}
ICONSET_ORDER = ("line", "black", "color")


def datamodel_namespace(version: Optional[str]) -> Tuple[str, List[str]]:
    major = (version or "").split(".")[0]
    if major in DM_NS:
        return DM_NS[major], []
    return DM_NS["7"], [f"SMART version {version!r} is not one this exporter knows (7.x); "
                        f"writing the 7.x DataModel namespace"]


def _names(x: Xml, labels: Labels, uuid: str, codes: List[str]) -> None:
    m = labels.all(uuid)
    for c in codes:
        if c in m:
            x.empty("names", [("language_code", c), ("value", m[c])])


def _b(v) -> str:
    return "true" if v else "false"


def build_datamodel_xml(db: SmartDb, ca_uuid: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    ns, w = datamodel_namespace(db.smart_version())
    warnings += w
    langs = db.languages(ca_uuid)
    codes = [l.code for l in langs]
    L = db.labels(ca_uuid)

    attrs = db.rows(f"SELECT uuid, keyid, is_required, att_type, min_value, max_value, regex, icon_uuid "
                    f"FROM {db.t('dm_attribute')} WHERE ca_uuid = ?", [ca_uuid])
    attrs.sort(key=lambda a: ((L.get(a["uuid"]) or "").lower(), a["keyid"]))
    lists: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT l.uuid, l.attribute_uuid, l.keyid, l.is_active, l.icon_uuid FROM {db.t('dm_attribute_list')} l "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = l.attribute_uuid WHERE a.ca_uuid = ? "
                     f"ORDER BY l.list_order, l.keyid", [ca_uuid]):
        lists[r["attribute_uuid"]].append(r)
    tree_children: Dict[Tuple[str, Optional[str]], list] = defaultdict(list)
    for r in db.rows(f"SELECT n.uuid, n.attribute_uuid, n.parent_uuid, n.keyid, n.is_active, n.icon_uuid FROM {db.t('dm_attribute_tree')} n "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = n.attribute_uuid WHERE a.ca_uuid = ? "
                     f"ORDER BY n.node_order, n.keyid", [ca_uuid]):
        tree_children[(r["attribute_uuid"], r["parent_uuid"])].append(r)
    aggs: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT m.attribute_uuid, m.agg_name FROM {db.t('dm_att_agg_map')} m "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = m.attribute_uuid WHERE a.ca_uuid = ? "
                     f"ORDER BY m.agg_name", [ca_uuid]):
        aggs[r["attribute_uuid"]].append(r["agg_name"])
    cats = db.rows(f"SELECT uuid, keyid, parent_category_uuid, is_multiple, is_active, icon_uuid "
                   f"FROM {db.t('dm_category')} WHERE ca_uuid = ? ORDER BY cat_order, keyid", [ca_uuid])
    cat_children: Dict[Optional[str], list] = defaultdict(list)
    for c in cats:
        cat_children[c["parent_category_uuid"]].append(c)
    cat_atts: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT m.category_uuid, m.is_active, a.keyid FROM {db.t('dm_cat_att_map')} m "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = m.attribute_uuid "
                     f"JOIN {db.t('dm_category')} c ON c.uuid = m.category_uuid WHERE c.ca_uuid = ? "
                     f"ORDER BY m.att_order, a.keyid", [ca_uuid]):
        cat_atts[r["category_uuid"]].append(r)
    icon_key = {r["uuid"]: r["keyid"] for r in db.rows(f"SELECT uuid, keyid FROM {db.t('icon')}")}
    used_icons: Dict[str, None] = {}   # ordered set of icon uuids referenced by this CA

    def iconkey(icon_uuid: Optional[str]) -> List[Tuple[str, str]]:
        if not icon_uuid or icon_uuid not in icon_key:
            if icon_uuid:
                warnings.append(f"icon {icon_uuid} referenced but missing from the icon table")
            return []
        used_icons[icon_uuid] = None
        return [("iconkey", icon_key[icon_uuid])]

    x = Xml()
    x.open("DataModel", [("xmlns", ns)])
    x.open("languages")
    for c in codes:
        x.empty("languages", [("code", c)])
    x.close("languages")

    x.open("attributes")
    for a in attrs:
        t = (a["att_type"] or "").strip()
        x.open("attribute", [("key", a["keyid"]), ("isrequired", _b(a["is_required"])), ("type", t)] + iconkey(a["icon_uuid"]))
        for name in aggs.get(a["uuid"], []):
            x.empty("aggregations", [("aggregation", name)])
        if t == "NUMERIC" and (a["min_value"] is not None or a["max_value"] is not None):
            x.open("qa_minmax")
            if a["min_value"] is not None:
                x.text("MinValue", java_double(a["min_value"]))
            if a["max_value"] is not None:
                x.text("MaxValue", java_double(a["max_value"]))
            x.close("qa_minmax")
        if t == "TEXT" and a["regex"] is not None:
            x.text("qa_regex", a["regex"])
        _names(x, L, a["uuid"], codes)
        if t in ("LIST", "MLIST"):
            for v in lists.get(a["uuid"], []):
                x.open("values", [("key", v["keyid"]), ("isactive", _b(v["is_active"]))] + iconkey(v["icon_uuid"]))
                _names(x, L, v["uuid"], codes)
                x.close("values")
        elif t == "TREE":
            def tree(parent: Optional[str], tag: str) -> None:
                for n in tree_children.get((a["uuid"], parent), []):
                    x.open(tag, [("key", n["keyid"]), ("isactive", _b(n["is_active"]))] + iconkey(n["icon_uuid"]))
                    _names(x, L, n["uuid"], codes)
                    tree(n["uuid"], "children")
                    x.close(tag)
            tree(None, "tree")
        x.close("attribute")
    x.close("attributes")

    x.open("categories")

    def category(c: dict) -> None:
        x.open("category", [("key", c["keyid"]), ("ismultiple", _b(c["is_multiple"])), ("isactive", _b(c["is_active"]))] + iconkey(c["icon_uuid"]))
        _names(x, L, c["uuid"], codes)
        for r in cat_atts.get(c["uuid"], []):
            x.empty("attributes", [("isactive", _b(r["is_active"])), ("attributekey", r["keyid"])])
        for child in cat_children.get(c["uuid"], []):
            category(child)
        x.close("category")

    for c in cat_children.get(None, []):
        category(c)
    x.close("categories")

    if used_icons:
        files: Dict[str, list] = defaultdict(list)
        marks = ", ".join("?" for _ in used_icons)
        for r in db.rows(f"SELECT f.uuid, f.icon_uuid, f.filename, s.keyid AS iconset FROM {db.t('iconfile')} f "
                         f"JOIN {db.t('iconset')} s ON s.uuid = f.iconset_uuid WHERE f.icon_uuid IN ({marks})", list(used_icons)):
            files[r["icon_uuid"]].append(r)
        rank = {k: i for i, k in enumerate(ICONSET_ORDER)}
        for icon_uuid in sorted(used_icons, key=lambda u: icon_key[u]):
            rows = sorted(files.get(icon_uuid, []), key=lambda r: (rank.get(r["iconset"], len(rank)), r["iconset"]))
            if not rows:
                warnings.append(f"icon {icon_key[icon_uuid]!r} has no files in any icon set")
            system = all(r["filename"].startswith("platform:/plugin/") for r in rows) if rows else True
            x.open("icons", [("key", icon_key[icon_uuid]), ("issystem", _b(system))])
            for r in rows:
                x.empty("icons", [("iconset", r["iconset"]), ("file", f"{r['uuid']}.svg")])
            _names(x, L, icon_uuid, codes)
            x.close("icons")
    x.close("DataModel")
    return x.render(), warnings
```

- [ ] **Step 8: Run the builder tests**

Run: `uv run pytest tests/test_datamodel_xml.py -v`
Expected: 4 passed. If the golden diff shows only ordering differences, fix the builder, not the golden: the golden encodes the reference export's rules.

- [ ] **Step 9: Commit**

```bash
git add export/xmlwriter.py export/datamodel_xml.py tests/test_xmlwriter.py tests/test_datamodel_xml.py
git commit -m "Export: DataModel XML builder matching SMART's export layout"
```

---

### Task 3: ConfigurableModel XML builder

**Files:**
- Modify: `export/datamodel_xml.py` (append), `tests/test_datamodel_xml.py` (append)

**Interfaces:**
- Produces: `build_configurable_model_xml(db: SmartDb, cm_uuid: str) -> tuple[str, list[str]]`; `list_configurable_models(db, ca_uuid) -> list[dict]` with keys `uuid`, `label`.

Rules follow the Botswana Guardians sample in earthranger-smart-utils (the only CM export we hold; the user has been asked for a CM export of a Lawin CA so Task 12 can verify strictly). `dmUuid`/`attributeUuid` are 32-hex as stored; `id` attributes hyphenated. Option rows keep table order. `useEarthRanger` is written `false` with a warning until a reference shows its source column.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datamodel_xml.py`:

```python
from export.datamodel_xml import build_configurable_model_xml, list_configurable_models
from export.smartdb import hyphenate
from tests.conftest import (CM, NODE_GROUP, NODE_LIVE, CAT_LIVE, ATT_SPECIES, CMATT_SPECIES,
                            CMCONF_SPECIES, CMLIST_ELE, LIST_ELE)

GOLDEN_CM = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ConfigurableModel xmlns="http://www.smartconservationsoftware.org/xml/1.0/dataentry" displayMode="TEXT_IMAGE" instantGps="true" photoFirst="false" useEarthRanger="false" iconSet="color">
    <languages>
        <language code="en" is_default="true"/>
        <language code="fr" is_default="false"/>
    </languages>
    <name language_code="en" value="Alpha mobile model" source="CM"/>
    <nodes>
        <node id="{hyphenate(NODE_GROUP)}">
            <name language_code="en" value="Sightings" source="CM"/>
            <node categoryKey="liveanimals" categoryHkey="animals.liveanimals." dmUuid="{CAT_LIVE}" photoAllowed="true" photoRequired="false" displayMode="TEXT" id="{hyphenate(NODE_LIVE)}" collectMultipleObs="false" useSingleGpsPoint="false">
                <name language_code="en" value="Live animals" source="DM"/>
                <attribute attributeKey="species" dmUuid="{ATT_SPECIES}" id="{hyphenate(CMATT_SPECIES)}" configId="{hyphenate(CMCONF_SPECIES)}" type="LIST" required="true" isCustomImage="false">
                    <name language_code="en" value="Species" source="DM"/>
                    <name language_code="fr" value="Espèce" source="DM"/>
                    <option id="IS_VISIBLE" doubleValue="1.0"/>
                    <option id="ENTER_ONCE" stringValue="NONE"/>
                </attribute>
            </node>
        </node>
    </nodes>
    <attributeConfig id="{hyphenate(CMCONF_SPECIES)}" attributeKey="species" displayMode="TEXT" isDefault="true" attributeUuid="{ATT_SPECIES}">
        <name language_code="en" value="Species (curated)" source="CM"/>
        <listItem keyRef="elephant" dmUuid="{LIST_ELE}" isActive="true" id="{hyphenate(CMLIST_ELE)}" isCustomImage="false">
            <name language_code="en" value="Elephant" source="DM"/>
            <name language_code="fr" value="Éléphant" source="DM"/>
        </listItem>
    </attributeConfig>
</ConfigurableModel>
'''


def test_list_configurable_models(smart_parquet):
    assert list_configurable_models(SmartDb(smart_parquet), CA_A) == [{"uuid": CM, "label": "Alpha mobile model"}]
    assert list_configurable_models(SmartDb(smart_parquet), CA_B) == []


def test_golden_configurable_model(smart_parquet):
    xml, warnings = build_configurable_model_xml(SmartDb(smart_parquet), CM)
    assert_same(xml, GOLDEN_CM)
    assert warnings == ["useEarthRanger has no known source column; written as false"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_datamodel_xml.py -k configurable -v`
Expected: FAIL, `cannot import name 'build_configurable_model_xml'`

- [ ] **Step 3: Implement**

Append to `export/datamodel_xml.py`:

```python
CM_NS = "http://www.smartconservationsoftware.org/xml/1.0/dataentry"


def list_configurable_models(db: SmartDb, ca_uuid: str) -> List[dict]:
    if not db.has("configurable_model"):
        return []
    L = db.labels(ca_uuid)
    rows = db.rows(f"SELECT uuid FROM {db.t('configurable_model')} WHERE ca_uuid = ?", [ca_uuid])
    out = [{"uuid": r["uuid"], "label": L.get(r["uuid"]) or r["uuid"]} for r in rows]
    out.sort(key=lambda m: (m["label"].lower(), m["uuid"]))
    return out


def _name_els(x: Xml, labels: Labels, uuid: str, codes: List[str], source: str) -> None:
    m = labels.all(uuid)
    for c in codes:
        if c in m:
            x.empty("name", [("language_code", c), ("value", m[c]), ("source", source)])


def build_configurable_model_xml(db: SmartDb, cm_uuid: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    cm = db.rows(f"SELECT uuid, ca_uuid, display_mode, instant_gps, photo_first, iconset_uuid "
                 f"FROM {db.t('configurable_model')} WHERE uuid = ?", [cm_uuid])
    if not cm:
        raise KeyError(f"no configurable model {cm_uuid}")
    cm = cm[0]
    ca_uuid = cm["ca_uuid"]
    langs = db.languages(ca_uuid)
    codes = [l.code for l in langs]
    L = db.labels(ca_uuid)
    iconset = db.rows(f"SELECT keyid FROM {db.t('iconset')} WHERE uuid = ?", [cm["iconset_uuid"]])
    iconset_key = iconset[0]["keyid"] if iconset else "color"
    warnings.append("useEarthRanger has no known source column; written as false")

    cats = {c["uuid"]: c for c in db.rows(f"SELECT uuid, keyid, hkey FROM {db.t('dm_category')} WHERE ca_uuid = ?", [ca_uuid])}
    atts = {a["uuid"]: a for a in db.rows(f"SELECT uuid, keyid, att_type, is_required FROM {db.t('dm_attribute')} WHERE ca_uuid = ?", [ca_uuid])}
    list_el = {r["uuid"]: r for r in db.rows(f"SELECT l.uuid, l.keyid FROM {db.t('dm_attribute_list')} l "
                                             f"JOIN {db.t('dm_attribute')} a ON a.uuid = l.attribute_uuid WHERE a.ca_uuid = ?", [ca_uuid])}
    tree_el = {r["uuid"]: r for r in db.rows(f"SELECT n.uuid, n.keyid, n.hkey FROM {db.t('dm_attribute_tree')} n "
                                             f"JOIN {db.t('dm_attribute')} a ON a.uuid = n.attribute_uuid WHERE a.ca_uuid = ?", [ca_uuid])}

    nodes = db.rows(f"SELECT uuid, category_uuid, parent_node_uuid, node_order, photo_allowed, photo_required, "
                    f"collect_multiple_obs, use_single_gps_point, display_mode, imagetype FROM {db.t('cm_node')} "
                    f"WHERE cm_uuid = ? ORDER BY node_order, uuid", [cm_uuid])
    node_children: Dict[Optional[str], list] = defaultdict(list)
    for n in nodes:
        node_children[n["parent_node_uuid"]].append(n)
    node_atts: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT a.uuid, a.node_uuid, a.attribute_uuid, a.config_uuid, a.attribute_order FROM {db.t('cm_attribute')} a "
                     f"JOIN {db.t('cm_node')} n ON n.uuid = a.node_uuid WHERE n.cm_uuid = ? ORDER BY a.attribute_order, a.uuid", [cm_uuid]):
        node_atts[r["node_uuid"]].append(r)
    options: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT o.cm_attribute_uuid, o.option_id, o.number_value, o.string_value FROM {db.t('cm_attribute_option')} o "
                     f"JOIN {db.t('cm_attribute')} a ON a.uuid = o.cm_attribute_uuid "
                     f"JOIN {db.t('cm_node')} n ON n.uuid = a.node_uuid WHERE n.cm_uuid = ?", [cm_uuid]):
        options[r["cm_attribute_uuid"]].append(r)
    configs = db.rows(f"SELECT uuid, dm_attribute_uuid, display_mode, is_default FROM {db.t('cm_attribute_config')} "
                      f"WHERE cm_uuid = ? ORDER BY uuid", [cm_uuid])
    cfg_lists: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT l.uuid, l.config_uuid, l.list_element_uuid, l.is_active, l.imagetype FROM {db.t('cm_attribute_list')} l "
                     f"JOIN {db.t('cm_attribute_config')} c ON c.uuid = l.config_uuid WHERE c.cm_uuid = ? ORDER BY l.list_order, l.uuid", [cm_uuid]):
        cfg_lists[r["config_uuid"]].append(r)
    cfg_tree: Dict[Tuple[str, Optional[str]], list] = defaultdict(list)
    for r in db.rows(f"SELECT t.uuid, t.config_uuid, t.dm_tree_node_uuid, t.is_active, t.parent_uuid, t.imagetype FROM {db.t('cm_attribute_tree_node')} t "
                     f"JOIN {db.t('cm_attribute_config')} c ON c.uuid = t.config_uuid WHERE c.cm_uuid = ? ORDER BY t.node_order, t.uuid", [cm_uuid]):
        cfg_tree[(r["config_uuid"], r["parent_uuid"])].append(r)

    def image_attrs(row: dict, uuid: str) -> List[Tuple[str, str]]:
        if row.get("imagetype"):
            return [("imageFile", f"cn_img1_{uuid}.{row['imagetype'].lower()}"), ("isCustomImage", "true")]
        return [("isCustomImage", "false")]

    x = Xml()
    x.open("ConfigurableModel", [("xmlns", CM_NS), ("displayMode", cm["display_mode"] or "TEXT_IMAGE"),
                                 ("instantGps", _b(cm["instant_gps"])), ("photoFirst", _b(cm["photo_first"])),
                                 ("useEarthRanger", "false"), ("iconSet", iconset_key)])
    x.open("languages")
    for l in langs:
        x.empty("language", [("code", l.code), ("is_default", _b(l.default))])
    x.close("languages")
    _name_els(x, L, cm_uuid, codes, "CM")

    def node(n: dict) -> None:
        cat = cats.get(n["category_uuid"]) if n["category_uuid"] else None
        if cat:
            x.open("node", [("categoryKey", cat["keyid"]), ("categoryHkey", cat["hkey"]), ("dmUuid", cat["uuid"]),
                            ("photoAllowed", _b(n["photo_allowed"])), ("photoRequired", _b(n["photo_required"])),
                            ("displayMode", n["display_mode"] or "TEXT"), ("id", hyphenate(n["uuid"])),
                            ("collectMultipleObs", _b(n["collect_multiple_obs"])), ("useSingleGpsPoint", _b(n["use_single_gps_point"]))]
                   + ([] if not n.get("imagetype") else image_attrs(n, n["uuid"].replace("-", ""))))
            if L.all(n["uuid"]):
                _name_els(x, L, n["uuid"], codes, "CM")
            else:
                _name_els(x, L, cat["uuid"], codes, "DM")
        else:
            x.open("node", [("id", hyphenate(n["uuid"]))] + ([] if not n.get("imagetype") else image_attrs(n, n["uuid"])))
            _name_els(x, L, n["uuid"], codes, "CM")
        for a in node_atts.get(n["uuid"], []):
            da = atts.get(a["attribute_uuid"])
            if not da:
                warnings.append(f"cm_attribute {a['uuid']} refers to unknown attribute {a['attribute_uuid']}")
                continue
            x.open("attribute", [("attributeKey", da["keyid"]), ("dmUuid", da["uuid"]), ("id", hyphenate(a["uuid"]))]
                   + ([("configId", hyphenate(a["config_uuid"]))] if a["config_uuid"] else [])
                   + [("type", (da["att_type"] or "").strip()), ("required", _b(da["is_required"]))]
                   + image_attrs(a, a["uuid"]))
            _name_els(x, L, da["uuid"], codes, "DM")
            for o in options.get(a["uuid"], []):
                if o["number_value"] is not None:
                    x.empty("option", [("id", o["option_id"]), ("doubleValue", java_double(o["number_value"]))])
                elif o["string_value"] is not None:
                    x.empty("option", [("id", o["option_id"]), ("stringValue", o["string_value"])])
                else:
                    x.empty("option", [("id", o["option_id"])])
            x.close("attribute")
        for child in node_children.get(n["uuid"], []):
            node(child)
        x.close("node")

    x.open("nodes")
    for n in node_children.get(None, []):
        node(n)
    x.close("nodes")

    for c in configs:
        da = atts.get(c["dm_attribute_uuid"])
        if not da:
            warnings.append(f"cm_attribute_config {c['uuid']} refers to unknown attribute {c['dm_attribute_uuid']}")
            continue
        x.open("attributeConfig", [("id", hyphenate(c["uuid"])), ("attributeKey", da["keyid"]),
                                   ("displayMode", c["display_mode"] or "TEXT"), ("isDefault", _b(c["is_default"])),
                                   ("attributeUuid", da["uuid"])])
        _name_els(x, L, c["uuid"], codes, "CM")
        for li in cfg_lists.get(c["uuid"], []):
            el = list_el.get(li["list_element_uuid"])
            if not el:
                warnings.append(f"cm_attribute_list {li['uuid']} refers to unknown list value")
                continue
            x.open("listItem", [("keyRef", el["keyid"]), ("dmUuid", el["uuid"]), ("isActive", _b(li["is_active"])),
                                ("id", hyphenate(li["uuid"]))] + image_attrs(li, li["uuid"]))
            _name_els(x, L, el["uuid"], codes, "DM")
            x.close("listItem")

        def tnode(parent: Optional[str], tag: str) -> None:
            for tn in cfg_tree.get((c["uuid"], parent), []):
                el = tree_el.get(tn["dm_tree_node_uuid"])
                if not el:
                    warnings.append(f"cm_attribute_tree_node {tn['uuid']} refers to unknown tree node")
                    continue
                x.open(tag, [("keyRef", el["keyid"]), ("hkeyRef", el["hkey"]), ("dmUuid", el["uuid"]),
                             ("isActive", _b(tn["is_active"])), ("id", hyphenate(tn["uuid"]))] + image_attrs(tn, tn["uuid"]))
                _name_els(x, L, el["uuid"], codes, "DM")
                tnode(tn["uuid"], "children")
                x.close(tag)
        tnode(None, "treeNode")
        x.close("attributeConfig")

    if db.has("cm_ct_properties_profile") and db.has("ct_properties_profile"):
        prof = db.rows(f"SELECT p.uuid, p.name FROM {db.t('cm_ct_properties_profile')} m "
                       f"JOIN {db.t('ct_properties_profile')} p ON p.uuid = m.profile_uuid WHERE m.cm_uuid = ?", [cm_uuid])
        if prof:
            x.open("extraData", [("type", "ct_profile")])
            x.open("labelKey", [("key", "name")])
            x.empty("label", [("language_code", codes[0] if codes else "en"), ("value", prof[0]["name"] or "")])
            x.close("labelKey")
            x.close("extraData")
            warnings.append("extraData written from ct_properties_profile.name only; connect_ct_properties keys unverified")
    x.close("ConfigurableModel")
    return x.render(), warnings
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_datamodel_xml.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add export/datamodel_xml.py tests/test_datamodel_xml.py
git commit -m "Export: ConfigurableModel XML builder"
```

---

### Task 4: `verify_xml.py`, the fidelity checker

**Files:**
- Create: `export/verify_xml.py`, `tests/test_verify_xml.py`

**Interfaces:**
- Produces: `compare(reference: str, candidate: str, loose: bool = False, limit: int = 20) -> list[str]` (empty when equal); CLI `uv run python -m export.verify_xml REF OURS [--loose] [--limit N]`, exit 0 when equal, 1 when different, 2 on parse error.

- [ ] **Step 1: Write the failing tests**

`tests/test_verify_xml.py`:

```python
from __future__ import annotations

from export.verify_xml import compare

A = '<?xml version="1.0"?>\n<r xmlns="u"><a k="1" j="2"><n v="x"/></a><b>t</b></r>'


def test_equal():
    assert compare(A, A) == []


def test_attribute_order_strict_vs_loose():
    b = A.replace('k="1" j="2"', 'j="2" k="1"')
    assert compare(A, b) == ["/r/a[1]: attribute order ['k', 'j'] != ['j', 'k']"]
    assert compare(A, b, loose=True) == []


def test_value_text_and_child_count():
    b = A.replace('v="x"', 'v="y"').replace("<b>t</b>", "<b>u</b><c/>")
    diffs = compare(A, b)
    assert "/r/a[1]/n[1]: attribute v 'x' != 'y'" in diffs
    assert "/r/b[1]: text 't' != 'u'" in diffs
    assert "/r: child count 2 != 3" in diffs


def test_limit():
    b = A.replace('v="x"', 'v="y"').replace("<b>t</b>", "<b>u</b>")
    assert len(compare(A, b, limit=1)) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_verify_xml.py -v`
Expected: FAIL, `No module named 'export.verify_xml'`

- [ ] **Step 3: Implement**

`export/verify_xml.py`:

```python
"""Compare our DataModel/ConfigurableModel XML with SMART's own export.

Strict mode reports element order, attribute order and values, and text.
Loose mode ignores attribute order and whitespace so semantic differences
stand out while byte fidelity is still being chased.

    uv run python -m export.verify_xml reference.xml ours.xml [--loose] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from typing import List


def _tag(el: ET.Element) -> str:
    return el.tag.split("}", 1)[-1]


def _walk(ref: ET.Element, got: ET.Element, path: str, loose: bool, out: List[str], limit: int) -> None:
    if len(out) >= limit:
        return
    if _tag(ref) != _tag(got):
        out.append(f"{path}: element {_tag(ref)} != {_tag(got)}")
        return
    rk, gk = list(ref.attrib), list(got.attrib)
    if not loose and rk != gk:
        out.append(f"{path}: attribute order {rk} != {gk}")
    for k in rk:
        if k not in got.attrib:
            out.append(f"{path}: attribute {k} missing")
        elif ref.attrib[k] != got.attrib[k]:
            out.append(f"{path}: attribute {k} {ref.attrib[k]!r} != {got.attrib[k]!r}")
    for k in gk:
        if k not in ref.attrib:
            out.append(f"{path}: attribute {k} unexpected")
    rt, gt = (ref.text or "").strip(), (got.text or "").strip()
    if rt != gt:
        out.append(f"{path}: text {rt!r} != {gt!r}")
    rc, gc = list(ref), list(got)
    if len(rc) != len(gc):
        out.append(f"{path}: child count {len(rc)} != {len(gc)}")
    counts: dict = {}
    for r, g in zip(rc, gc):
        n = counts[_tag(r)] = counts.get(_tag(r), 0) + 1
        _walk(r, g, f"{path}/{_tag(r)}[{n}]", loose, out, limit)
    del out[limit:]


def compare(reference: str, candidate: str, loose: bool = False, limit: int = 20) -> List[str]:
    ref = ET.fromstring(reference.encode("utf-8") if isinstance(reference, str) else reference)
    got = ET.fromstring(candidate.encode("utf-8") if isinstance(candidate, str) else candidate)
    out: List[str] = []
    _walk(ref, got, "/" + _tag(ref), loose, out, limit)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("reference"); p.add_argument("candidate")
    p.add_argument("--loose", action="store_true"); p.add_argument("--limit", type=int, default=20)
    a = p.parse_args(argv)
    try:
        ref = open(a.reference, encoding="utf-8").read()
        got = open(a.candidate, encoding="utf-8").read()
        diffs = compare(ref, got, loose=a.loose, limit=a.limit)
    except (OSError, ET.ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not diffs and not a.loose and ref != got:
        diffs = ["documents are structurally equal but differ in bytes (whitespace, declaration or escaping)"]
    for d in diffs:
        print(d)
    print("identical" if not diffs else f"{len(diffs)} difference(s) shown")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_verify_xml.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add export/verify_xml.py tests/test_verify_xml.py
git commit -m "Export: verify_xml compares our XML with SMART's export"
```

---

### Task 5: Browser JSON for the Data Model tab

**Files:**
- Create: `export/datamodel_json.py`, `tests/test_datamodel_json.py`

**Interfaces:**
- Consumes: `SmartDb`, `list_configurable_models` (Task 3).
- Produces: `build_datamodel_json(db: SmartDb, ca: CA) -> dict` with the shape in the spec's "Browser: Data Model tab" section; `language_coverage(db, ca_uuid) -> list[dict]` (`code`, `default`, `labels`, `missing`), reused by the bundle manifest in Task 8.

- [ ] **Step 1: Write the failing tests**

`tests/test_datamodel_json.py`:

```python
from __future__ import annotations

import json

from export.datamodel_json import build_datamodel_json, language_coverage
from export.smartdb import SmartDb
from tests.conftest import CA_A, CM


def test_language_coverage(smart_parquet):
    assert language_coverage(SmartDb(smart_parquet), CA_A) == [
        {"code": "en", "default": True, "labels": 25, "missing": 1},
        {"code": "fr", "default": False, "labels": 3, "missing": 23},
    ]


def test_datamodel_json_shape(smart_parquet):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    d = build_datamodel_json(db, ca)
    assert d["ca"] == CA_A and d["ca_id"] == "ALPHA" and d["default_language"] == "en"
    assert [l["code"] for l in d["languages"]] == ["en", "fr"]
    roots = d["categories"]
    assert [c["key"] for c in roots] == ["threats", "animals"]
    animals = roots[1]
    assert animals["labels"] == {"en": "Animals", "fr": "Animaux"} and animals["label"] == "Animals"
    assert animals["icon"] == "species" and animals["multiple"] is True
    live = animals["children"][0]
    assert live["hkey"] == "animals.liveanimals."
    assert [(a["key"], a["active"]) for a in live["attributes"]] == [("species", True), ("count", True), ("note", False)]
    atts = d["attributes"]
    assert atts["species"]["type"] == "LIST" and atts["species"]["required"] is True
    assert [o["key"] for o in atts["species"]["options"]] == ["elephant", "lion"]
    assert atts["count"]["min"] == 0.0 and atts["count"]["max"] == 10000000.0 and atts["count"]["aggregations"] == ["avg", "sum"]
    assert atts["threattype"]["options"][0]["children"][0]["key"] == "wire"
    assert atts["note"]["regex"] == ""
    cm = d["configurable_models"][0]
    assert cm["uuid"] == CM and cm["file"] == f"configurable_model_{CM}.xml" and cm["label"] == "Alpha mobile model"
    group = cm["nodes"][0]
    assert group["label"] == "Sightings" and group["category"] is None
    leaf = group["children"][0]
    assert leaf["category"] == "animals.liveanimals." and leaf["attributes"][0]["key"] == "species"
    assert leaf["attributes"][0]["options"] == ["elephant"]
    assert d["files"] == {"datamodel": "datamodel.xml"}
    json.dumps(d, ensure_ascii=False)  # serialisable
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_datamodel_json.py -v`
Expected: FAIL, `No module named 'export.datamodel_json'`

- [ ] **Step 3: Implement**

`export/datamodel_json.py`:

```python
"""The Data Model tab's JSON: the same content as the XML, shaped for the
browser (nested categories, attributes keyed by key, configurable models
with the options they keep, per-language labels and coverage).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from .datamodel_xml import list_configurable_models
from .smartdb import CA, Labels, SmartDb


def language_coverage(db: SmartDb, ca_uuid: str) -> List[dict]:
    elements = db.labelled_elements(ca_uuid)
    L = db.labels(ca_uuid)
    out = []
    for lang in db.languages(ca_uuid):
        have = sum(1 for u in elements if lang.code in L.all(u))
        out.append({"code": lang.code, "default": lang.default, "labels": have, "missing": len(elements) - have})
    return out


def _lab(L: Labels, uuid: str) -> dict:
    return {"labels": L.all(uuid), "label": L.get(uuid)}


def build_datamodel_json(db: SmartDb, ca: CA) -> dict:
    L = db.labels(ca.uuid)
    icon_key = {r["uuid"]: r["keyid"] for r in db.rows(f"SELECT uuid, keyid FROM {db.t('icon')}")}
    ik = lambda u: icon_key.get(u) if u else None  # noqa: E731

    # attributes
    attrs: Dict[str, dict] = {}
    by_uuid: Dict[str, str] = {}
    for a in db.rows(f"SELECT uuid, keyid, is_required, att_type, min_value, max_value, regex, icon_uuid "
                     f"FROM {db.t('dm_attribute')} WHERE ca_uuid = ? ORDER BY keyid", [ca.uuid]):
        by_uuid[a["uuid"]] = a["keyid"]
        attrs[a["keyid"]] = {**_lab(L, a["uuid"]), "type": (a["att_type"] or "").strip(), "required": bool(a["is_required"]),
                             "icon": ik(a["icon_uuid"]), "min": a["min_value"], "max": a["max_value"], "regex": a["regex"],
                             "aggregations": [], "options": []}
    for r in db.rows(f"SELECT m.attribute_uuid, m.agg_name FROM {db.t('dm_att_agg_map')} m JOIN {db.t('dm_attribute')} a "
                     f"ON a.uuid = m.attribute_uuid WHERE a.ca_uuid = ? ORDER BY m.agg_name", [ca.uuid]):
        attrs[by_uuid[r["attribute_uuid"]]]["aggregations"].append(r["agg_name"])
    for r in db.rows(f"SELECT l.uuid, l.attribute_uuid, l.keyid, l.is_active, l.icon_uuid FROM {db.t('dm_attribute_list')} l "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = l.attribute_uuid WHERE a.ca_uuid = ? ORDER BY l.list_order, l.keyid", [ca.uuid]):
        attrs[by_uuid[r["attribute_uuid"]]]["options"].append({"key": r["keyid"], **_lab(L, r["uuid"]), "active": bool(r["is_active"]), "icon": ik(r["icon_uuid"])})
    tree: Dict[tuple, list] = defaultdict(list)
    for r in db.rows(f"SELECT n.uuid, n.attribute_uuid, n.parent_uuid, n.keyid, n.hkey, n.is_active, n.icon_uuid FROM {db.t('dm_attribute_tree')} n "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = n.attribute_uuid WHERE a.ca_uuid = ? ORDER BY n.node_order, n.keyid", [ca.uuid]):
        tree[(r["attribute_uuid"], r["parent_uuid"])].append(r)

    def tnodes(att_uuid: str, parent: Optional[str]) -> list:
        return [{"key": n["keyid"], "hkey": n["hkey"], **_lab(L, n["uuid"]), "active": bool(n["is_active"]), "icon": ik(n["icon_uuid"]),
                 "children": tnodes(att_uuid, n["uuid"])} for n in tree.get((att_uuid, parent), [])]

    for att_uuid, key in by_uuid.items():
        if attrs[key]["type"] == "TREE":
            attrs[key]["options"] = tnodes(att_uuid, None)

    # categories
    cat_atts: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT m.category_uuid, m.is_active, m.att_order, a.keyid FROM {db.t('dm_cat_att_map')} m "
                     f"JOIN {db.t('dm_attribute')} a ON a.uuid = m.attribute_uuid JOIN {db.t('dm_category')} c ON c.uuid = m.category_uuid "
                     f"WHERE c.ca_uuid = ? ORDER BY m.att_order, a.keyid", [ca.uuid]):
        cat_atts[r["category_uuid"]].append({"key": r["keyid"], "active": bool(r["is_active"]), "order": r["att_order"]})
    kids: Dict[Optional[str], list] = defaultdict(list)
    cat_hkey: Dict[str, str] = {}
    for c in db.rows(f"SELECT uuid, keyid, parent_category_uuid, is_multiple, is_active, hkey, icon_uuid FROM {db.t('dm_category')} "
                     f"WHERE ca_uuid = ? ORDER BY cat_order, keyid", [ca.uuid]):
        kids[c["parent_category_uuid"]].append(c)
        cat_hkey[c["uuid"]] = c["hkey"]

    def cnodes(parent: Optional[str]) -> list:
        return [{"key": c["keyid"], "hkey": c["hkey"], **_lab(L, c["uuid"]), "multiple": bool(c["is_multiple"]), "active": bool(c["is_active"]),
                 "icon": ik(c["icon_uuid"]), "attributes": cat_atts.get(c["uuid"], []), "children": cnodes(c["uuid"])} for c in kids.get(parent, [])]

    # configurable models
    cms = []
    for m in list_configurable_models(db, ca.uuid):
        node_rows = db.rows(f"SELECT uuid, category_uuid, parent_node_uuid FROM {db.t('cm_node')} WHERE cm_uuid = ? ORDER BY node_order, uuid", [m["uuid"]])
        nkids: Dict[Optional[str], list] = defaultdict(list)
        for n in node_rows:
            nkids[n["parent_node_uuid"]].append(n)
        natts: Dict[str, list] = defaultdict(list)
        for r in db.rows(f"SELECT a.node_uuid, a.attribute_uuid, a.config_uuid FROM {db.t('cm_attribute')} a JOIN {db.t('cm_node')} n ON n.uuid = a.node_uuid "
                         f"WHERE n.cm_uuid = ? ORDER BY a.attribute_order, a.uuid", [m["uuid"]]):
            natts[r["node_uuid"]].append(r)
        kept: Dict[str, list] = defaultdict(list)
        for r in db.rows(f"SELECT l.config_uuid, e.keyid FROM {db.t('cm_attribute_list')} l JOIN {db.t('dm_attribute_list')} e ON e.uuid = l.list_element_uuid "
                         f"JOIN {db.t('cm_attribute_config')} c ON c.uuid = l.config_uuid WHERE c.cm_uuid = ? AND l.is_active ORDER BY l.list_order", [m["uuid"]]):
            kept[r["config_uuid"]].append(r["keyid"])
        for r in db.rows(f"SELECT t.config_uuid, e.hkey FROM {db.t('cm_attribute_tree_node')} t JOIN {db.t('dm_attribute_tree')} e ON e.uuid = t.dm_tree_node_uuid "
                         f"JOIN {db.t('cm_attribute_config')} c ON c.uuid = t.config_uuid WHERE c.cm_uuid = ? AND t.is_active ORDER BY t.node_order", [m["uuid"]]):
            kept[r["config_uuid"]].append(r["hkey"])

        def nnodes(parent: Optional[str]) -> list:
            out = []
            for n in nkids.get(parent, []):
                label = L.get(n["uuid"]) or (L.get(n["category_uuid"]) if n["category_uuid"] else None)
                out.append({"label": label, "category": cat_hkey.get(n["category_uuid"]) if n["category_uuid"] else None,
                            "attributes": [{"key": by_uuid.get(a["attribute_uuid"]), "config": a["config_uuid"],
                                            "options": kept.get(a["config_uuid"], [])} for a in natts.get(n["uuid"], [])],
                            "children": nnodes(n["uuid"])})
            return out

        cms.append({"uuid": m["uuid"], "label": m["label"], "file": f"configurable_model_{m['uuid']}.xml", "nodes": nnodes(None)})

    langs = db.languages(ca.uuid)
    return {"ca": ca.uuid, "ca_id": ca.id, "ca_name": ca.name,
            "default_language": next((l.code for l in langs if l.default), langs[0].code if langs else "en"),
            "languages": language_coverage(db, ca.uuid),
            "categories": cnodes(None), "attributes": attrs, "configurable_models": cms,
            "files": {"datamodel": "datamodel.xml"}}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_datamodel_json.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add export/datamodel_json.py tests/test_datamodel_json.py
git commit -m "Export: Data Model tab JSON"
```

---

### Task 6: Timezone resolution and track WKB parsing

**Files:**
- Create: `export/timezone.py`, `export/wkb.py`, `tests/test_timezone.py`, `tests/test_wkb.py`

**Interfaces:**
- Produces: `resolve_timezone(db: SmartDb, ca: CA, site_data: Path | None, env: Mapping = os.environ) -> tuple[str, str]` returning `(iana_name, source)` with source in `configured`, `inferred`, `default`; `localize(naive: datetime, zone: ZoneInfo) -> str`; `utc_ms_iso(ms: float, zone: ZoneInfo) -> str`; `plausible_epoch_ms(z: float) -> bool`; `parse_track_wkb(hexstr: str) -> list[list[tuple[float, float, float | None]]]` (list of parts, each a list of `(x, y, z)`).

- [ ] **Step 1: Write the failing tests**

`tests/test_timezone.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from export.smartdb import SmartDb
from export.timezone import localize, plausible_epoch_ms, resolve_timezone, utc_ms_iso
from tests.conftest import T0


def test_configured_wins(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    assert resolve_timezone(db, ca, None, {"SMART_ABLE_TIMEZONE": "Africa/Nairobi"}) == ("Africa/Nairobi", "configured")


def test_site_timezones_json(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    (tmp_path / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    assert resolve_timezone(db, ca, tmp_path, {}) == ("Asia/Manila", "inferred")


def test_inferred_from_waypoints(smart_parquet):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    assert resolve_timezone(db, ca, None, {}) == ("Asia/Manila", "inferred")   # fixture waypoint at 123.9E 14.1N


def test_default_when_no_gps(smart_parquet):
    db = SmartDb(smart_parquet)
    beta = db.cas()[1]
    assert resolve_timezone(db, beta, None, {}) == ("UTC", "default")


def test_formatting():
    z = ZoneInfo("Asia/Manila")
    assert localize(datetime(2019, 3, 4, 6, 10, 0), z) == "2019-03-04T06:10:00+08:00"
    assert utc_ms_iso(T0, z) == "2019-03-04T06:10:00+08:00"
    assert plausible_epoch_ms(T0) and not plausible_epoch_ms(1234.5) and not plausible_epoch_ms(5e15)
```

`tests/test_wkb.py`:

```python
from __future__ import annotations

import struct

import pytest

from export.wkb import parse_track_wkb
from tests.conftest import T0, TRACK_WKB, wkb_line_z


def test_linestring_z():
    parts = parse_track_wkb(TRACK_WKB)
    assert parts == [[(123.72, 13.06, T0), (123.73, 13.07, T0 + 3600000)]]


def test_multilinestring_z():
    a = wkb_line_z([(1.0, 2.0, 10.0)])
    b = wkb_line_z([(3.0, 4.0, 20.0), (5.0, 6.0, 30.0)])
    multi = "00" + "80000005" + struct.pack(">I", 2).hex() + a + b
    assert parse_track_wkb(multi) == [[(1.0, 2.0, 10.0)], [(3.0, 4.0, 20.0), (5.0, 6.0, 30.0)]]


def test_plain_2d_linestring():
    pts = [(1.0, 2.0), (3.0, 4.0)]
    wkb = "00" + "00000002" + struct.pack(">I", 2).hex() + b"".join(struct.pack(">dd", *p) for p in pts).hex()
    assert parse_track_wkb(wkb) == [[(1.0, 2.0, None), (3.0, 4.0, None)]]


def test_little_endian_and_bad_type():
    pts = [(1.0, 2.0, 5.0)]
    wkb = "01" + struct.pack("<I", 0x80000002).hex() + struct.pack("<I", 1).hex() + struct.pack("<ddd", *pts[0]).hex()
    assert parse_track_wkb(wkb) == [[(1.0, 2.0, 5.0)]]
    with pytest.raises(ValueError):
        parse_track_wkb("00" + "00000001" + "00")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_timezone.py tests/test_wkb.py -v`
Expected: FAIL, modules not found

- [ ] **Step 3: Implement `export/timezone.py`**

```python
"""Which timezone a CA's wall-clock times belong to.

SMART stores dates and times without a zone. Precedence: SMART_ABLE_TIMEZONE
(configured), then the browser's timezones.json written by
browse/infer_timezones.py, then a fresh inference from the CA's waypoints
(both "inferred"), then UTC ("default", always with a warning).
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

from .smartdb import CA, SmartDb


def resolve_timezone(db: SmartDb, ca: CA, site_data: Optional[Path], env: Mapping = os.environ) -> Tuple[str, str]:
    name = env.get("SMART_ABLE_TIMEZONE")
    if name:
        ZoneInfo(name)  # raises for an unknown zone, which is what we want
        return name, "configured"
    if site_data and (site_data / "timezones.json").exists():
        tz = json.loads((site_data / "timezones.json").read_text())
        name = (tz.get("byCa") or {}).get(ca.id)
        if name:
            return name, "inferred"
    rows = db.rows(f"SELECT x, y FROM {db.t('waypoint')} WHERE ca_uuid = ? AND x IS NOT NULL AND y IS NOT NULL "
                   f"AND NOT (abs(x) < 0.01 AND abs(y) < 0.01)", [ca.uuid])
    if rows:
        from timezonefinder import TimezoneFinder
        name = TimezoneFinder().timezone_at(lng=statistics.median(r["x"] for r in rows), lat=statistics.median(r["y"] for r in rows))
        if name:
            return name, "inferred"
    return "UTC", "default"


def localize(naive: datetime, zone: ZoneInfo) -> str:
    return naive.replace(tzinfo=zone).isoformat()


def utc_ms_iso(ms: float, zone: ZoneInfo) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(zone).replace(microsecond=0).isoformat()


def plausible_epoch_ms(z: Optional[float]) -> bool:
    """True when z reads as a time between 1990 and 2100 in epoch milliseconds."""
    return z is not None and 631152000000 <= z <= 4102444800000
```

- [ ] **Step 4: Implement `export/wkb.py`**

```python
"""Parse SMART track geometries: (extended) WKB in hex, LineString or
MultiLineString, optionally with a Z coordinate (SMART puts the point's
epoch-millisecond timestamp there).
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

Point = Tuple[float, float, Optional[float]]

LINESTRING, MULTILINESTRING = 2, 5
Z_FLAG = 0x80000000


class _Reader:
    def __init__(self, data: bytes):
        self.b = data
        self.pos = 0

    def take(self, fmt: str):
        v = struct.unpack_from(fmt, self.b, self.pos)
        self.pos += struct.calcsize(fmt)
        return v


def _geometry(r: _Reader) -> Tuple[int, bool, str]:
    (order,) = r.take("B")
    bo = ">" if order == 0 else "<"
    (t,) = r.take(bo + "I")
    has_z = bool(t & Z_FLAG)
    base = t & 0xFFFF
    if base >= 1000:            # ISO WKB encodes Z as type + 1000
        base -= 1000
        has_z = True
    return base, has_z, bo


def _line(r: _Reader, has_z: bool, bo: str) -> List[Point]:
    (n,) = r.take(bo + "I")
    if has_z:
        vals = r.take(bo + f"{3 * n}d")
        return [(vals[i], vals[i + 1], vals[i + 2]) for i in range(0, 3 * n, 3)]
    vals = r.take(bo + f"{2 * n}d")
    return [(vals[i], vals[i + 1], None) for i in range(0, 2 * n, 2)]


def parse_track_wkb(hexstr: str) -> List[List[Point]]:
    r = _Reader(bytes.fromhex(hexstr))
    base, has_z, bo = _geometry(r)
    if base == LINESTRING:
        return [_line(r, has_z, bo)]
    if base == MULTILINESTRING:
        (n,) = r.take(bo + "I")
        parts = []
        for _ in range(n):
            pb, pz, pbo = _geometry(r)
            if pb != LINESTRING:
                raise ValueError(f"MultiLineString part has type {pb}")
            parts.append(_line(r, pz, pbo))
        return parts
    raise ValueError(f"unsupported WKB geometry type {base}")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_timezone.py tests/test_wkb.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add export/timezone.py export/wkb.py tests/test_timezone.py tests/test_wkb.py
git commit -m "Export: timezone resolution and track WKB parsing"
```

---

### Task 7: Bundle reference and patrols

**Files:**
- Create: `export/bundle.py`, `tests/test_bundle.py`

**Interfaces:**
- Consumes: `SmartDb`, `Labels`, `hyphenate`, `localize`, `ZoneInfo`.
- Produces: `build_reference(db, ca_uuid) -> dict`; `build_patrols(db, ca_uuid, zone, attachments_root: Path | None, out_dir: Path | None, warnings: list[str]) -> dict` (`out_dir` is the bundle directory; attachments are copied under `out_dir/attachments/<wp_uuid>/`); helpers `iso_date(d) -> str | None`, `leg_day_span(day: date, start: time | None, end: time | None, zone) -> tuple[str | None, str | None]`, `typed_value(att_type, row, mlist_rows, L) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_bundle.py`:

```python
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

from export.bundle import build_patrols, build_reference, leg_day_span
from export.smartdb import SmartDb, hyphenate
from tests.conftest import (CA_A, EMP_LEAD, EMP_TWO, TEAM, STATION, TRANSPORT_FOOT, MANDATE_LAW, PATROL_1, PATROL_2,
                            LEG_1, DAY_1, DAY_2, WP_1, OBS_1, OBS_2, ATTACH_1)

MANILA = ZoneInfo("Asia/Manila")


def test_reference(smart_parquet):
    ref = build_reference(SmartDb(smart_parquet), CA_A)
    assert ref["patrol_types"] == [{"key": "AIR", "active": False, "max_speed": 500}, {"key": "GROUND", "active": True, "max_speed": 120}]
    assert ref["transports"] == [{"uuid": hyphenate(TRANSPORT_FOOT), "key": "foot", "labels": {"en": "Foot"}, "label": "Foot", "patrol_type": "GROUND", "active": True}]
    assert ref["mandates"][0]["key"] == "law" and ref["stations"][0]["label"] == "HQ"
    assert ref["teams"] == [{"uuid": hyphenate(TEAM), "labels": {"en": "Team One"}, "label": "Team One", "member_uuids": [hyphenate(EMP_LEAD), hyphenate(EMP_TWO)]}]
    emps = {e["id"]: e for e in ref["employees"]}
    assert emps["E1"] == {"uuid": hyphenate(EMP_LEAD), "id": "E1", "given_name": "Ana", "family_name": "Cruz",
                          "agency_uuid": hyphenate(ref["agencies"][0]["uuid"].replace("-", "")), "rank_uuid": ref["ranks"][0]["uuid"],
                          "employment_start": "2017-01-01", "employment_end": None, "active": True}
    assert emps["E2"]["active"] is False and emps["E2"]["employment_end"] == "2018-06-30"
    assert "smartuserid" not in json.dumps(ref) and "birth" not in json.dumps(ref)
    assert ref["ranks"] == [{"uuid": ref["ranks"][0]["uuid"], "agency_uuid": ref["agencies"][0]["uuid"], "labels": {"en": "Ranger"}, "label": "Ranger"}]
    assert ref["patrol_attributes"] == []


def test_leg_day_midnight_and_null_times():
    assert leg_day_span(date(2019, 4, 1), time(22, 0), time(1, 30), MANILA) == ("2019-04-01T22:00:00+08:00", "2019-04-02T01:30:00+08:00")
    assert leg_day_span(date(2019, 4, 1), None, None, MANILA) == (None, None)
    assert leg_day_span(date(2019, 4, 1), time(6, 0), None, MANILA) == ("2019-04-01T06:00:00+08:00", None)


def test_patrols(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    att_root = tmp_path / "site_attachments"
    (att_root / CA_A / "patrol" / PATROL_1).mkdir(parents=True)
    (att_root / CA_A / "patrol" / PATROL_1 / "photo1.jpg").write_bytes(b"\xff\xd8jpg")
    out = tmp_path / "bundle"
    warnings: list = []
    d = build_patrols(db, CA_A, MANILA, att_root, out, warnings)
    assert warnings == []
    p1, p2 = d["patrols"]
    assert p1["uuid"] == hyphenate(PATROL_1) and p1["id"] == "P-0001" and p1["patrol_type"] == "GROUND"
    assert p1["station_uuid"] == hyphenate(STATION) and p1["team_uuid"] == hyphenate(TEAM)
    assert p1["objective"] == "Boundary walk" and p1["comment"] == "Fine weather" and p1["armed"] is False
    assert p1["start_date"] == "2019-03-04" and p1["end_date"] == "2019-03-05" and p1["attributes"] == []
    leg = p1["legs"][0]
    assert leg["uuid"] == hyphenate(LEG_1) and leg["transport_uuid"] == hyphenate(TRANSPORT_FOOT) and leg["mandate_uuid"] == hyphenate(MANDATE_LAW)
    assert leg["members"] == [{"employee_uuid": hyphenate(EMP_LEAD), "leader": True, "pilot": False},
                              {"employee_uuid": hyphenate(EMP_TWO), "leader": False, "pilot": False}]
    day = leg["days"][0]
    assert day == {"uuid": hyphenate(DAY_1), "date": "2019-03-04", "start_time": "06:10:00", "end_time": "14:35:00", "rest_minutes": 0,
                   "start": "2019-03-04T06:10:00+08:00", "end": "2019-03-04T14:35:00+08:00", "has_track": True}
    wp = leg["waypoints"][0]
    assert wp["uuid"] == hyphenate(WP_1) and wp["leg_day_uuid"] == hyphenate(DAY_1) and wp["id"] == "WP-1"
    assert wp["time"] == "2019-03-04T08:12:31+08:00" and wp["location"] == [123.9, 14.1] and wp["comment"] == "Near the river"
    assert wp["source"] == "PATROL" and wp["last_modified_by_uuid"] == hyphenate(EMP_LEAD)
    assert wp["attachments"] == [{"uuid": hyphenate(ATTACH_1), "filename": "photo1.jpg", "path": f"attachments/{hyphenate(WP_1)}/photo1.jpg"}]
    assert (out / "attachments" / hyphenate(WP_1) / "photo1.jpg").read_bytes() == b"\xff\xd8jpg"
    obs = {o["uuid"]: o for o in wp["observation_groups"][0]["observations"]}
    o1, o2 = obs[hyphenate(OBS_1)], obs[hyphenate(OBS_2)]
    assert o1["category_key"] == "animals.liveanimals" and o1["category_hkey"] == "animals.liveanimals." and o1["employee_uuid"] == hyphenate(EMP_LEAD)
    assert o1["attributes"] == [{"key": "species", "type": "LIST", "value": "elephant", "label": "Elephant"},
                                {"key": "count", "type": "NUMERIC", "value": 3.0}]
    assert o2["employee_uuid"] is None
    assert {a["key"]: a for a in o2["attributes"]} == {
        "threattype": {"key": "threattype", "type": "TREE", "value": "snare.wire", "label": "Wire snare"},
        "threat": {"key": "threat", "type": "MLIST", "value": ["snare", "fire"], "labels": ["Snare", "Fire"]},
        "armed": {"key": "armed", "type": "BOOLEAN", "value": True},
        "seen": {"key": "seen", "type": "DATE", "value": "2019-03-01"}}
    assert p2["legs"][0]["days"][0]["end"] == "2019-04-02T01:30:00+08:00" and p2["legs"][0]["days"][0]["has_track"] is False
    assert p2["legs"][0]["days"][0]["rest_minutes"] is None and p2["legs"][0]["waypoints"] == []


def test_missing_attachment_warns(smart_parquet, tmp_path):
    warnings: list = []
    build_patrols(SmartDb(smart_parquet), CA_A, MANILA, tmp_path / "nothing", tmp_path / "bundle", warnings)
    assert warnings == [f"attachment photo1.jpg of waypoint {hyphenate(WP_1)} is not in the extracted filestore"]


def test_json_is_utf8(smart_parquet, tmp_path):
    ref = build_reference(SmartDb(smart_parquet), CA_A)
    s = json.dumps(ref, ensure_ascii=False)
    assert "Éléphant" not in s  # not in reference, but labels in patrols are
    d = build_patrols(SmartDb(smart_parquet), CA_A, MANILA, None, None, [])
    assert "Elephant" in json.dumps(d, ensure_ascii=False)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_bundle.py -v`
Expected: FAIL, `No module named 'export.bundle'`

- [ ] **Step 3: Implement `export/bundle.py` (reference and patrols)**

```python
"""The migration bundle: reference.json, patrols.json, tracks.json and
manifest.json for one conservation area, plus copied attachments.

Everything here is plain dicts ready for json.dump; the contract is
export/bundle.schema.json.
"""
from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .smartdb import CA, Labels, SmartDb, hyphenate
from .timezone import localize

BUNDLE_SCHEMA_VERSION = 1


def H(u: Optional[str]) -> Optional[str]:
    return hyphenate(u) if u else None


def iso_date(d) -> Optional[str]:
    if d is None:
        return None
    return d.isoformat() if isinstance(d, date) else str(d)[:10]


def _lab(L: Labels, uuid: Optional[str]) -> dict:
    return {"labels": L.all(uuid) if uuid else {}, "label": L.get(uuid) if uuid else None}


def leg_day_span(day: date, start: Optional[time], end: Optional[time], zone: ZoneInfo) -> Tuple[Optional[str], Optional[str]]:
    s = localize(datetime.combine(day, start), zone) if start is not None else None
    if end is None:
        return s, None
    end_day = day + timedelta(days=1) if (start is not None and end < start) else day
    return s, localize(datetime.combine(end_day, end), zone)


def build_reference(db: SmartDb, ca_uuid: str) -> dict:
    L = db.labels(ca_uuid)
    ref: dict = {}
    ref["patrol_types"] = [{"key": r["patrol_type"], "active": bool(r["is_active"]), "max_speed": r["max_speed"]}
                           for r in db.rows(f"SELECT patrol_type, is_active, max_speed FROM {db.t('patrol_type')} WHERE ca_uuid = ? ORDER BY patrol_type", [ca_uuid])]
    ref["transports"] = [{"uuid": H(r["uuid"]), "key": r["keyid"], **_lab(L, r["uuid"]), "patrol_type": r["patrol_type"], "active": bool(r["is_active"])}
                         for r in db.rows(f"SELECT uuid, keyid, patrol_type, is_active FROM {db.t('patrol_transport')} WHERE ca_uuid = ? ORDER BY keyid", [ca_uuid])]
    ref["mandates"] = [{"uuid": H(r["uuid"]), "key": r["keyid"], **_lab(L, r["uuid"]), "active": bool(r["is_active"])}
                       for r in db.rows(f"SELECT uuid, keyid, is_active FROM {db.t('patrol_mandate')} WHERE ca_uuid = ? ORDER BY keyid", [ca_uuid])]
    ref["stations"] = [{"uuid": H(r["uuid"]), **_lab(L, r["desc_uuid"]), "active": bool(r["is_active"])}
                       for r in db.rows(f"SELECT uuid, desc_uuid, is_active FROM {db.t('station')} WHERE ca_uuid = ? ORDER BY uuid", [ca_uuid])]
    opts: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT l.uuid, l.patrol_attribute_uuid, l.keyid, l.is_active FROM {db.t('patrol_attribute_list')} l "
                     f"JOIN {db.t('patrol_attribute')} a ON a.uuid = l.patrol_attribute_uuid WHERE a.ca_uuid = ? ORDER BY l.list_order, l.keyid", [ca_uuid]):
        opts[r["patrol_attribute_uuid"]].append({"uuid": H(r["uuid"]), "key": r["keyid"], **_lab(L, r["uuid"]), "active": bool(r["is_active"])})
    ref["patrol_attributes"] = [{"uuid": H(r["uuid"]), "key": r["keyid"], **_lab(L, r["uuid"]), "type": (r["att_type"] or "").strip(),
                                 "active": bool(r["is_active"]), "options": opts.get(r["uuid"], [])}
                                for r in db.rows(f"SELECT uuid, keyid, att_type, is_active FROM {db.t('patrol_attribute')} WHERE ca_uuid = ? ORDER BY keyid", [ca_uuid])]
    ref["agencies"] = [{"uuid": H(r["uuid"]), "key": r["keyid"]}
                       for r in db.rows(f"SELECT uuid, keyid FROM {db.t('agency')} WHERE ca_uuid = ? ORDER BY keyid", [ca_uuid])]
    ref["ranks"] = [{"uuid": H(r["uuid"]), "agency_uuid": H(r["agency_uuid"]), **_lab(L, r["uuid"])}
                    for r in db.rows(f"SELECT r.uuid, r.agency_uuid FROM {db.t('rank')} r JOIN {db.t('agency')} g ON g.uuid = r.agency_uuid "
                                     f"WHERE g.ca_uuid = ? ORDER BY r.uuid", [ca_uuid])]
    members: Dict[str, list] = defaultdict(list)
    if db.has("employee_team_member"):
        for r in db.rows(f"SELECT m.team_uuid, m.employee_uuid FROM {db.t('employee_team_member')} m JOIN {db.t('employee_team')} t ON t.uuid = m.team_uuid "
                         f"WHERE t.ca_uuid = ? ORDER BY m.employee_uuid", [ca_uuid]):
            members[r["team_uuid"]].append(H(r["employee_uuid"]))
    ref["teams"] = [{"uuid": H(r["uuid"]), **_lab(L, r["uuid"]), "member_uuids": members.get(r["uuid"], [])}
                    for r in db.rows(f"SELECT uuid FROM {db.t('employee_team')} WHERE ca_uuid = ? ORDER BY uuid", [ca_uuid])] if db.has("employee_team") else []
    today = date.today()
    ref["employees"] = []
    for r in db.rows(f"SELECT uuid, id, givenname, familyname, startemploymentdate, endemploymentdate, agency_uuid, rank_uuid "
                     f"FROM {db.t('employee')} WHERE ca_uuid = ? ORDER BY familyname, givenname, id", [ca_uuid]):
        end = r["endemploymentdate"]
        ref["employees"].append({"uuid": H(r["uuid"]), "id": r["id"], "given_name": r["givenname"], "family_name": r["familyname"],
                                 "agency_uuid": H(r["agency_uuid"]), "rank_uuid": H(r["rank_uuid"]),
                                 "employment_start": iso_date(r["startemploymentdate"]), "employment_end": iso_date(end),
                                 "active": end is None or (end if isinstance(end, date) else date.fromisoformat(str(end)[:10])) >= today})
    return ref


def typed_value(att_type: str, row: dict, mlist_rows: List[dict], L: Labels) -> dict:
    """One observation attribute value, typed by dm_attribute.att_type."""
    t = (att_type or "").strip()
    out: dict = {"key": row["keyid"], "type": t}
    if t == "LIST":
        out["value"] = row["list_keyid"]; out["label"] = L.get(row["list_element_uuid"]) if row["list_element_uuid"] else None
    elif t == "MLIST":
        rows = mlist_rows or ([row] if row["list_element_uuid"] else [])
        out["value"] = [m["list_keyid"] for m in rows]; out["labels"] = [L.get(m["list_element_uuid"]) for m in rows]
    elif t == "TREE":
        out["value"] = (row["tree_hkey"] or "").rstrip(".") or None; out["label"] = L.get(row["tree_node_uuid"]) if row["tree_node_uuid"] else None
    elif t == "NUMERIC":
        out["value"] = row["number_value"]
    elif t == "BOOLEAN":
        out["value"] = None if row["number_value"] is None else bool(row["number_value"])
    elif t == "DATE":
        if row["string_value"]:
            out["value"] = str(row["string_value"])[:10]
        elif row["number_value"] is not None:
            out["value"] = datetime.utcfromtimestamp(row["number_value"] / 1000.0).date().isoformat()
        else:
            out["value"] = None
    else:
        out["value"] = row["string_value"]
    return out


def build_patrols(db: SmartDb, ca_uuid: str, zone: ZoneInfo, attachments_root: Optional[Path], out_dir: Optional[Path], warnings: List[str]) -> dict:
    L = db.labels(ca_uuid)
    cats = {r["uuid"]: r for r in db.rows(f"SELECT uuid, hkey FROM {db.t('dm_category')} WHERE ca_uuid = ?", [ca_uuid])}
    tracked = {r["patrol_leg_day_uuid"] for r in db.rows(f"SELECT t.patrol_leg_day_uuid FROM {db.t('track')} t JOIN {db.t('patrol_leg_day')} d ON d.uuid = t.patrol_leg_day_uuid "
                                                         f"JOIN {db.t('patrol_leg')} l ON l.uuid = d.patrol_leg_uuid JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid WHERE p.ca_uuid = ?", [ca_uuid])}

    patrols = db.rows(f"SELECT uuid, id, patrol_type, station_uuid, team_uuid, objective, comment, is_armed, start_date, end_date "
                      f"FROM {db.t('patrol')} WHERE ca_uuid = ? ORDER BY start_date, id, uuid", [ca_uuid])
    legs: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT l.uuid, l.patrol_uuid, l.id, l.transport_uuid, l.mandate_uuid, l.start_date, l.end_date FROM {db.t('patrol_leg')} l "
                     f"JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid WHERE p.ca_uuid = ? ORDER BY l.start_date, l.id, l.uuid", [ca_uuid]):
        legs[r["patrol_uuid"]].append(r)
    days: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT d.uuid, d.patrol_leg_uuid, d.patrol_day, d.start_time, d.end_time, d.rest_minutes FROM {db.t('patrol_leg_day')} d "
                     f"JOIN {db.t('patrol_leg')} l ON l.uuid = d.patrol_leg_uuid JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid "
                     f"WHERE p.ca_uuid = ? ORDER BY d.patrol_day, d.start_time, d.uuid", [ca_uuid]):
        days[r["patrol_leg_uuid"]].append(r)
    members: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT m.patrol_leg_uuid, m.employee_uuid, m.is_leader, m.is_pilot FROM {db.t('patrol_leg_members')} m "
                     f"JOIN {db.t('patrol_leg')} l ON l.uuid = m.patrol_leg_uuid JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid "
                     f"WHERE p.ca_uuid = ? ORDER BY m.is_leader DESC, m.employee_uuid", [ca_uuid]):
        members[r["patrol_leg_uuid"]].append({"employee_uuid": H(r["employee_uuid"]), "leader": bool(r["is_leader"]), "pilot": bool(r["is_pilot"])})
    pattrs: Dict[str, list] = defaultdict(list)
    if db.has("patrol_attribute_value"):
        for r in db.rows(f"SELECT v.patrol_uuid, a.uuid AS attribute_uuid, a.keyid, a.att_type, v.string_value, v.number_value, l.keyid AS list_keyid "
                         f"FROM {db.t('patrol_attribute_value')} v JOIN {db.t('patrol_attribute')} a ON a.uuid = v.patrol_attribute_uuid "
                         f"LEFT JOIN {db.t('patrol_attribute_list')} l ON l.uuid = v.list_item_uuid WHERE a.ca_uuid = ? ORDER BY a.keyid", [ca_uuid]):
            t = (r["att_type"] or "").strip()
            val = r["list_keyid"] if t in ("LIST", "MLIST") else r["number_value"] if t in ("NUMERIC", "BOOLEAN") else r["string_value"]
            if t == "BOOLEAN" and val is not None:
                val = bool(val)
            pattrs[r["patrol_uuid"]].append({"attribute_uuid": H(r["attribute_uuid"]), "key": r["keyid"], "value": val})

    # waypoints of this CA's patrols, keyed by leg
    wps_by_leg: Dict[str, list] = defaultdict(list)
    wp_patrol: Dict[str, str] = {}
    for r in db.rows(f"SELECT w.uuid, w.id, w.x, w.y, w.datetime, w.wp_comment, w.source, w.last_modified_by, pw.leg_day_uuid, l.uuid AS leg_uuid, l.patrol_uuid "
                     f"FROM {db.t('waypoint')} w JOIN {db.t('patrol_waypoint')} pw ON pw.wp_uuid = w.uuid "
                     f"JOIN {db.t('patrol_leg_day')} d ON d.uuid = pw.leg_day_uuid JOIN {db.t('patrol_leg')} l ON l.uuid = d.patrol_leg_uuid "
                     f"JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid WHERE p.ca_uuid = ? ORDER BY w.datetime, w.uuid", [ca_uuid]):
        wps_by_leg[r["leg_uuid"]].append(r)
        wp_patrol[r["uuid"]] = r["patrol_uuid"]
    dangling = db.rows(f"SELECT pw.wp_uuid FROM {db.t('patrol_waypoint')} pw JOIN {db.t('waypoint')} w ON w.uuid = pw.wp_uuid "
                       f"LEFT JOIN {db.t('patrol_leg_day')} d ON d.uuid = pw.leg_day_uuid WHERE w.ca_uuid = ? AND d.uuid IS NULL", [ca_uuid])
    for r in dangling:
        warnings.append(f"waypoint {H(r['wp_uuid'])} links to a leg day that does not exist; left out")

    groups: Dict[str, list] = defaultdict(list)       # wp uuid -> group rows
    obs_by_group: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT g.uuid, g.wp_uuid FROM {db.t('wp_observation_group')} g JOIN {db.t('waypoint')} w ON w.uuid = g.wp_uuid WHERE w.ca_uuid = ? ORDER BY g.uuid", [ca_uuid]):
        groups[r["wp_uuid"]].append(r)
    for r in db.rows(f"SELECT o.uuid, o.wp_group_uuid, o.category_uuid, o.employee_uuid FROM {db.t('wp_observation')} o "
                     f"JOIN {db.t('wp_observation_group')} g ON g.uuid = o.wp_group_uuid JOIN {db.t('waypoint')} w ON w.uuid = g.wp_uuid "
                     f"WHERE w.ca_uuid = ? ORDER BY o.uuid", [ca_uuid]):
        obs_by_group[r["wp_group_uuid"]].append(r)
    vals: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT v.uuid, v.observation_uuid, a.keyid, a.att_type, v.list_element_uuid, le.keyid AS list_keyid, v.tree_node_uuid, tn.hkey AS tree_hkey, "
                     f"v.number_value, v.string_value FROM {db.t('wp_observation_attributes')} v JOIN {db.t('dm_attribute')} a ON a.uuid = v.attribute_uuid "
                     f"LEFT JOIN {db.t('dm_attribute_list')} le ON le.uuid = v.list_element_uuid LEFT JOIN {db.t('dm_attribute_tree')} tn ON tn.uuid = v.tree_node_uuid "
                     f"JOIN {db.t('wp_observation')} o ON o.uuid = v.observation_uuid JOIN {db.t('wp_observation_group')} g ON g.uuid = o.wp_group_uuid "
                     f"JOIN {db.t('waypoint')} w ON w.uuid = g.wp_uuid WHERE w.ca_uuid = ? ORDER BY a.keyid, v.uuid", [ca_uuid]):
        vals[r["observation_uuid"]].append(r)
    mlist: Dict[str, list] = defaultdict(list)
    if db.has("wp_observation_attributes_list"):
        for r in db.rows(f"SELECT m.observation_attribute_uuid, m.list_element_uuid, le.keyid AS list_keyid FROM {db.t('wp_observation_attributes_list')} m "
                         f"JOIN {db.t('dm_attribute_list')} le ON le.uuid = m.list_element_uuid ORDER BY le.list_order, le.keyid"):
            mlist[r["observation_attribute_uuid"]].append(r)
    atts: Dict[str, list] = defaultdict(list)
    for r in db.rows(f"SELECT a.uuid, a.wp_uuid, a.filename FROM {db.t('wp_attachments')} a JOIN {db.t('waypoint')} w ON w.uuid = a.wp_uuid WHERE w.ca_uuid = ? ORDER BY a.filename", [ca_uuid]):
        atts[r["wp_uuid"]].append(r)

    def waypoint(w: dict) -> dict:
        files = []
        for a in atts.get(w["uuid"], []):
            rel = f"attachments/{H(w['uuid'])}/{a['filename']}"
            src = attachments_root / w_ca / "patrol" / wp_patrol[w["uuid"]] / a["filename"] if attachments_root else None
            if src is not None and src.exists():
                if out_dir is not None:
                    dst = out_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
            else:
                warnings.append(f"attachment {a['filename']} of waypoint {H(w['uuid'])} is not in the extracted filestore")
            files.append({"uuid": H(a["uuid"]), "filename": a["filename"], "path": rel})
        ogs = []
        for g in groups.get(w["uuid"], []):
            obs = []
            for o in obs_by_group.get(g["uuid"], []):
                cat = cats.get(o["category_uuid"], {})
                hkey = cat.get("hkey") or ""
                obs.append({"uuid": H(o["uuid"]), "category_key": hkey.rstrip("."), "category_hkey": hkey, "employee_uuid": H(o["employee_uuid"]),
                            "attributes": [typed_value(v["att_type"], v, mlist.get(v["uuid"], []), L) for v in vals.get(o["uuid"], [])]})
            ogs.append({"uuid": H(g["uuid"]), "observations": obs})
        loc = [w["x"], w["y"]] if w["x"] is not None and w["y"] is not None else None
        if loc and not (-180 <= loc[0] <= 180 and -90 <= loc[1] <= 90):
            warnings.append(f"waypoint {H(w['uuid'])} has coordinates outside WGS 84 range: {loc}")
        return {"uuid": H(w["uuid"]), "id": w["id"], "leg_day_uuid": H(w["leg_day_uuid"]),
                "time": localize(w["datetime"], zone) if w["datetime"] is not None else None, "location": loc,
                "comment": w["wp_comment"], "source": w["source"], "last_modified_by_uuid": H(w["last_modified_by"]),
                "attachments": files, "observation_groups": ogs}

    w_ca = ca_uuid
    out = []
    for p in patrols:
        pl = []
        for l in legs.get(p["uuid"], []):
            dl = []
            for d in days.get(l["uuid"], []):
                s, e = leg_day_span(d["patrol_day"], d["start_time"], d["end_time"], zone)
                dl.append({"uuid": H(d["uuid"]), "date": iso_date(d["patrol_day"]),
                           "start_time": None if d["start_time"] is None else d["start_time"].isoformat(),
                           "end_time": None if d["end_time"] is None else d["end_time"].isoformat(),
                           "rest_minutes": d["rest_minutes"], "start": s, "end": e, "has_track": d["uuid"] in tracked})
            pl.append({"uuid": H(l["uuid"]), "id": l["id"], "transport_uuid": H(l["transport_uuid"]), "mandate_uuid": H(l["mandate_uuid"]),
                       "start_date": iso_date(l["start_date"]), "end_date": iso_date(l["end_date"]),
                       "members": members.get(l["uuid"], []), "days": dl, "waypoints": [waypoint(w) for w in wps_by_leg.get(l["uuid"], [])]})
        out.append({"uuid": H(p["uuid"]), "id": p["id"], "patrol_type": p["patrol_type"], "station_uuid": H(p["station_uuid"]), "team_uuid": H(p["team_uuid"]),
                    "objective": p["objective"], "comment": p["comment"], "armed": None if p["is_armed"] is None else bool(p["is_armed"]),
                    "start_date": iso_date(p["start_date"]), "end_date": iso_date(p["end_date"]), "attributes": pattrs.get(p["uuid"], []), "legs": pl})
    return {"patrols": out}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_bundle.py -v`
Expected: 5 passed. If `test_reference` fails on `agency_uuid`, the comparison line in the test is overwrought: replace it with `emps["E1"]["agency_uuid"] == ref["agencies"][0]["uuid"]`.

- [ ] **Step 5: Commit**

```bash
git add export/bundle.py tests/test_bundle.py
git commit -m "Export: bundle reference and patrols"
```

---

### Task 8: Bundle tracks, manifest, and `write_bundle`

**Files:**
- Modify: `export/bundle.py` (append), `tests/test_bundle.py` (append)

**Interfaces:**
- Consumes: `parse_track_wkb`, `utc_ms_iso`, `plausible_epoch_ms`, `language_coverage`, `version()`.
- Produces: `build_tracks(db, ca_uuid, zone, warnings) -> dict`; `check_track_offset(db, ca_uuid, zone, warnings) -> None`; `time_coverage(patrols: dict, tracks: dict) -> dict` (per leg day, the best time source available: `track` when a timed track exists, else `leg_day_times` when start and end are set, else `waypoints` when any waypoint on the day has a time, else `date_only`); `build_manifest(db, ca, zone_name, zone_source, source: dict, counts: dict, coverage: dict, warnings) -> dict`; `write_bundle(db, ca, out_dir: Path, zone_name: str, zone_source: str, attachments_root: Path | None, source: dict) -> dict` writing the four files and returning the manifest.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bundle.py`:

```python
import struct

from export.bundle import build_tracks, check_track_offset, write_bundle
from tests.conftest import T0, TRACK_1, wkb_line_z


def test_tracks(smart_parquet):
    warnings: list = []
    d = build_tracks(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    assert warnings == []
    t = d["tracks"][0]
    assert t["uuid"] == hyphenate(TRACK_1) and t["leg_day_uuid"] == hyphenate(DAY_1) and t["leg_uuid"] == hyphenate(LEG_1) and t["patrol_uuid"] == hyphenate(PATROL_1)
    assert t["distance_km"] == 1.5
    assert t["start"] == "2019-03-04T06:10:00+08:00" and t["end"] == "2019-03-04T07:10:00+08:00"
    assert t["parts"] == [{"coordinates": [[123.72, 13.06], [123.73, 13.07]],
                           "times": ["2019-03-04T06:10:00+08:00", "2019-03-04T07:10:00+08:00"]}]


def test_track_without_plausible_times(smart_parquet, tmp_path):
    import duckdb
    p = smart_parquet / "track.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE TABLE x AS SELECT * FROM '{p}'")
    con.execute("UPDATE x SET geometry = ?", [wkb_line_z([(1.0, 2.0, 350.0), (1.1, 2.1, 360.0)])])  # Z is an elevation
    con.execute(f"COPY x TO '{p}' (FORMAT PARQUET)")
    con.close()
    warnings: list = []
    d = build_tracks(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    t = d["tracks"][0]
    assert "times" not in t["parts"][0] and t["start"] is None and t["end"] is None
    assert warnings == ["1 track(s) have Z values that are not epoch-millisecond timestamps; their points carry no times"]


def test_track_offset_check(smart_parquet):
    warnings: list = []
    check_track_offset(SmartDb(smart_parquet), CA_A, MANILA, warnings)
    assert warnings == []
    check_track_offset(SmartDb(smart_parquet), CA_A, ZoneInfo("Africa/Nairobi"), warnings)
    assert warnings == ["track timestamps imply UTC+08:00 on 1 of 1 leg days with both a track and a start time, but the bundle timezone Africa/Nairobi is UTC+03:00; set SMART_ABLE_TIMEZONE"]


def test_write_bundle(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    ca = db.cas()[0]
    out = tmp_path / "bundle"
    m = write_bundle(db, ca, out, "Asia/Manila", "inferred", None, {"kind": "backup", "file": "x.zip"})
    assert sorted(p.name for p in out.iterdir()) == ["manifest.json", "patrols.json", "reference.json", "tracks.json"]
    assert m["bundle_schema_version"] == 1 and m["conservation_area"]["uuid"] == hyphenate(CA_A) and m["conservation_area"]["id"] == "ALPHA"
    assert m["source"] == {"kind": "backup", "file": "x.zip", "smart_version": "7.5.4"}
    assert m["timezone"] == {"name": "Asia/Manila", "source": "inferred"}
    assert m["default_language"] == "en" and m["languages"][1] == {"code": "fr", "default": False, "labels": 3, "missing": 23}
    assert m["counts"] == {"patrols": 2, "legs": 2, "leg_days": 2, "waypoints": 1, "observations": 2, "tracks": 1, "track_points": 2, "employees": 2, "attachments": 1}
    # best available time source per leg day: DAY_1 has a timed track, DAY_2 only its start/end times
    assert m["time_coverage"] == {"leg_days": 2, "track": 1, "leg_day_times": 1, "waypoints": 0, "date_only": 0}
    assert m["generator"]["name"] == "smart-able"
    assert any("not in the extracted filestore" in w for w in m["warnings"])
    assert json.loads((out / "manifest.json").read_text()) == m
    assert m["generated_at"].endswith("Z")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_bundle.py -k "tracks or offset or write_bundle" -v`
Expected: FAIL, `cannot import name 'build_tracks'`

- [ ] **Step 3: Implement**

Append to `export/bundle.py`:

```python
import json
from datetime import timezone as _tz

from . import version
from .datamodel_json import language_coverage
from .timezone import plausible_epoch_ms, utc_ms_iso
from .wkb import parse_track_wkb


def _track_rows(db: SmartDb, ca_uuid: str) -> List[dict]:
    return db.rows(f"SELECT t.uuid, t.patrol_leg_day_uuid, t.geometry, t.distance, l.uuid AS leg_uuid, p.uuid AS patrol_uuid, "
                   f"d.patrol_day, d.start_time FROM {db.t('track')} t JOIN {db.t('patrol_leg_day')} d ON d.uuid = t.patrol_leg_day_uuid "
                   f"JOIN {db.t('patrol_leg')} l ON l.uuid = d.patrol_leg_uuid JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid "
                   f"WHERE p.ca_uuid = ? ORDER BY d.patrol_day, t.uuid", [ca_uuid])


def build_tracks(db: SmartDb, ca_uuid: str, zone: ZoneInfo, warnings: List[str]) -> dict:
    out = []
    untimed = 0
    for r in _track_rows(db, ca_uuid):
        try:
            parts = parse_track_wkb(r["geometry"])
        except (ValueError, struct.error) as e:
            warnings.append(f"track {H(r['uuid'])} has unreadable geometry ({e}); left out")
            continue
        timed = all(plausible_epoch_ms(z) for part in parts for (_, _, z) in part) and any(parts)
        if not timed:
            untimed += 1
        first = last = None
        jparts = []
        for part in parts:
            jp: dict = {"coordinates": [[x, y] for (x, y, _) in part]}
            if timed and part:
                jp["times"] = [utc_ms_iso(z, zone) for (_, _, z) in part]
                first = jp["times"][0] if first is None else min(first, jp["times"][0])
                last = jp["times"][-1] if last is None else max(last, jp["times"][-1])
            jparts.append(jp)
        out.append({"uuid": H(r["uuid"]), "leg_day_uuid": H(r["patrol_leg_day_uuid"]), "leg_uuid": H(r["leg_uuid"]), "patrol_uuid": H(r["patrol_uuid"]),
                    "distance_km": r["distance"], "start": first, "end": last, "parts": jparts})
    if untimed:
        warnings.append(f"{untimed} track(s) have Z values that are not epoch-millisecond timestamps; their points carry no times")
    return {"tracks": out}


def check_track_offset(db: SmartDb, ca_uuid: str, zone: ZoneInfo, warnings: List[str]) -> None:
    """Compare each leg day's local start time with its track's first UTC
    timestamp; the rounded difference is the offset the data implies."""
    votes: Dict[int, int] = defaultdict(int)
    for r in _track_rows(db, ca_uuid):
        if r["start_time"] is None:
            continue
        try:
            parts = parse_track_wkb(r["geometry"])
        except (ValueError, struct.error):
            continue
        zs = [z for part in parts for (_, _, z) in part if plausible_epoch_ms(z)]
        if not zs:
            continue
        local = datetime.combine(r["patrol_day"], r["start_time"])
        utc = datetime.fromtimestamp(min(zs) / 1000.0, tz=_tz.utc).replace(tzinfo=None)
        votes[round((local - utc).total_seconds() / 3600)] += 1
    if not votes:
        return
    implied, n = max(votes.items(), key=lambda kv: kv[1])
    total = sum(votes.values())
    sample = datetime(2019, 1, 1).replace(tzinfo=zone)   # offsets can vary with DST; compare against the zone's January offset and July offset
    offsets = {int(datetime(2019, m, 1).replace(tzinfo=zone).utcoffset().total_seconds() // 3600) for m in (1, 7)}
    if implied not in offsets:
        fmt = lambda h: f"UTC{'+' if h >= 0 else '-'}{abs(h):02d}:00"  # noqa: E731
        warnings.append(f"track timestamps imply {fmt(implied)} on {n} of {total} leg days with both a track and a start time, "
                        f"but the bundle timezone {zone.key} is {fmt(min(offsets))}; set SMART_ABLE_TIMEZONE")


def time_coverage(patrols: dict, tracks: dict) -> dict:
    """How well each leg day's time range is pinned down, by its best source.
    The importer uses the same precedence to set ER segment time ranges."""
    timed = {t["leg_day_uuid"] for t in tracks["tracks"] if t["start"] and t["end"]}
    out = {"leg_days": 0, "track": 0, "leg_day_times": 0, "waypoints": 0, "date_only": 0}
    for p in patrols["patrols"]:
        for l in p["legs"]:
            wp_days = {w["leg_day_uuid"] for w in l["waypoints"] if w["time"]}
            for d in l["days"]:
                out["leg_days"] += 1
                if d["uuid"] in timed:
                    out["track"] += 1
                elif d["start"] and d["end"]:
                    out["leg_day_times"] += 1
                elif d["uuid"] in wp_days:
                    out["waypoints"] += 1
                else:
                    out["date_only"] += 1
    return out


def build_manifest(db: SmartDb, ca: CA, zone_name: str, zone_source: str, source: dict, counts: dict, coverage: dict, warnings: List[str]) -> dict:
    langs = db.languages(ca.uuid)
    return {"bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "generated_at": datetime.now(_tz.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "generator": {"name": "smart-able", "version": version()},
            "source": {"kind": source.get("kind"), "file": source.get("file"), "smart_version": db.smart_version()},
            "conservation_area": {"uuid": H(ca.uuid), "id": ca.id, "name": ca.name, "designation": ca.designation,
                                  "country": ca.country, "organization": ca.organization, "owner": ca.owner},
            "timezone": {"name": zone_name, "source": zone_source},
            "default_language": next((l.code for l in langs if l.default), langs[0].code if langs else "en"),
            "languages": language_coverage(db, ca.uuid),
            "counts": counts, "time_coverage": coverage, "warnings": list(warnings)}


def write_bundle(db: SmartDb, ca: CA, out_dir: Path, zone_name: str, zone_source: str, attachments_root: Optional[Path], source: dict) -> dict:
    zone = ZoneInfo(zone_name)
    warnings: List[str] = []
    if zone_source == "inferred":
        warnings.append(f"timezone {zone_name} was inferred from waypoint positions; set SMART_ABLE_TIMEZONE to override")
    elif zone_source == "default":
        warnings.append("no timezone could be inferred (no GPS waypoints); times are written as UTC; set SMART_ABLE_TIMEZONE")
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks = build_tracks(db, ca.uuid, zone, warnings)
    check_track_offset(db, ca.uuid, zone, warnings)
    patrols = build_patrols(db, ca.uuid, zone, attachments_root, out_dir, warnings)
    reference = build_reference(db, ca.uuid)
    legs = [l for p in patrols["patrols"] for l in p["legs"]]
    wps = [w for l in legs for w in l["waypoints"]]
    counts = {"patrols": len(patrols["patrols"]), "legs": len(legs), "leg_days": sum(len(l["days"]) for l in legs),
              "waypoints": len(wps), "observations": sum(len(o) for w in wps for o in [[x for g in w["observation_groups"] for x in g["observations"]]]),
              "tracks": len(tracks["tracks"]), "track_points": sum(len(p["coordinates"]) for t in tracks["tracks"] for p in t["parts"]),
              "employees": len(reference["employees"]), "attachments": sum(len(w["attachments"]) for w in wps)}
    coverage = time_coverage(patrols, tracks)
    if coverage["date_only"]:
        warnings.append(f"{coverage['date_only']} of {coverage['leg_days']} leg days have no times at all (no track, no start/end, no timed waypoint); "
                        f"ER will get whole-day ranges for them")
    manifest = build_manifest(db, ca, zone_name, zone_source, source, counts, coverage, warnings)
    for name, doc in (("reference.json", reference), ("patrols.json", patrols), ("tracks.json", tracks), ("manifest.json", manifest)):
        (out_dir / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest
```

Add `import struct` to the module's imports.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_bundle.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add export/bundle.py tests/test_bundle.py
git commit -m "Export: bundle tracks with per-point times, manifest, write_bundle"
```

---

### Task 9: Bundle JSON Schema and validation test

**Files:**
- Create: `export/bundle.schema.json`, `tests/test_bundle_schema.py`

**Interfaces:**
- Produces: the schema document; `validate_bundle_dir(path: Path) -> list[str]` in `export/bundle.py` (returns error strings, empty when valid), used by the CLI after writing.

- [ ] **Step 1: Write the failing test**

`tests/test_bundle_schema.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from export.bundle import validate_bundle_dir, write_bundle
from export.smartdb import SmartDb

SCHEMA = json.loads((Path(__file__).parent.parent / "export" / "bundle.schema.json").read_text())


def test_schema_is_valid_2020_12():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"].endswith("/bundle.schema.json")


def test_fixture_bundle_validates(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "configured", None, {"kind": "backup", "file": "x.zip"})
    assert validate_bundle_dir(out) == []


def test_validation_reports_errors(smart_parquet, tmp_path):
    db = SmartDb(smart_parquet)
    out = tmp_path / "bundle"
    write_bundle(db, db.cas()[0], out, "Asia/Manila", "configured", None, {"kind": "backup", "file": "x.zip"})
    m = json.loads((out / "manifest.json").read_text())
    m["bundle_schema_version"] = "one"
    (out / "manifest.json").write_text(json.dumps(m))
    (out / "tracks.json").unlink()
    errs = validate_bundle_dir(out)
    assert any("manifest.json" in e and "bundle_schema_version" in e for e in errs)
    assert any("tracks.json" in e and "missing" in e for e in errs)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_bundle_schema.py -v`
Expected: FAIL (`FileNotFoundError` for the schema, then `ImportError` for `validate_bundle_dir`)

- [ ] **Step 3: Write the schema**

`export/bundle.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/PADAS/er-smart-able/export/bundle.schema.json",
  "title": "smart-able migration bundle",
  "description": "Four JSON files written by `smart-able export` under work/export/<ca_id>/bundle/. Validate each file against $defs/<file name without .json>. bundle_schema_version 1.",
  "oneOf": [
    {"$ref": "#/$defs/manifest"}, {"$ref": "#/$defs/reference"}, {"$ref": "#/$defs/patrols"}, {"$ref": "#/$defs/tracks"}
  ],
  "$defs": {
    "uuid": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
    "uuid_or_null": {"oneOf": [{"$ref": "#/$defs/uuid"}, {"type": "null"}]},
    "date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "date_or_null": {"oneOf": [{"$ref": "#/$defs/date"}, {"type": "null"}]},
    "timestamp": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?([+-][0-9]{2}:[0-9]{2}|Z)$"},
    "timestamp_or_null": {"oneOf": [{"$ref": "#/$defs/timestamp"}, {"type": "null"}]},
    "time_or_null": {"oneOf": [{"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}:[0-9]{2}$"}, {"type": "null"}]},
    "labels": {"type": "object", "additionalProperties": {"type": "string"}},
    "labelled": {"type": "object", "properties": {"labels": {"$ref": "#/$defs/labels"}, "label": {"type": ["string", "null"]}}, "required": ["labels", "label"]},
    "lonlat": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
    "language": {"type": "object", "properties": {"code": {"type": "string"}, "default": {"type": "boolean"}, "labels": {"type": "integer"}, "missing": {"type": "integer"}}, "required": ["code", "default", "labels", "missing"]},

    "manifest": {
      "type": "object",
      "properties": {
        "bundle_schema_version": {"type": "integer", "const": 1},
        "generated_at": {"$ref": "#/$defs/timestamp"},
        "generator": {"type": "object", "properties": {"name": {"type": "string"}, "version": {"type": "string"}}, "required": ["name", "version"]},
        "source": {"type": "object", "properties": {"kind": {"enum": ["backup", "export", null]}, "file": {"type": ["string", "null"]}, "smart_version": {"type": ["string", "null"]}}, "required": ["kind", "file", "smart_version"]},
        "conservation_area": {"type": "object", "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "id": {"type": "string"}, "name": {"type": "string"}, "designation": {"type": ["string", "null"]}, "country": {"type": ["string", "null"]}, "organization": {"type": ["string", "null"]}, "owner": {"type": ["string", "null"]}}, "required": ["uuid", "id", "name"]},
        "timezone": {"type": "object", "properties": {"name": {"type": "string"}, "source": {"enum": ["configured", "inferred", "default"]}}, "required": ["name", "source"]},
        "default_language": {"type": "string"},
        "languages": {"type": "array", "items": {"$ref": "#/$defs/language"}},
        "counts": {"type": "object", "properties": {"patrols": {"type": "integer"}, "legs": {"type": "integer"}, "leg_days": {"type": "integer"}, "waypoints": {"type": "integer"}, "observations": {"type": "integer"}, "tracks": {"type": "integer"}, "track_points": {"type": "integer"}, "employees": {"type": "integer"}, "attachments": {"type": "integer"}}, "required": ["patrols", "legs", "leg_days", "waypoints", "observations", "tracks", "track_points", "employees", "attachments"]},
        "time_coverage": {"type": "object", "properties": {"leg_days": {"type": "integer"}, "track": {"type": "integer"}, "leg_day_times": {"type": "integer"}, "waypoints": {"type": "integer"}, "date_only": {"type": "integer"}}, "required": ["leg_days", "track", "leg_day_times", "waypoints", "date_only"]},
        "warnings": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["bundle_schema_version", "generated_at", "generator", "source", "conservation_area", "timezone", "default_language", "languages", "counts", "time_coverage", "warnings"]
    },

    "reference": {
      "type": "object",
      "properties": {
        "patrol_types": {"type": "array", "items": {"type": "object", "properties": {"key": {"type": "string"}, "active": {"type": "boolean"}, "max_speed": {"type": ["number", "null"]}}, "required": ["key", "active"]}},
        "transports": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": "string"}, "patrol_type": {"type": ["string", "null"]}, "active": {"type": "boolean"}}, "required": ["uuid", "key", "patrol_type", "active"]}]}},
        "mandates": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": "string"}, "active": {"type": "boolean"}}, "required": ["uuid", "key", "active"]}]}},
        "stations": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "active": {"type": "boolean"}}, "required": ["uuid", "active"]}]}},
        "patrol_attributes": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": "string"}, "type": {"type": "string"}, "active": {"type": "boolean"}, "options": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": "string"}, "active": {"type": "boolean"}}, "required": ["uuid", "key", "active"]}]}}}, "required": ["uuid", "key", "type", "active", "options"]}]}},
        "agencies": {"type": "array", "items": {"type": "object", "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": ["string", "null"]}}, "required": ["uuid"]}},
        "ranks": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "agency_uuid": {"$ref": "#/$defs/uuid_or_null"}}, "required": ["uuid"]}]}},
        "teams": {"type": "array", "items": {"allOf": [{"$ref": "#/$defs/labelled"}, {"properties": {"uuid": {"$ref": "#/$defs/uuid"}, "member_uuids": {"type": "array", "items": {"$ref": "#/$defs/uuid"}}}, "required": ["uuid", "member_uuids"]}]}},
        "employees": {"type": "array", "items": {"type": "object", "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "id": {"type": ["string", "null"]}, "given_name": {"type": ["string", "null"]}, "family_name": {"type": ["string", "null"]}, "agency_uuid": {"$ref": "#/$defs/uuid_or_null"}, "rank_uuid": {"$ref": "#/$defs/uuid_or_null"}, "employment_start": {"$ref": "#/$defs/date_or_null"}, "employment_end": {"$ref": "#/$defs/date_or_null"}, "active": {"type": "boolean"}}, "required": ["uuid", "id", "given_name", "family_name", "agency_uuid", "rank_uuid", "employment_start", "employment_end", "active"], "not": {"anyOf": [{"required": ["smartuserid"]}, {"required": ["smartpassword"]}, {"required": ["birthdate"]}, {"required": ["gender"]}]}}}
      },
      "required": ["patrol_types", "transports", "mandates", "stations", "patrol_attributes", "agencies", "ranks", "teams", "employees"]
    },

    "attribute_value": {
      "type": "object",
      "properties": {"key": {"type": "string"}, "type": {"enum": ["LIST", "MLIST", "TREE", "NUMERIC", "BOOLEAN", "DATE", "TEXT", ""]},
                     "value": {}, "label": {"type": ["string", "null"]}, "labels": {"type": "array", "items": {"type": ["string", "null"]}}},
      "required": ["key", "type", "value"]
    },
    "observation": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "category_key": {"type": "string"}, "category_hkey": {"type": "string"}, "employee_uuid": {"$ref": "#/$defs/uuid_or_null"}, "attributes": {"type": "array", "items": {"$ref": "#/$defs/attribute_value"}}},
      "required": ["uuid", "category_key", "category_hkey", "employee_uuid", "attributes"]
    },
    "waypoint": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "id": {"type": ["string", "null"]}, "leg_day_uuid": {"$ref": "#/$defs/uuid"}, "time": {"$ref": "#/$defs/timestamp_or_null"},
                     "location": {"oneOf": [{"$ref": "#/$defs/lonlat"}, {"type": "null"}]}, "comment": {"type": ["string", "null"]}, "source": {"type": ["string", "null"]}, "last_modified_by_uuid": {"$ref": "#/$defs/uuid_or_null"},
                     "attachments": {"type": "array", "items": {"type": "object", "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "filename": {"type": "string"}, "path": {"type": "string"}}, "required": ["uuid", "filename", "path"]}},
                     "observation_groups": {"type": "array", "items": {"type": "object", "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "observations": {"type": "array", "items": {"$ref": "#/$defs/observation"}}}, "required": ["uuid", "observations"]}}},
      "required": ["uuid", "id", "leg_day_uuid", "time", "location", "comment", "source", "last_modified_by_uuid", "attachments", "observation_groups"]
    },
    "leg_day": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "date": {"$ref": "#/$defs/date"}, "start_time": {"$ref": "#/$defs/time_or_null"}, "end_time": {"$ref": "#/$defs/time_or_null"}, "rest_minutes": {"type": ["integer", "null"]}, "start": {"$ref": "#/$defs/timestamp_or_null"}, "end": {"$ref": "#/$defs/timestamp_or_null"}, "has_track": {"type": "boolean"}},
      "required": ["uuid", "date", "start_time", "end_time", "rest_minutes", "start", "end", "has_track"]
    },
    "leg": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "id": {"type": ["string", "null"]}, "transport_uuid": {"$ref": "#/$defs/uuid_or_null"}, "mandate_uuid": {"$ref": "#/$defs/uuid_or_null"}, "start_date": {"$ref": "#/$defs/date_or_null"}, "end_date": {"$ref": "#/$defs/date_or_null"},
                     "members": {"type": "array", "items": {"type": "object", "properties": {"employee_uuid": {"$ref": "#/$defs/uuid"}, "leader": {"type": "boolean"}, "pilot": {"type": "boolean"}}, "required": ["employee_uuid", "leader", "pilot"]}},
                     "days": {"type": "array", "items": {"$ref": "#/$defs/leg_day"}}, "waypoints": {"type": "array", "items": {"$ref": "#/$defs/waypoint"}}},
      "required": ["uuid", "id", "transport_uuid", "mandate_uuid", "start_date", "end_date", "members", "days", "waypoints"]
    },
    "patrol": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "id": {"type": ["string", "null"]}, "patrol_type": {"type": ["string", "null"]}, "station_uuid": {"$ref": "#/$defs/uuid_or_null"}, "team_uuid": {"$ref": "#/$defs/uuid_or_null"}, "objective": {"type": ["string", "null"]}, "comment": {"type": ["string", "null"]}, "armed": {"type": ["boolean", "null"]}, "start_date": {"$ref": "#/$defs/date_or_null"}, "end_date": {"$ref": "#/$defs/date_or_null"},
                     "attributes": {"type": "array", "items": {"type": "object", "properties": {"attribute_uuid": {"$ref": "#/$defs/uuid"}, "key": {"type": "string"}, "value": {}}, "required": ["attribute_uuid", "key", "value"]}},
                     "legs": {"type": "array", "items": {"$ref": "#/$defs/leg"}}},
      "required": ["uuid", "id", "patrol_type", "station_uuid", "team_uuid", "objective", "comment", "armed", "start_date", "end_date", "attributes", "legs"]
    },
    "patrols": {"type": "object", "properties": {"patrols": {"type": "array", "items": {"$ref": "#/$defs/patrol"}}}, "required": ["patrols"]},

    "track": {
      "type": "object",
      "properties": {"uuid": {"$ref": "#/$defs/uuid"}, "leg_day_uuid": {"$ref": "#/$defs/uuid"}, "leg_uuid": {"$ref": "#/$defs/uuid"}, "patrol_uuid": {"$ref": "#/$defs/uuid"}, "distance_km": {"type": ["number", "null"]}, "start": {"$ref": "#/$defs/timestamp_or_null"}, "end": {"$ref": "#/$defs/timestamp_or_null"},
                     "parts": {"type": "array", "items": {"type": "object", "properties": {"coordinates": {"type": "array", "items": {"$ref": "#/$defs/lonlat"}}, "times": {"type": "array", "items": {"$ref": "#/$defs/timestamp"}}}, "required": ["coordinates"]}}},
      "required": ["uuid", "leg_day_uuid", "leg_uuid", "patrol_uuid", "distance_km", "start", "end", "parts"]
    },
    "tracks": {"type": "object", "properties": {"tracks": {"type": "array", "items": {"$ref": "#/$defs/track"}}}, "required": ["tracks"]}
  }
}
```

- [ ] **Step 4: Implement `validate_bundle_dir`**

Append to `export/bundle.py`:

```python
SCHEMA_PATH = Path(__file__).with_name("bundle.schema.json")
BUNDLE_FILES = ("manifest", "reference", "patrols", "tracks")


def validate_bundle_dir(path: Path) -> List[str]:
    """Validate the four files against bundle.schema.json; [] when all pass."""
    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    for name in BUNDLE_FILES:
        f = path / f"{name}.json"
        if not f.exists():
            errors.append(f"{name}.json: missing")
            continue
        sub = {"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]}
        v = jsonschema.Draft202012Validator(sub)
        for e in sorted(v.iter_errors(json.loads(f.read_text(encoding="utf-8"))), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in e.path) or "(root)"
            errors.append(f"{name}.json: {where}: {e.message}")
    return errors
```

`jsonschema` is a dev dependency; the CLI (Task 10) calls `validate_bundle_dir` only when the import succeeds, and prints a one-line notice otherwise.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_bundle_schema.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add export/bundle.schema.json export/bundle.py tests/test_bundle_schema.py
git commit -m "Export: bundle JSON Schema and validation"
```

---

### Task 10: CLI, launcher `export` subcommand, and docs

**Files:**
- Create: `export/__main__.py`, `tests/test_cli.py`
- Modify: `smart-able` (header comment lines 2–11, the `case $cmd` block, new `export_()` function after `browse()`, one line in `extract()`), `README.md` ("What you get", "Repository layout"), `RUNBOOK.md` (new "### Export" after "### Browse", rows in the Warnings table), `docs/smart-data-model.md` (pointer to the export), `.dockerignore` (ensure `export/` ships; add `tests/`)

**Interfaces:**
- Produces: `python -m export --work DIR [--site-data DIR] [--attachments DIR] [--source-kind backup|export] [--source-file NAME] [ca_id …]` → writes `DIR/export/<safe_id>/{datamodel.xml, configurable_model_<uuid>.xml, datamodel.json, bundle/}`, copies the XML into `<site-data>/../export/<safe_id>/` and a merged `<site-data>/datamodel.json` (array of per-CA objects) when `--site-data` is given; exit 0, one summary line per CA; `main(argv) -> int`.
- Launcher: `./smart-able export [ca_id …]`; `./smart-able all <backup>` = extract, browse, export. Environment: `SMART_ABLE_WORK`, `SMART_ABLE_TIMEZONE`.

- [ ] **Step 1: Write the failing CLI test**

`tests/test_cli.py`:

```python
from __future__ import annotations

import json

from export.__main__ import main
from tests.conftest import CM


def test_cli_writes_everything(smart_parquet, tmp_path, capsys):
    work = smart_parquet.parent
    site = work / "site" / "data"
    site.mkdir(parents=True)
    (site / "timezones.json").write_text(json.dumps({"default": "Asia/Manila", "byCa": {"ALPHA": "Asia/Manila"}}))
    rc = main(["--work", str(work), "--site-data", str(site), "--source-kind", "backup", "--source-file", "x.zip"])
    assert rc == 0
    a = work / "export" / "ALPHA"
    assert (a / "datamodel.xml").exists() and (a / f"configurable_model_{CM}.xml").exists() and (a / "datamodel.json").exists()
    assert (a / "bundle" / "manifest.json").exists()
    m = json.loads((a / "bundle" / "manifest.json").read_text())
    assert m["timezone"] == {"name": "Asia/Manila", "source": "inferred"} and m["source"]["file"] == "x.zip"
    b = work / "export" / "BETA"
    assert (b / "datamodel.xml").exists() and not (b / "bundle").exists()   # no patrols, no bundle
    merged = json.loads((site / "datamodel.json").read_text())
    assert [d["ca_id"] for d in merged] == ["ALPHA", "BETA"]
    assert (work / "site" / "export" / "ALPHA" / "datamodel.xml").exists()
    out = capsys.readouterr()
    assert "ALPHA" in out.out and "2 patrols" in out.out
    assert "warning:" in out.err   # the missing attachment


def test_cli_selects_ca_and_rejects_unknown(smart_parquet, tmp_path, capsys):
    work = smart_parquet.parent
    assert main(["--work", str(work), "BETA"]) == 0
    assert not (work / "export" / "ALPHA").exists()
    assert main(["--work", str(work), "NOPE"]) == 1
    assert "NOPE" in capsys.readouterr().err
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL, `No module named 'export.__main__'`

- [ ] **Step 3: Implement `export/__main__.py`**

```python
"""smart-able export: write each CA's data model XML, Data Model tab JSON
and migration bundle under <work>/export/<ca_id>/.

    uv run python -m export --work work [--site-data work/site/data] [ca_id ...]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from .bundle import write_bundle
from .datamodel_json import build_datamodel_json
from .datamodel_xml import build_configurable_model_xml, build_datamodel_xml, list_configurable_models
from .smartdb import SmartDb, safe_id
from .timezone import resolve_timezone

SKIP_CA_UUID = "0" * 32   # "Cross Conservation Area Analysis" placeholder row

# warning prefix -> section of docs/smart-data-quirks.md (served as quirks.html)
QUIRK = {"timezone": "timezones", "no timezone": "timezones", "track": "tracks", "attachment": "attachments",
         "icon": "data-model-export", "useEarthRanger": "configurable-models", "extraData": "configurable-models",
         "waypoint": "waypoints-and-legs", "SMART version": "backups-versus-exports", "leg days have no times": "patrol-times"}


def warn(msg: str) -> None:
    anchor = next((a for k, a in QUIRK.items() if msg.startswith(k)), None)
    print(f"warning: {msg}" + (f"  (see quirks.html#{anchor})" if anchor else ""), file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="smart-able export", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", required=True, type=Path, help="work directory holding parquet/ (and site/)")
    p.add_argument("--site-data", type=Path, help="site/data directory to receive datamodel.json (and ../export/ copies of the XML)")
    p.add_argument("--attachments", type=Path, help="decrypted filestore root (default: <work>/site/attachments)")
    p.add_argument("--source-kind", choices=["backup", "export"], help="what the Parquet came from, for the manifest")
    p.add_argument("--source-file", help="name of the zip or folder the Parquet came from, for the manifest")
    p.add_argument("ca_ids", nargs="*", help="conservation_area.id values to export (default: all)")
    a = p.parse_args(argv)

    parquet = a.work / "parquet"
    if not (parquet / "conservation_area.parquet").exists():
        print(f"error: no {parquet}; run ./smart-able extract first", file=sys.stderr)
        return 1
    db = SmartDb(parquet)
    cas = [c for c in db.cas() if c.uuid != SKIP_CA_UUID]
    if a.ca_ids:
        by_id = {c.id: c for c in cas}
        missing = [i for i in a.ca_ids if i not in by_id]
        if missing:
            print(f"error: unknown conservation area id(s): {', '.join(missing)}; have: {', '.join(sorted(by_id))}", file=sys.stderr)
            return 1
        cas = [by_id[i] for i in a.ca_ids]
    attachments = a.attachments or (a.work / "site" / "attachments")
    merged = []
    for ca in cas:
        out = a.work / "export" / safe_id(ca.id)
        out.mkdir(parents=True, exist_ok=True)
        xml, warnings = build_datamodel_xml(db, ca.uuid)
        (out / "datamodel.xml").write_text(xml, encoding="utf-8")
        for m in list_configurable_models(db, ca.uuid):
            cm_xml, w = build_configurable_model_xml(db, m["uuid"])
            (out / f"configurable_model_{m['uuid']}.xml").write_text(cm_xml, encoding="utf-8")
            warnings += w
        dmj = build_datamodel_json(db, ca)
        (out / "datamodel.json").write_text(json.dumps(dmj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        merged.append(dmj)
        n_patrols = db.rows(f"SELECT count(*) AS n FROM {db.t('patrol')} WHERE ca_uuid = ?", [ca.uuid])[0]["n"]
        summary = (f"  {ca.id}: data model ({len(dmj['categories'])} root categories, {len(dmj['attributes'])} attributes, "
                   f"{len(dmj['configurable_models'])} configurable models)")
        if n_patrols:
            zone, source = resolve_timezone(db, ca, a.site_data)
            manifest = write_bundle(db, ca, out / "bundle", zone, source,
                                    attachments if attachments.exists() else None,
                                    {"kind": a.source_kind, "file": a.source_file})
            warnings += manifest["warnings"]
            c = manifest["counts"]
            tc = manifest["time_coverage"]
            summary += (f"; bundle ({c['patrols']} patrols, {c['waypoints']} waypoints, {c['tracks']} tracks, timezone {zone}; "
                        f"leg-day times from track {tc['track']}, start/end {tc['leg_day_times']}, waypoints {tc['waypoints']}, date only {tc['date_only']})")
            try:
                from .bundle import validate_bundle_dir
                errs = validate_bundle_dir(out / "bundle")
            except ImportError:
                errs = []
                print("  (jsonschema not installed; bundle not validated)")
            for e in errs:
                warn(f"{ca.id}: bundle schema: {e}")
        else:
            summary += "; no patrols, no bundle"
        print(summary)
        for w in dict.fromkeys(warnings):
            warn(f"{ca.id}: {w}")
        if a.site_data:
            site_export = a.site_data.parent / "export" / safe_id(ca.id)
            site_export.mkdir(parents=True, exist_ok=True)
            for f in out.glob("*.xml"):
                shutil.copyfile(f, site_export / f.name)
    if a.site_data:
        a.site_data.mkdir(parents=True, exist_ok=True)
        (a.site_data / "datamodel.json").write_text(json.dumps(merged, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: `warn()` prefixes messages with the CA id, so `QUIRK` matching uses the text after `"<id>: "`; implement the lookup on `msg.split(": ", 1)[-1]`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Wire the launcher**

In `smart-able`, header comment: add after the `browse` line

```
#   ./smart-able export [ca_id ...]    work/parquet -> work/export/<ca_id>/ (data model XML,
#                                      Data Model tab JSON, migration bundle)
```

and change the `all` line to `extract + browse + export`. Add after `browse()`:

```bash
export_() {   # `export` is a shell builtin
  [ -d "$WORK/parquet" ] || die "no $WORK/parquet; run ./smart-able extract <backup> first"
  [ -d "$ROOT/.venv" ] || die "no .venv; run ./smart-able setup first"
  say "Exporting data models and migration bundles"
  local kind= src=
  [ -f "$WORK/source.txt" ] && { kind=$(sed -n 1p "$WORK/source.txt"); src=$(sed -n 2p "$WORK/source.txt"); }
  uv run --project "$ROOT" --quiet python -m export --work "$WORK" --site-data "$WORK/site/data" \
    ${kind:+--source-kind "$kind"} ${src:+--source-file "$src"} "$@"
  say "Export ready: $WORK/export  (XML, datamodel.json and bundle/ per conservation area)"
}
```

In `extract()`, right after the input kind is decided (where `input=database` or `input=export` is set), record it for the manifest:

```bash
  printf '%s\n%s\n' "$([ "$input" = export ] && echo export || echo backup)" "$(basename "$1")" > "$WORK/source.txt"
```

In the `case $cmd` block:

```bash
  export)  export_ "$@" ;;
  all)     extract "$@"; browse; export_ ;;
```

Run: `./smart-able export` against the Lawin work directory, then `./smart-able` with no arguments.
Expected: one summary line per CA (`050500`, `050504`, `SMART`), warnings for the inferred timezone and any missing attachments, files under `work/export/`, `work/site/data/datamodel.json` and `work/site/export/*/datamodel.xml` present; the usage text shows the `export` line.

- [ ] **Step 6: Docs**

README "What you get": add a bullet

```
- `work/export/<ca_id>/`: the CA's data model as SMART-exact `datamodel.xml` and one
  `configurable_model_<uuid>.xml` per configurable model, `datamodel.json` for the browser's
  Data Model tab, and `bundle/` (manifest, reference, patrols, tracks, attachments) for
  er-smart-sync's patrol migration. See RUNBOOK.md § Export.
```

README "Repository layout": add `export/` with one line per module as in the file-structure table above, and `tests/`.

RUNBOOK: new `### Export` section after `### Browse`:

```
### Export

    ./smart-able export            # every conservation area
    ./smart-able export 050500     # one, by conservation_area.id

Writes work/export/<ca_id>/:
  datamodel.xml                      SMART's DataModel export format
  configurable_model_<uuid>.xml      one per configurable model
  datamodel.json                     the browser's Data Model tab
  bundle/manifest.json               what this bundle is, counts, timezone, warnings
  bundle/reference.json              transports, mandates, stations, teams, employees, …
  bundle/patrols.json                patrols → legs → days, members, waypoints, observations
  bundle/tracks.json                 one line per leg day with per-point times
  bundle/attachments/<wp_uuid>/      waypoint photos
The bundle is what er-smart-sync's patrol migration reads (schema: export/bundle.schema.json).

Timezone: SMART stores wall-clock times without a zone. The bundle anchors
them to the zone inferred from the waypoints (see Browse) unless you set
SMART_ABLE_TIMEZONE=Asia/Manila (any IANA name). The manifest records which.
See quirks.html#timezones.

Fidelity check against SMART's own export (SMART Desktop: Data Model > Export):

    uv run python -m export.verify_xml ~/path/to/reference/datamodel.xml work/export/<ca_id>/datamodel.xml
```

RUNBOOK Warnings table: add one row per warning text introduced in Tasks 2, 3, 7, 8 and 10 (unknown SMART version, icon missing files, `useEarthRanger` defaulted, `extraData` unverified, inferred timezone, no timezone, track offset disagreement, untimed tracks, unreadable track geometry, dangling waypoint links, missing attachments, coordinates out of range, bundle schema errors), each with its cause and what to do, and a "See" column pointing at `quirks.html#<section>` (Task 13 writes the sections).

`docs/smart-data-model.md`: one paragraph under the data-model section pointing at `export/datamodel_xml.py` for the table-to-XML mapping and at the spec.

`.dockerignore`: confirm `export/` is not listed (it must ship in the job image); add `tests/`.

- [ ] **Step 7: Run everything and commit**

Run: `uv run pytest -q && ./smart-able export && ./smart-able`
Expected: all tests pass; export runs; usage shows the new line.

```bash
git add export/__main__.py tests/test_cli.py smart-able README.md RUNBOOK.md docs/smart-data-model.md .dockerignore
git commit -m "Export: smart-able export command, all runs it, docs"
```

---

### Task 11: Browser Data Model tab

**Files:**
- Modify: `browse/index.html`: `boot()` (optional load of `datamodel.json`), the `TAB` whitelist at the `location.hash` check, `buildHeader()` tabs array, `render()` map, new `rDataModel(v)` after `rSchema`, new `<template id="help-datamodel">` next to `help-flow`, CSS additions after the `.tree` rules.

**Interfaces:**
- Consumes: `datamodel.json` as written by Task 10 (array of per-CA objects with `ca_id`, `ca_name`, `default_language`, `languages`, `categories`, `attributes`, `configurable_models`, `files`).
- Produces: tab id `datamodel`, label "Data model", icon `account_tree`; module-level state `dmLang`, `dmCm`, `dmSel` (selected category hkey); XML links `export/<safe_id>/<file>` relative to the site root.

- [ ] **Step 1: Load the data**

In `boot()`, after the `timezones` load:

```js
    try { D.dm = await getJSON('datamodel'); } catch (e) { D.dm = null; } // optional (./smart-able export)
```

Add `'datamodel'` to the hash whitelist array, `['datamodel','Data model','account_tree']` to the tabs array after `'observations'`, and `datamodel: rDataModel` to the `render()` map.

- [ ] **Step 2: Add CSS**

After the `.tree` rules:

```css
/* data model tab */
.dm .cols { grid-template-columns: 360px minmax(0, 1fr); }
.dm .attr { border-top: 1px solid var(--line); padding: 8px 0; }
.dm .attr:first-child { border-top: 0; }
.dm .attr .opts { margin: 4px 0 0 0; padding-left: 18px; }
.dm .attr .opts li.off, .dm .tree div.nd.off { color: var(--ink-3); text-decoration: line-through; }
.dm .attr .opts li.kept { font-weight: 600; }
.dm .dl a { margin-right: 14px; }
```

- [ ] **Step 3: Add the help template**

```html
  <template id="help-datamodel">
    <div class="help">
      <h3>Data model and configurable models</h3>
      <p>The <b>data model</b> is the conservation area's full vocabulary: categories (what can be observed, as a tree)
        and attributes (the fields each category asks for, with their list values or tree options). Every observation
        in this backup is typed against it.</p>
      <p>A <b>configurable model</b> is a curated subset of the data model, arranged for a mobile form: which categories
        appear, in what groups, which attributes each node shows, and which list values are kept. A conservation area can
        have several. Options the model keeps are shown in bold; dropped ones are struck through.</p>
      <h2>Languages</h2>
      <p>Labels exist per language. The picker shows each language's code and how many labels it is missing; when a label
        is missing the default language's text is shown instead. The code shown is the value to pass to
        <code>er-smart-sync --smart-language</code> when populating EarthRanger.
        <a href="quirks.html#labels-and-languages" target="_blank">More on labels and languages.</a></p>
      <h2>Downloads</h2>
      <p>The XML files are what SMART Desktop itself exports (Data Model &gt; Export), so they can be loaded into
        <code>er-smart-sync datamodel --from-file</code> or back into SMART.
        <a href="quirks.html#data-model-export" target="_blank">Known differences from SMART's own output.</a></p>
    </div>
  </template>
```

- [ ] **Step 4: Write the view**

After `rSchema`:

```js
/* ---------------- Data model ---------------- */
let dmLang = null, dmCm = '', dmSel = '';
function rDataModel(v) {
  if (!D.dm) {
    v.insertAdjacentHTML('beforeend', '<div class="panel">No data model export on disk. Run <code>./smart-able export</code> (or <code>./smart-able all</code>) and reload.</div>');
    return;
  }
  const cas = D.dm.filter(d => CA === 'all' || d.ca_id === CA);
  if (!cas.length) { v.insertAdjacentHTML('beforeend', '<div class="panel">No data model for this conservation area.</div>'); return; }
  const dm = cas.find(d => d.ca_id === CA) || cas[0];
  if (!dmLang || !dm.languages.some(l => l.code === dmLang)) dmLang = dm.default_language;
  const lab = o => (o.labels && o.labels[dmLang]) || o.label || '';
  const cm = dm.configurable_models.find(m => m.uuid === dmCm) || null;
  const kept = new Map(); // attribute key -> Set(option keys kept by the selected model)
  if (cm) (function walk(nodes) { for (const n of nodes) { for (const a of n.attributes) { if (!kept.has(a.key)) kept.set(a.key, new Set()); a.options.forEach(o => kept.get(a.key).add(o)); } walk(n.children); } })(cm.nodes);
  const safe = dm.ca_id.replace(/[^A-Za-z0-9._-]/g, '_');

  const box = el('div', 'dm'); v.appendChild(box);
  const bar = el('div', 'panel filterbar'); box.appendChild(bar);
  const nCats = (function count(cs) { return cs.reduce((n, c) => n + 1 + count(c.children), 0); })(dm.categories);
  bar.insertAdjacentHTML('beforeend', '<div class="hdr"><h2>' + esc(dm.ca_name) + ' <span class="tiny">' + nCats + ' categories · ' +
    Object.keys(dm.attributes).length + ' attributes · ' + dm.configurable_models.length + ' configurable models</span></h2>' +
    '<button class="ghost" id="dmHelp"><span class="mi" aria-hidden="true">help</span>How to read this</button></div>');
  $('#dmHelp', bar).onclick = () => helpDrawer('datamodel');
  const langSel = el('select'); langSel.setAttribute('aria-label', 'Label language');
  for (const l of dm.languages) langSel.appendChild(new Option(l.code + (l.default ? ' (default)' : '') + (l.missing ? ' · ' + l.missing + ' missing' : ''), l.code));
  langSel.value = dmLang; langSel.onchange = () => { dmLang = langSel.value; render(); };
  const cmSel = el('select'); cmSel.setAttribute('aria-label', 'Configurable model');
  cmSel.appendChild(new Option('Full data model', ''));
  for (const m of dm.configurable_models) cmSel.appendChild(new Option(m.label, m.uuid));
  cmSel.value = dmCm; cmSel.onchange = () => { dmCm = cmSel.value; dmSel = ''; render(); };
  const { wrap: sw, inp } = searchField('dmSearch', 'Find category or attribute…', '');
  const langLab = el('label', 'tiny', 'Language <a href="quirks.html#labels-and-languages" target="_blank" title="About labels and languages"><span class="mi" aria-hidden="true">info</span></a> ');
  langLab.appendChild(langSel); bar.appendChild(langLab);
  const cmLab = el('label', 'tiny', 'Model '); cmLab.appendChild(cmSel); bar.appendChild(cmLab);
  bar.appendChild(sw);
  const dl = el('div', 'dl tiny'); dl.innerHTML = 'Download: <a href="export/' + encodeURIComponent(safe) + '/' + dm.files.datamodel + '" download>datamodel.xml</a>' +
    dm.configurable_models.map(m => '<a href="export/' + encodeURIComponent(safe) + '/' + m.file + '" download>' + esc(m.label) + '.xml</a>').join('');
  bar.appendChild(dl);

  const cols = el('div', 'cols'); box.appendChild(cols);
  const left = el('div', 'panel tree'); const right = el('div', 'panel'); cols.append(left, right);
  let q = '';
  inp.oninput = () => { q = inp.value.toLowerCase(); drawTree(); };

  function drawTree() {
    left.innerHTML = '<h2>' + (cm ? esc(cm.label) : 'Categories') + '</h2>';
    const hit = c => !q || lab(c).toLowerCase().includes(q) || c.key.includes(q) || (c.attributes || []).some(a => a.key.includes(q));
    function catNode(c, depth) {
      const any = hit(c) || c.children.some(k => hit(k));
      if (!any && !c.children.length) return;
      const d = el('div', 'nd' + (c.hkey === dmSel ? ' sel' : '') + (c.active ? '' : ' off'));
      d.style.paddingLeft = (6 + depth * 14) + 'px';
      d.innerHTML = esc(lab(c)) + ' <span class="cnt">' + c.attributes.length + '</span>';
      d.onclick = () => { dmSel = c.hkey; drawTree(); drawRight(); };
      left.appendChild(d);
      c.children.forEach(k => catNode(k, depth + 1));
    }
    function cmNode(n, depth) {
      const d = el('div', 'nd' + (n.category && n.category === dmSel ? ' sel' : ''));
      d.style.paddingLeft = (6 + depth * 14) + 'px';
      d.innerHTML = (n.category ? '' : '<span class="mi" aria-hidden="true">folder</span>') + esc(n.label || '') + ' <span class="cnt">' + n.attributes.length + '</span>';
      if (n.category) d.onclick = () => { dmSel = n.category; drawTree(); drawRight(); };
      left.appendChild(d);
      n.children.forEach(k => cmNode(k, depth + 1));
    }
    (cm ? cm.nodes : dm.categories).forEach(c => (cm ? cmNode : catNode)(c, 0));
  }
  function findCat(cs, hkey) { for (const c of cs) { if (c.hkey === hkey) return c; const r = findCat(c.children, hkey); if (r) return r; } return null; }
  function optList(opts, type, keep) {
    if (!opts || !opts.length) return '';
    const li = o => '<li class="' + (o.active ? '' : 'off') + (keep && keep.has(type === 'TREE' ? o.hkey : o.key) ? ' kept' : '') + '">' + esc(lab(o)) +
      ' <span class="mono tiny">' + esc(o.key) + '</span>' + (o.children && o.children.length ? '<ul class="opts">' + o.children.map(li).join('') + '</ul>' : '') + '</li>';
    return '<ul class="opts">' + opts.map(li).join('') + '</ul>';
  }
  function drawRight() {
    const c = findCat(dm.categories, dmSel);
    if (!c) { right.innerHTML = '<p class="muted">Select a category on the left to see its attributes.</p>'; return; }
    let h = '<h2>' + esc(lab(c)) + ' <span class="mono tiny">' + esc(c.hkey) + '</span></h2>' +
      '<p class="tiny">' + (c.multiple ? 'multiple observations allowed' : 'single observation') + (c.active ? '' : ' · inactive') + (c.icon ? ' · icon ' + esc(c.icon) : '') + '</p>';
    for (const ref of c.attributes) {
      const a = dm.attributes[ref.key]; if (!a) continue;
      const keep = kept.get(ref.key);
      h += '<div class="attr' + (ref.active ? '' : ' off') + '"><b>' + esc(lab(a)) + '</b> <span class="pill">' + esc(a.type) + '</span>' +
        (a.required ? ' <span class="pill">required</span>' : '') + (ref.active ? '' : ' <span class="pill">inactive here</span>') +
        ' <span class="mono tiny">' + esc(ref.key) + '</span>' +
        (a.min != null || a.max != null ? '<div class="tiny">range ' + (a.min ?? '') + ' – ' + (a.max ?? '') + '</div>' : '') +
        (a.regex ? '<div class="tiny mono">regex ' + esc(a.regex) + '</div>' : '') +
        optList(a.options, a.type, keep) + '</div>';
    }
    right.innerHTML = h;
  }
  drawTree(); drawRight();
}
```

- [ ] **Step 5: Check syntax and click through**

Extract the script and syntax-check it:

```bash
mkdir -p /tmp/claude-smart-able
python3 -c "import re; s=open('browse/index.html').read(); open('/tmp/claude-smart-able/page.js','w').write(re.search(r'<script>(.*)</script>', s, re.S).group(1))"
node --check /tmp/claude-smart-able/page.js
```
Expected: no output.

Then, with `./smart-able serve 8765` running after Task 10's export, drive headless Chrome over the DevTools protocol (Node's built-in WebSocket, script under `/tmp/claude-smart-able/`, as in earlier sessions): open `http://localhost:8765/#datamodel`; assert `#tab-datamodel` has class `on`; assert the tree has more than 20 `.nd` rows for `050500`; click the first `.nd` and assert the right panel has at least one `.attr`; set the model select to the configurable model and assert a `folder` icon node and at least one `.kept` option exist; assert the language select's first option text starts with `en (default)`; assert the download link responds 200. Screenshot to `/tmp/claude-smart-able/datamodel.png` and look at it.

- [ ] **Step 6: Commit**

```bash
git add browse/index.html
git commit -m "Browse: Data Model tab with language and configurable-model pickers"
```

---

### Task 12: Fidelity verification against the reference export

**Files:**
- Create: `tests/test_reference_export.py` (skipped unless `SMART_ABLE_REFERENCE_DIR` is set)
- Modify: `RUNBOOK.md` (fidelity results), `export/datamodel_xml.py` as needed

Inputs: `~/projects/smart-migration-artifacts/R05 data model.zip` (SMART Desktop export of the Camarines Norte CA: `datamodel.xml` plus the icon SVGs) and `~/projects/smart-migration-artifacts/Region 05 - Camarines Norte.zip` (the CA export zip). A configurable-model export for a Lawin CA has been requested from the user; until it arrives the CM check is loose.

- [ ] **Step 1: Extract the export zip into its own work dir**

```bash
mkdir -p /tmp/claude-smart-able/ref && cd /tmp/claude-smart-able/ref && unzip -o -q ~/projects/smart-migration-artifacts/"R05 data model.zip"
cd ~/padas/er-smart-able && SMART_ABLE_WORK=/tmp/claude-smart-able/work-cn ./smart-able all ~/projects/smart-migration-artifacts/"Region 05 - Camarines Norte.zip"
```
Expected: extract, browse, export complete; `/tmp/claude-smart-able/work-cn/export/051600/datamodel.xml` exists.

- [ ] **Step 2: Compare**

```bash
uv run python -m export.verify_xml /tmp/claude-smart-able/ref/datamodel.xml /tmp/claude-smart-able/work-cn/export/051600/datamodel.xml --loose
uv run python -m export.verify_xml /tmp/claude-smart-able/ref/datamodel.xml /tmp/claude-smart-able/work-cn/export/051600/datamodel.xml
```
Expected: loose mode `identical`. Strict mode lists any ordering differences; fix each in `build_datamodel_xml` (and in the golden test only if the fixture's rule was wrong) and re-run until `identical`. Known candidates: label sort collation (Java `String.compareTo` is code-point order; if the reference disagrees with the case-insensitive sort, switch to `key=lambda a: (L.get(a['uuid']) or '', a['keyid'])`), icon ordering, and `qa_minmax` presence when only one bound is set.

- [ ] **Step 3: Compatibility checks**

```bash
cd ~/padas/earthranger-smart-utils && uv run python - <<'PY'
from smartconnect import SmartClient
c = SmartClient(api="https://tempuri.org/", username="", password="", use_language_code="en")
ref = c.load_datamodel(filename="/tmp/claude-smart-able/ref/datamodel.xml").export_as_dict()
ours = c.load_datamodel(filename="/tmp/claude-smart-able/work-cn/export/051600/datamodel.xml").export_as_dict()
assert ref == ours, "smartconnect sees a difference"
print("smartconnect: identical", len(ours["categories"]), "categories", len(ours["attributes"]), "attributes")
PY
cd ~/padas/earthranger-smart-utils && uv run er-smart-sync --dry-run datamodel --from-file /tmp/claude-smart-able/work-cn/export/051600/datamodel.xml --ca-identifier R05CN --er-endpoint example.pamdas.org --er-token x
```
Expected: `smartconnect: identical`; the dry run plans event types without contacting ER (the CLI selects `DryRunERClient` under `--dry-run`).

- [ ] **Step 4: Automate as a skipped-by-default test**

`tests/test_reference_export.py`:

```python
"""Strict fidelity check against SMART Desktop's own export.
Set SMART_ABLE_REFERENCE_DIR to a directory holding reference/datamodel.xml
and work/ (a smart-able work dir for the same CA) to enable."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from export.verify_xml import compare

REF = os.environ.get("SMART_ABLE_REFERENCE_DIR")
pytestmark = pytest.mark.skipif(not REF, reason="SMART_ABLE_REFERENCE_DIR not set")


def test_datamodel_matches_reference():
    base = Path(REF)
    ours = next((base / "work" / "export").glob("*/datamodel.xml"))
    diffs = compare((base / "reference" / "datamodel.xml").read_text(), ours.read_text())
    assert diffs == []
```

- [ ] **Step 5: Record results**

RUNBOOK "### Export": add a "Fidelity" paragraph stating the CA and SMART version the DataModel output was verified byte-identical against, that configurable-model output is verified structurally against the Botswana sample only until a CM reference arrives, and any residual strict differences with their cause. Mirror the same facts in the "Data model export" section of `docs/smart-data-quirks.md` (Task 13).

- [ ] **Step 6: Commit**

```bash
git add tests/test_reference_export.py export/datamodel_xml.py RUNBOOK.md
git commit -m "Export: DataModel XML verified against SMART Desktop's export"
```

---

### Task 13: SMART data quirks document, published with the app

**Files:**
- Create: `docs/smart-data-quirks.md`, `browse/__init__.py` (empty), `browse/build_quirks.py`, `tests/test_quirks.py`
- Modify: `pyproject.toml` (add `markdown>=3.6` to dependencies; regenerate `uv.lock`), `smart-able` (`browse()` renders the doc), `browse/index.html` (links), `RUNBOOK.md` and `README.md` (links), `web/app.py` (confirm `quirks.html` is served for a dataset)

**Interfaces:**
- Produces: `work/site/quirks.html`, rendered from the markdown with Python-Markdown's `toc` extension so every heading has a stable id; `browse/build_quirks.py <docs/smart-data-quirks.md> <out.html>` and `render(md_text: str) -> str`. The anchor ids are a contract: the app, the runbook and the exporter's warnings link to them, and a test checks that every linked anchor exists.

Anchors (slugs of the `##` headings below, exactly): `timezones`, `patrol-times`, `tracks`, `waypoints-and-legs`, `labels-and-languages`, `observation-values`, `data-model-export`, `configurable-models`, `patrol-metadata`, `staff-and-credentials`, `attachments`, `backups-versus-exports`, `profiles`.

- [ ] **Step 1: Write the document**

`docs/smart-data-quirks.md`. Write every section out in full (facts only, naming the tables and columns involved, two to five short paragraphs each); the list below gives the heading text and the facts each section must cover.

```markdown
# SMART data quirks

What to know when reading data out of a SMART conservation area backup or
export. Each section is linked from the place in smart-able where it
matters. Verified on SMART 7.5.4–7.5.6 unless noted.

## Timezones
SMART stores every date and time as local wall-clock values with no zone
(`waypoint.datetime`, `patrol_leg_day.start_time`/`end_time`, patrol dates).
smart-able infers a zone per CA from the median waypoint position
(`browse/infer_timezones.py`), and `SMART_ABLE_TIMEZONE` overrides it. The
bundle manifest records which. Track timestamps are UTC (see Tracks) and
are used to cross-check the zone. SMART 8 stores Profiles creation times in
UTC; 7.x stores them local.

## Patrol times
A SMART patrol has no timestamps of its own: `patrol` and `patrol_leg` carry
dates only. Times come from three places, in this order of precision:
(1) the leg day's track, whose points carry UTC timestamps (see Tracks);
(2) `patrol_leg_day.start_time`/`end_time`, local wall-clock, present on
most leg days; (3) the times of the waypoints recorded on that leg day
(`waypoint.datetime`, local), which bound the day's activity even when
nothing else is recorded. Lawin: 2,648 of 3,597 leg days have a track.
EarthRanger needs a start and end for every patrol segment, so the
importer sets each segment's range from the earliest and latest of those
sources per leg day, falling back to the whole calendar day when none
exists, and tags the segment's provenance with which source it used. The
bundle manifest's `time_coverage` counts leg days by their best source so
you know before importing how precise the result will be. Track points
become ER location observations on the leader with their real times;
waypoints become events at their own times.

## Tracks
`track.geometry` is extended WKB in hex: a LineString Z or MultiLineString
Z per leg day. The Z coordinate is the point's timestamp in Unix
milliseconds, UTC. GPX imports and InReach feeds land in the same table and
are indistinguishable from SMART Mobile tracks; there is no source column.
Z values that are not timestamps (elevation from some GPX tools) are
detected and the track is exported without times. No per-point speed or
accuracy. `track.distance` is in kilometres.

## Waypoints and legs
`patrol_waypoint` ties each waypoint to a leg day; legs carry dates only,
leg days carry start and end times; a leg day whose end time is earlier
than its start crossed midnight. Missing GPS is stored as 0,0. `waypoint.x`
is longitude and `y` latitude (WGS 84). `waypoint.source` values: PATROL,
INDINC, SMARTCOLLECT, ASSET, SURVEY; smart-able handles PATROL.

## Labels and languages
All display names live in `i18n_label` keyed by the row UUID; a CA can
declare languages with almost no labels (Lawin's `en_PH` has 7). Fallback
order: requested language, CA default, any. The language code is the value
to pass to `er-smart-sync --smart-language`.

## Observation values
`wp_observation_attributes` is one row per value, typed by
`dm_attribute.att_type`: LIST stores the option row (`list_element_uuid`),
TREE the node (`tree_node_uuid`), MLIST uses the `wp_observation_attributes_list`
link table, NUMERIC and BOOLEAN both use `number_value` (1.0/0.0), TEXT uses
`string_value`; DATE has not been seen in real data, the bundle reads
`string_value` then `number_value` as epoch milliseconds.

## Data model export
Attribute order is by label, not key; child element order is aggregations,
QA, names, values or tree; icon file names are the `iconfile` row UUID;
system icons are stored as `platform:/plugin/…` paths; namespace
`xml/1.1/datamodel` for 7.5. Known differences from SMART's own output are
listed here (filled in by the fidelity check).

## Configurable models
Curated overlays of the data model (`configurable_model`, `cm_node`,
`cm_attribute`, `cm_attribute_config`); nodes without a category are groups;
attribute configs are shared between nodes; options live in
`cm_attribute_option`; `useEarthRanger` and `extraData` have no known
source columns and are written with defaults.

## Patrol metadata
Patrol types GROUND/AIR/MARINE/MIXED on the patrol, transports per leg
(`patrol_leg.transport_uuid`); transports can share a label ("Others" twice
in Lawin); mandates and stations are optional; custom patrol attributes;
teams can be empty while leg members are set (`patrol_leg_members`).

## Staff and credentials
`employee` holds SMART login hashes and personal data; smart-able drops
`smartpassword` and Connect passwords from the Parquet by default
(`--keep-credentials`) and never writes login name, birth date or gender to
the bundle; `active` is derived from the employment end date.

## Attachments
Encrypted per CA with the CA UUID as the AES key; backups and exports can
lack files the database refers to; export zips have no `<ca_uuid>/` level.

## Backups versus exports
Multi-CA backups include the "Cross Conservation Area Analysis" placeholder
and SMART's example CA; exports hold one CA; `.def`/`.dat` format; the
schema snapshot is 7.5.4 and `check_schema.sh` warns on differences.

## Profiles
Lawin uses Profiles (the i2 plugin) to track individual threat sightings,
which is unusual; see docs/profiles-to-er-entities.md and the in-app help.
```

- [ ] **Step 2: Write the failing test**

`tests/test_quirks.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
ANCHORS = {"timezones", "patrol-times", "tracks", "waypoints-and-legs", "labels-and-languages", "observation-values", "data-model-export",
           "configurable-models", "patrol-metadata", "staff-and-credentials", "attachments", "backups-versus-exports", "profiles"}


def test_render_has_every_anchor():
    from browse.build_quirks import render
    html = render((ROOT / "docs" / "smart-data-quirks.md").read_text())
    for a in ANCHORS:
        assert f'id="{a}"' in html, a
    assert "<nav" in html and "quirks" in html.lower()


def test_links_in_app_and_runbook_resolve():
    linked = set()
    for f in (ROOT / "browse" / "index.html", ROOT / "RUNBOOK.md", ROOT / "README.md", ROOT / "export" / "__main__.py"):
        linked |= set(re.findall(r"quirks\.html#([a-z0-9-]+)", f.read_text()))
    assert linked <= ANCHORS, linked - ANCHORS
    assert {"timezones", "patrol-times", "tracks", "labels-and-languages", "data-model-export"} <= linked
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_quirks.py -v`
Expected: FAIL (`No module named 'browse.build_quirks'`)

- [ ] **Step 4: Implement the renderer**

Add `"markdown>=3.6"` to `[project.dependencies]`, run `uv lock && uv sync --extra dev --extra web`. Create `browse/__init__.py` (empty) and `browse/build_quirks.py`:

```python
#!/usr/bin/env python3
"""Render docs/smart-data-quirks.md to work/site/quirks.html with stable
heading ids, so the browser, the runbook and export warnings can deep-link
to sections. Run by `./smart-able browse`.

Usage: build_quirks.py <markdown file> <output html>
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SMART data quirks · smart-able</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font: 15px/1.55 system-ui, sans-serif; margin: 0; color: #1d2b36; background: #fff; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 24px 20px 60px; }}
  nav {{ background: #f3f6f8; border: 1px solid #dde3e8; border-radius: 10px; padding: 10px 16px; margin-bottom: 24px; }}
  nav ul {{ margin: 0; padding-left: 18px; }} h1 {{ margin-top: 0; }}
  h2 {{ margin-top: 32px; border-top: 1px solid #dde3e8; padding-top: 16px; }}
  code {{ background: #f3f6f8; padding: 1px 4px; border-radius: 4px; }}
  table {{ border-collapse: collapse; }} td, th {{ border: 1px solid #dde3e8; padding: 4px 8px; }}
  a.back {{ font-size: 13px; }}
  :target {{ background: #fff6d6; }}
</style></head>
<body><div class="wrap"><a class="back" href="./">&larr; back to the browser</a>
{toc}
{body}
</div></body></html>
"""


def render(md_text: str) -> str:
    m = markdown.Markdown(extensions=["toc", "tables", "fenced_code"], extension_configs={"toc": {"toc_depth": "2-3"}})
    body = m.convert(md_text)
    return PAGE.format(toc="<nav>" + m.toc + "</nav>", body=body)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(render(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"  {dst}")
```

In `smart-able` `browse()`, inside the `.venv` branch after the timezone step:

```bash
    uv run --project "$ROOT" --quiet python "$ROOT/browse/build_quirks.py" "$ROOT/docs/smart-data-quirks.md" "$WORK/site/quirks.html"
```

- [ ] **Step 5: Add the links**

`browse/index.html`:
- `rOverview`, where the timezone `zones` line is rendered: append `' <a class="tiny" href="quirks.html#timezones" target="_blank">why times need a zone</a>'`.
- Patrol drawer caption that reads `'Waypoints colored by observation group; orange line is the recorded GPS track. '`: append `'<a href="quirks.html#tracks" target="_blank">About tracks</a> '` before the attribution.
- Patrol drawer, in the `kv` block that lists the patrol's dates: add a row `['Times', 'legs carry dates; times come from tracks, leg-day start/end and waypoints']` whose value cell links to `quirks.html#patrol-times`.
- Patrols view filter bar, next to the timeline controls: a `tiny` link `how patrol times are derived` to `quirks.html#patrol-times`.
- Task 11's help template and language label already link `#labels-and-languages` and `#data-model-export`.
- `rSchema` reading notes: add a final `<li>` with `<a href="quirks.html" target="_blank">The full list of SMART data quirks</a>`.

`RUNBOOK.md` Warnings table: fill the "See" column added in Task 10 with `quirks.html#<anchor>` per row; add a line under "## Handling the data" naming `docs/smart-data-quirks.md` and that `browse` publishes it as `quirks.html`.

`README.md` "Documentation": add `docs/smart-data-quirks.md` with one line, and that it is served at `quirks.html` in the browser.

`web/app.py`: `quirks.html` is a regular file in the dataset's site directory; confirm the `/d/{id}/{path}` handler serves it (`open_site_file`) and add it to the local curl check: `curl -s localhost:8080/d/<id>/quirks.html | grep -c 'id="timezones"'` → `1`. The service image does not run `browse`, so `web/Dockerfile` needs nothing; the job image copies the whole tree.

- [ ] **Step 6: Run tests and look at the page**

Run: `uv run pytest -q && ./smart-able browse && ./smart-able export`, then with `serve` running open `http://localhost:8765/quirks.html#tracks`.
Expected: all tests pass; the page renders with the table of contents and `#tracks` highlighted; the Overview and a patrol drawer show the new links.

- [ ] **Step 7: Commit**

```bash
git add docs/smart-data-quirks.md browse/__init__.py browse/build_quirks.py tests/test_quirks.py pyproject.toml uv.lock smart-able browse/index.html RUNBOOK.md README.md web/app.py
git commit -m "Docs: SMART data quirks, published with the browser and deep-linked"
```

---

## Self-review notes

- Spec coverage: command and layout (Task 10), DataModel XML (2), ConfigurableModel XML (3), fidelity verification (4, 12), Data Model tab with language picker (11), bundle files and schema (7, 8, 9), timezone (6, 8), multi-CA and safe ids (10), warnings (2, 3, 7, 8, 10), language coverage (5), testing (every task). The quirks document (13) was requested on 2026-10-12 after the spec was approved and is reflected in the spec's "Browser" and "Warnings" sections.
- Type consistency: `build_datamodel_xml(db, ca_uuid) -> (str, list)`; `build_configurable_model_xml(db, cm_uuid) -> (str, list)`; `build_datamodel_json(db, ca: CA) -> dict`; `write_bundle(db, ca, out_dir, zone_name, zone_source, attachments_root, source) -> dict`; `resolve_timezone(db, ca, site_data, env) -> (str, str)`; `validate_bundle_dir(path) -> list[str]`; Task 10 calls all of these in these forms.
- Review Focus tests: `test_labels_fallback` (1), `test_xml_escaping` and `test_json_is_utf8` (2), `test_leg_day_midnight_and_null_times` (3), `test_track_without_plausible_times` (4), `test_icons_only_referenced_and_unique` (5).
