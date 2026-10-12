"""The migration bundle: reference.json, patrols.json, tracks.json and
manifest.json for one conservation area, plus copied attachments.

Everything here is plain dicts ready for json.dump; the contract is
export/bundle.schema.json.
"""
from __future__ import annotations

import json
import shutil
import struct
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from datetime import timezone as _tz
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import version
from .datamodel_json import language_coverage
from .smartdb import CA, Labels, SmartDb, hyphenate
from .timezone import localize, plausible_epoch_ms, utc_ms_iso
from .wkb import parse_track_wkb

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
    if db.has("employee_team_member") and db.has("employee_team"):
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
        end_d = None if end is None else (end if isinstance(end, date) else date.fromisoformat(str(end)[:10]))
        ref["employees"].append({"uuid": H(r["uuid"]), "id": r["id"], "given_name": r["givenname"], "family_name": r["familyname"],
                                 "agency_uuid": H(r["agency_uuid"]), "rank_uuid": H(r["rank_uuid"]),
                                 "employment_start": iso_date(r["startemploymentdate"]), "employment_end": iso_date(end),
                                 "active": end_d is None or end_d >= today})
    return ref


def typed_value(att_type: str, row: dict, mlist_rows: List[dict], L: Labels) -> dict:
    """One observation attribute value, typed by dm_attribute.att_type."""
    t = (att_type or "").strip()
    out: dict = {"key": row["keyid"], "type": t}
    if t == "LIST":
        out["value"] = row["list_keyid"]
        out["label"] = L.get(row["list_element_uuid"]) if row["list_element_uuid"] else None
    elif t == "MLIST":
        rows = mlist_rows or ([row] if row["list_element_uuid"] else [])
        out["value"] = [m["list_keyid"] for m in rows]
        out["labels"] = [L.get(m["list_element_uuid"]) for m in rows]
    elif t == "TREE":
        out["value"] = (row["tree_hkey"] or "").rstrip(".") or None
        out["label"] = L.get(row["tree_node_uuid"]) if row["tree_node_uuid"] else None
    elif t == "NUMERIC":
        out["value"] = row["number_value"]
    elif t == "BOOLEAN":
        out["value"] = None if row["number_value"] is None else bool(row["number_value"])
    elif t == "DATE":
        if row["string_value"]:
            out["value"] = str(row["string_value"])[:10]
        elif row["number_value"] is not None:
            out["value"] = datetime.fromtimestamp(row["number_value"] / 1000.0, tz=_tz.utc).date().isoformat()
        else:
            out["value"] = None
    else:
        out["value"] = row["string_value"]
    return out


def build_patrols(db: SmartDb, ca_uuid: str, zone: ZoneInfo, attachments_root: Optional[Path], out_dir: Optional[Path], warnings: List[str]) -> dict:
    L = db.labels(ca_uuid)
    cats = {r["uuid"]: r for r in db.rows(f"SELECT uuid, hkey FROM {db.t('dm_category')} WHERE ca_uuid = ?", [ca_uuid])}
    tracked = {r["patrol_leg_day_uuid"] for r in db.rows(
        f"SELECT t.patrol_leg_day_uuid FROM {db.t('track')} t JOIN {db.t('patrol_leg_day')} d ON d.uuid = t.patrol_leg_day_uuid "
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
    if db.has("patrol_attribute_value") and db.has("patrol_attribute"):
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
    for r in db.rows(f"SELECT pw.wp_uuid FROM {db.t('patrol_waypoint')} pw JOIN {db.t('waypoint')} w ON w.uuid = pw.wp_uuid "
                     f"LEFT JOIN {db.t('patrol_leg_day')} d ON d.uuid = pw.leg_day_uuid WHERE w.ca_uuid = ? AND d.uuid IS NULL", [ca_uuid]):
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
            src = attachments_root / ca_uuid / "patrol" / wp_patrol[w["uuid"]] / a["filename"] if attachments_root else None
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
                hkey = (cats.get(o["category_uuid"]) or {}).get("hkey") or ""
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
