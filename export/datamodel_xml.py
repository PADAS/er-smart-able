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

from .smartdb import Labels, SmartDb, hyphenate
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
            return [("imageFile", f"cn_img1_{uuid.replace('-', '')}.{row['imagetype'].lower()}"), ("isCustomImage", "true")]
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
                   + ([] if not n.get("imagetype") else image_attrs(n, n["uuid"])))
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

        def tnode(parent: Optional[str], tag: str, cfg: str = c["uuid"]) -> None:
            for tn in cfg_tree.get((cfg, parent), []):
                el = tree_el.get(tn["dm_tree_node_uuid"])
                if not el:
                    warnings.append(f"cm_attribute_tree_node {tn['uuid']} refers to unknown tree node")
                    continue
                x.open(tag, [("keyRef", el["keyid"]), ("hkeyRef", el["hkey"]), ("dmUuid", el["uuid"]),
                             ("isActive", _b(tn["is_active"])), ("id", hyphenate(tn["uuid"]))] + image_attrs(tn, tn["uuid"]))
                _name_els(x, L, el["uuid"], codes, "DM")
                tnode(tn["uuid"], "children", cfg)
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
