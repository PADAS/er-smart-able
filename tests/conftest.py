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


# columns retyped the way csv_to_parquet.sh types them, so tests see real types
CASTS = {
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


def _cell(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


@pytest.fixture
def smart_parquet(tmp_path: Path) -> Path:
    out = tmp_path / "parquet"
    out.mkdir()
    con = duckdb.connect()
    for name, (cols, rows) in _tables().items():
        con.execute(f"CREATE TABLE t_{name} ({', '.join(c + ' VARCHAR' for c in cols)})")
        if rows:
            con.executemany(f"INSERT INTO t_{name} VALUES ({', '.join('?' for _ in cols)})", [[_cell(v) for v in r] for r in rows])
        expr = CASTS.get(name)
        sel = f"SELECT * REPLACE ({expr}) FROM t_{name}" if expr else f"SELECT * FROM t_{name}"
        con.execute(f"COPY ({sel}) TO '{out / name}.parquet' (FORMAT PARQUET)")
    con.close()
    return out
