"""Findings and the plan: the data the load page renders. A finding is where
the job stopped and what a human does about it; the plan is what a run
would write. Pure functions, no er-smart-sync or Google imports, so the
service and the job both use them."""
import re

MAX_PATROLS = 50
LIST_CAP = 200
DETAIL_LINES = 200   # a finding's detail on the load doc; the full list is in findings.json and log.txt
# Preflight codes (er-smart-sync preflight.py) for what a run's stages 1-2
# create: event types (datamodel), patrol types, the segment schema (the
# universal patrol fields), subjects and choices (patrol-datamodel). A plan
# writes nothing, so its preflight reports these as missing; the run writes
# them and preflights again. Teams, the roster group, the preview feature,
# permissions, the timezone and the collection type are not created by a run.
CREATED_BY_RUN = frozenset({"event_types", "patrol_types", "segment_schema", "subjects", "choices"})
CREATED_PREFIX = "Will be created by this load: "
BLOCKING_CHECKLIST = ("enable_patrol_schemas", "permission_patrol_types", "permission_segment_schema",
                      "permission_subjects", "permission_patrol_config", "permission_subject_group", "team",
                      "roster_group")

EVENT_CATEGORY = re.compile(r"[A-Za-z0-9_-]{2,30}")


def ca_identifier(ca_id: str) -> str:
    """A load's default ER event-category identifier: smart-<ca id>, made safe (2-30 chars of [A-Za-z0-9_-])."""
    s = re.sub(r"[^a-z0-9_-]+", "-", f"smart-{ca_id or 'ca'}".lower()).strip("-")
    return (s if len(s) >= 2 else "smart-ca")[:30]


def finding(stage, code, severity, title, detail="", fix="", patrols=(), values=()) -> dict:
    patrols = list(patrols)
    return {"stage": stage, "code": code, "severity": severity, "title": title, "detail": detail, "fix": fix,
            "affected": {"count": len(patrols), "patrols": patrols[:MAX_PATROLS]}, "values": list(values)}


# The exact strings a finding asks the admin to type, shown as copyable
# values. The checklist quotes them in backticks; commands and placeholders
# are quoted the same way and are left out.
_QUOTED = re.compile(r"`([^`]+)`")
_PLACEHOLDER = re.compile(r"<.*>")


def _not_a_value(v: str) -> bool:
    return v.startswith("er-smart-sync") or v.startswith("--") or bool(_PLACEHOLDER.fullmatch(v))
VALUE_LABEL = {"team": "Team name", "permission_subject_group": "Subject group", "station_names": "Station name",
               "enable_patrol_schemas": "Feature"}   # roster_group quotes only an example name: no value
_TEAM_EXAMPLE = re.compile(r"^(.*) \((?:missing|inactive), \d+ patrols?\)$")


def checklist_values(item: dict) -> list:
    code = item.get("code") or ""
    label = VALUE_LABEL.get(code) or ("Permission" if code.startswith("permission_") else None)
    if not label:
        return []
    out, seen = [], set()
    for text in [item.get("title") or ""] + list(item.get("steps") or []):
        for v in _QUOTED.findall(text):
            if v in seen or _not_a_value(v):
                continue
            if code == "station_names" and not v.startswith("Unnamed station"):
                continue   # the `patrol_station` field name is quoted beside the station names
            seen.add(v)
            out.append({"label": label, "value": v})
    return out


def preflight_values(f: dict) -> list:
    if f.get("code") != "teams":
        return []
    names = [m.group(1) for m in map(_TEAM_EXAMPLE.match, f.get("examples") or []) if m]
    return [{"label": "Team name", "value": n} for n in names]


def from_checklist(items: list) -> list:
    return [finding("patrol_datamodel", i["code"], "blocking" if i["code"] in BLOCKING_CHECKLIST else "warning",
                    i["title"], fix="\n".join(i.get("steps") or []), values=checklist_values(i)) for i in items]


def from_preflight(report: dict) -> list:
    out = []
    for f in list(report.get("blocking") or []) + list(report.get("warnings") or []):
        out.append(finding("preflight", f["code"], f["level"], f["message"], detail="\n".join(f.get("examples") or []),
                           fix=f.get("fix") or "", patrols=f.get("affected_patrols") or [], values=preflight_values(f)))
    return out


def _created_by_run(f: dict) -> bool:
    if f.get("stage") != "preflight" or f.get("code") not in CREATED_BY_RUN:
        return False
    # of the event_types findings only "no active event type" is what the
    # datamodel push creates; ambiguous matches and configurable-model
    # variants stay as they are
    return f["code"] != "event_types" or "have no active event type" in (f.get("title") or "")


