"""Build SMART's DataModel XML and ConfigurableModel XML from the Parquet
tables, matching SMART Desktop's own export byte for byte.

Ordering and layout rules were read off a SMART 7.5.6 export of the
Camarines Norte CA (2026-10-12): attributes sorted by default-language
label; child elements aggregations, qa, names, values/tree; categories by
cat_order; icon files named <iconfile.uuid>.svg. See the spec for the table.
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
        if not icon_uuid:
            return []
        if icon_uuid not in icon_key:
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
            def tree(parent: Optional[str], tag: str, att_uuid: str = a["uuid"]) -> None:
                for n in tree_children.get((att_uuid, parent), []):
                    x.open(tag, [("key", n["keyid"]), ("isactive", _b(n["is_active"]))] + iconkey(n["icon_uuid"]))
                    _names(x, L, n["uuid"], codes)
                    tree(n["uuid"], "children", att_uuid)
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
