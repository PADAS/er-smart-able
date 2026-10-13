"""The Data Model tab's JSON: the same content as the XML, shaped for the
browser (nested categories, attributes keyed by key, configurable models
with the options they keep, per-language labels and coverage).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from .datamodel_xml import list_configurable_models
from .smartdb import CA, Labels, SmartDb, safe_id


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

    def ik(u: Optional[str]) -> Optional[str]:
        return icon_key.get(u) if u else None

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

        def nnodes(parent: Optional[str], nkids=nkids, natts=natts, kept=kept) -> list:
            out = []
            for n in nkids.get(parent, []):
                label = L.get(n["uuid"]) or (L.get(n["category_uuid"]) if n["category_uuid"] else None)
                out.append({"label": label, "category": cat_hkey.get(n["category_uuid"]) if n["category_uuid"] else None,
                            "attributes": [{"key": by_uuid.get(a["attribute_uuid"]), "config": a["config_uuid"],
                                            "options": kept.get(a["config_uuid"], [])} for a in natts.get(n["uuid"], [])],
                            "children": nnodes(n["uuid"], nkids, natts, kept)})
            return out

        cms.append({"uuid": m["uuid"], "label": m["label"], "file": f"configurable_model_{safe_id(m['uuid'])}.xml", "nodes": nnodes(None)})

    langs = db.languages(ca.uuid)
    return {"ca": ca.uuid, "ca_id": ca.id, "ca_name": ca.name, "dir": None,
            "default_language": next((l.code for l in langs if l.default), langs[0].code if langs else "en"),
            "languages": language_coverage(db, ca.uuid),
            "categories": cnodes(None), "attributes": attrs, "configurable_models": cms,
            "files": {"datamodel": "datamodel.xml"}}