def plan_mode_adjust(findings: list) -> list:
    """A plan's preflight findings for what the run itself will create become
    info, titled so; every other finding is returned unchanged."""
    out = []
    for f in findings:
        if _created_by_run(f):
            f = {**f, "severity": "info", "title": CREATED_PREFIX + (f.get("title") or "")}
        out.append(f)
    return out


def clip(line: str, n: int = 500) -> str:
    return line if len(line) <= n else line[:n - 1] + "…"


def from_failed_patrols(failed: dict, ids: dict) -> list:
    if not failed:
        return []
    n = len(failed)
    lines = [clip(f"{ids.get(u, u)}: {err}") for u, err in failed.items()]
    if len(lines) > DETAIL_LINES:
        lines = lines[:DETAIL_LINES] + [f"… and {len(lines) - DETAIL_LINES} more; see log.txt"]
    detail = "\n".join(lines)
    return [finding("import", "patrols_failed", "blocking", f"{n} patrol{'s' if n != 1 else ''} failed to import",
                    detail=detail, fix="Read each error; fix the site if it names a missing team, subject or event type, "
                    "then press Continue. Only these patrols are retried.", patrols=list(failed))]


def token_rejected(detail: str) -> dict:
    return finding("datamodel", "site_token_rejected", "blocking", "The site's token no longer works", detail=detail,
                   fix="Register the site again with a working token, then start a new load.")


def has_blocking(findings: list) -> bool:
    return any(f.get("severity") == "blocking" for f in findings)


def _cap(items: list) -> tuple:
    return items[:LIST_CAP], max(0, len(items) - LIST_CAP)


def _entry(value, label=None) -> dict:
    return {"value": value, "label": label or value}


def _group(**lists) -> dict:
    """Each list capped, with `more` saying per list how many were cut."""
    out, more = {}, {}
    for k, v in lists.items():
        if isinstance(v, list):
            out[k], cut = _cap(v)
            if cut:
                more[k] = cut
        else:
            out[k] = v
    if more:
        out["more"] = more
    return out


def build_plan(*, datamodel_stats, dry_calls, pd_changes, pd_stats, roster_group, patrols, ledger_done, counts) -> dict:
    cats, types = {"create": [], "update": []}, {"create": [], "update": []}
    for name, args, kwargs in dry_calls:
        payload = args[0] if args else kwargs.get("data") or kwargs.get("event_type") or {}
        e = _entry(payload.get("value"), payload.get("display"))
        if name == "post_event_category":
            cats["create"].append(e)
        elif name == "patch_event_category":
            cats["update"].append(e)
        elif name == "post_event_type":
            types["create"].append(e)
        elif name == "patch_event_type":
            types["update"].append(e)
    by_kind = {kind: {"create": [], "update": [], "deactivate": []} for kind in ("patrol_type", "choice", "subject")}
    action_key = {"created": "create", "updated": "update", "deactivated": "deactivate"}
    for c in pd_changes:
        kind, value, ident = c.get("kind"), c.get("value"), c.get("id")
        # er-smart-sync records a deactivation as an update whose before-state was active
        deactivation = c.get("action") == "updated" and (c.get("before") or {}).get("is_active") is True
        k = "deactivate" if deactivation else action_key.get(c.get("action"))
        if kind not in by_kind or k not in by_kind[kind]:
            continue
        if kind == "subject":
            # a plan writes nothing, so a subject it would create has no id yet (er-smart-sync records a
            # placeholder there, never shown); an update or deactivation names the existing one
            name = c.get("name") or ("(unnamed)" if k == "create" else ident)
            entry = _entry(None if k == "create" else ident, name)
        elif kind == "choice" and c.get("field") and value:
            entry = _entry(f"{c['field']}.{value}", value)   # the same value can exist under several fields
        else:
            entry = _entry(value or ident)
        by_kind[kind][k].append(entry)
    plan = {
        "event_categories": _group(**cats, unchanged=datamodel_stats.get("categories_existing", 0)),
        "event_types": _group(**types, unchanged=datamodel_stats.get("event_types_unchanged", 0)),
        "patrol_types": _group(**by_kind["patrol_type"]),
        "universal_patrol_fields": "write" if pd_stats.get("schema_written") else "skip" if pd_stats.get("schema_skipped") else "merge",
        "choices": _group(**by_kind["choice"]),
        "subjects": _group(**by_kind["subject"]),
        "roster": {"group": roster_group, "add": pd_stats.get("subjects_grouped", 0)},
    }
    if patrols is not None:   # None: a data-model-only load imports no patrols
        dates = sorted(p["start_date"] for p in patrols if p.get("start_date"))
        plan["patrols"] = {"total": len(patrols), "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                           "already_done": len(ledger_done), "events": counts.get("observations", 0),
                           "track_points": counts.get("track_points", 0)}
    return plan
