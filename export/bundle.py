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
from .timezone import localize, plausible_epoch_ms, track_ms_iso
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
            name = a["filename"] or ""
            if not name or Path(name).name != name or name in (".", ".."):
                warnings.append(f"attachment {name!r} of waypoint {H(w['uuid'])} has a path in its name; left out")
                continue
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
    placeholder_legs = 0
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
            # SMART stores an unset start date as 1970-01-01 and then generates a leg day for every day up to the end
            sd = l["start_date"]
            sd = sd if isinstance(sd, date) or sd is None else date.fromisoformat(str(sd)[:10])
            placeholder = (sd is not None and sd <= date(1971, 1, 1)) or len(dl) > 366
            placeholder_legs += placeholder
            pl.append({"uuid": H(l["uuid"]), "id": l["id"], "transport_uuid": H(l["transport_uuid"]), "mandate_uuid": H(l["mandate_uuid"]),
                       "start_date": iso_date(l["start_date"]), "end_date": iso_date(l["end_date"]), "placeholder_dates": placeholder,
                       "members": members.get(l["uuid"], []), "days": dl, "waypoints": [waypoint(w) for w in wps_by_leg.get(l["uuid"], [])]})
        out.append({"uuid": H(p["uuid"]), "id": p["id"], "patrol_type": p["patrol_type"], "station_uuid": H(p["station_uuid"]), "team_uuid": H(p["team_uuid"]),
                    "objective": p["objective"], "comment": p["comment"], "armed": None if p["is_armed"] is None else bool(p["is_armed"]),
                    "start_date": iso_date(p["start_date"]), "end_date": iso_date(p["end_date"]), "attributes": pattrs.get(p["uuid"], []), "legs": pl})
    if placeholder_legs:
        warnings.append(f"{placeholder_legs} leg(s) start on 1970-01-01, SMART's placeholder for an unset date, or span more than a year; "
                        f"their leg days are kept as stored (see quirks.html#patrol-times)")
    return {"patrols": out}


def _track_rows(db: SmartDb, ca_uuid: str) -> List[dict]:
    return db.rows(f"SELECT t.uuid, t.patrol_leg_day_uuid, t.geometry, t.distance, l.uuid AS leg_uuid, p.uuid AS patrol_uuid, "
                   f"d.patrol_day, d.start_time FROM {db.t('track')} t JOIN {db.t('patrol_leg_day')} d ON d.uuid = t.patrol_leg_day_uuid "
                   f"JOIN {db.t('patrol_leg')} l ON l.uuid = d.patrol_leg_uuid JOIN {db.t('patrol')} p ON p.uuid = l.patrol_uuid "
                   f"WHERE p.ca_uuid = ? ORDER BY d.patrol_day, t.uuid", [ca_uuid])


def build_tracks(db: SmartDb, ca_uuid: str, zone: ZoneInfo, warnings: List[str]) -> dict:
    out = []
    untimed = 0
    for r in _track_rows(db, ca_uuid):
        if not r["geometry"]:
            warnings.append(f"track {H(r['uuid'])} has no geometry; left out")
            continue
        try:
            parts = parse_track_wkb(r["geometry"])
        except (ValueError, struct.error) as e:
            warnings.append(f"track {H(r['uuid'])} has unreadable geometry ({e}); left out")
            continue
        timed = any(parts) and all(plausible_epoch_ms(z) for part in parts for (_, _, z) in part)
        if not timed:
            untimed += 1
        first = last = None
        jparts = []
        for part in parts:
            jp: dict = {"coordinates": [[x, y] for (x, y, _) in part]}
            if timed and part:
                jp["times"] = [track_ms_iso(z, zone) for (_, _, z) in part]
                first = jp["times"][0] if first is None else min(first, jp["times"][0])
                last = jp["times"][-1] if last is None else max(last, jp["times"][-1])
            jparts.append(jp)
        out.append({"uuid": H(r["uuid"]), "leg_day_uuid": H(r["patrol_leg_day_uuid"]), "leg_uuid": H(r["leg_uuid"]), "patrol_uuid": H(r["patrol_uuid"]),
                    "distance_km": r["distance"], "start": first, "end": last, "parts": jparts})
    if untimed:
        warnings.append(f"{untimed} track(s) have Z values that are not epoch-millisecond timestamps; their points carry no times")
    return {"tracks": out}


def check_track_offset(db: SmartDb, ca_uuid: str, warnings: List[str]) -> None:
    """Compare each leg day's start time with its track's first point. SMART
    stores both as local wall-clock, so they should agree to the hour; a
    majority that does not means the tracks are in true UTC (another SMART
    version) or the leg-day times are wrong."""
    votes: Dict[int, int] = defaultdict(int)
    for r in _track_rows(db, ca_uuid):
        if r["start_time"] is None or not r["geometry"]:
            continue
        try:
            parts = parse_track_wkb(r["geometry"])
        except (ValueError, struct.error):
            continue
        zs = [z for part in parts for (_, _, z) in part if plausible_epoch_ms(z)]
        if not zs:
            continue
        local = datetime.combine(r["patrol_day"], r["start_time"])
        first = datetime.fromtimestamp(min(zs) / 1000.0, tz=_tz.utc).replace(tzinfo=None)
        votes[round((local - first).total_seconds() / 3600)] += 1
    if not votes:
        return
    diff, n = max(votes.items(), key=lambda kv: kv[1])
    total = sum(votes.values())
    if diff != 0:
        warnings.append(f"track times are {abs(diff)} h {'behind' if diff > 0 else 'ahead of'} the leg-day start times on {n} of {total} leg days with both; "
                        f"SMART normally stores track times as local wall-clock, so these tracks may be in UTC or the leg-day times may be wrong "
                        f"(see quirks.html#patrol-times)")


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
    check_track_offset(db, ca.uuid, warnings)
    patrols = build_patrols(db, ca.uuid, zone, attachments_root, out_dir, warnings)
    reference = build_reference(db, ca.uuid)
    legs = [l for p in patrols["patrols"] for l in p["legs"]]
    wps = [w for l in legs for w in l["waypoints"]]
    counts = {"patrols": len(patrols["patrols"]), "legs": len(legs), "leg_days": sum(len(l["days"]) for l in legs),
              "waypoints": len(wps), "observations": sum(len(g["observations"]) for w in wps for g in w["observation_groups"]),
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
