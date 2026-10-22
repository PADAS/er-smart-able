"""Findings and the plan: the data the load page renders. A finding is where
the job stopped and what a human does about it; the plan is what a run
would write. Pure functions, no er-smart-sync or Google imports, so the
service and the job both use them."""
MAX_PATROLS = 50
LIST_CAP = 200
BLOCKING_CHECKLIST = ("enable_patrol_schemas", "permission_patrol_types", "permission_segment_schema",
                      "permission_subjects", "permission_patrol_config", "permission_subject_group", "team",
                      "roster_group")


def finding(stage, code, severity, title, detail="", fix="", patrols=()) -> dict:
    patrols = list(patrols)
    return {"stage": stage, "code": code, "severity": severity, "title": title, "detail": detail, "fix": fix,
            "affected": {"count": len(patrols), "patrols": patrols[:MAX_PATROLS]}}


def from_checklist(items: list) -> list:
    return [finding("patrol_datamodel", i["code"], "blocking" if i["code"] in BLOCKING_CHECKLIST else "warning",
                    i["title"], fix="\n".join(i.get("steps") or [])) for i in items]


def from_preflight(report: dict) -> list:
    out = []
    for f in list(report.get("blocking") or []) + list(report.get("warnings") or []):
        out.append(finding("preflight", f["code"], f["level"], f["message"], detail="\n".join(f.get("examples") or []),
                           fix=f.get("fix") or "", patrols=f.get("affected_patrols") or []))
    return out


def from_failed_patrols(failed: dict, ids: dict) -> list:
    if not failed:
        return []
    n = len(failed)
    detail = "\n".join(f"{ids.get(u, u)}: {err}" for u, err in failed.items())
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
    out, more = {}, 0
    for k, v in lists.items():
        if isinstance(v, list):
            out[k], cut = _cap(v)
            more += cut
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
    by_kind = {"patrol_type": {"create": [], "update": []}, "choice": {"create": [], "update": []},
               "subject": {"create": [], "update": [], "deactivate": []}}
    action_key = {"created": "create", "updated": "update", "deactivated": "deactivate"}
    for c in pd_changes:
        k = action_key.get(c.get("action"))
        if c.get("kind") in by_kind and k in by_kind[c["kind"]]:
            ident = c.get("id") if c.get("kind") == "subject" else c.get("value")
            by_kind[c["kind"]][k].append(_entry(ident or c.get("value"), (c.get("name") or c.get("value")) if c.get("kind") == "subject" else None))
    dates = sorted(p["start_date"] for p in patrols if p.get("start_date"))
    return {
        "event_categories": _group(**cats, unchanged=datamodel_stats.get("categories_existing", 0)),
        "event_types": _group(**types, unchanged=datamodel_stats.get("event_types_unchanged", 0)),
        "patrol_types": _group(**by_kind["patrol_type"]),
        "universal_patrol_fields": "write" if pd_stats.get("schema_written") else "skip" if pd_stats.get("schema_skipped") else "merge",
        "choices": _group(**by_kind["choice"]),
        "subjects": _group(**by_kind["subject"]),
        "roster": {"group": roster_group, "add": pd_stats.get("subjects_grouped", 0)},
        "patrols": {"total": len(patrols), "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                    "already_done": len(ledger_done), "events": counts.get("observations", 0),
                    "track_points": counts.get("track_points", 0)},
    }
