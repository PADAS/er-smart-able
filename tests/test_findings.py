"""Findings and the plan are data the UI renders; the job only assembles them."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def findings(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    sys.modules.pop("findings", None)
    return importlib.import_module("findings")


def test_checklist_items_become_findings_with_their_severity(findings):
    out = findings.from_checklist([
        {"code": "team", "title": "Create the patrol team Alpha", "steps": ["Django admin > Teams.", "Re-run."]},
        {"code": "patrol_type_icons", "title": "Pick icons", "steps": ["Admin > Patrol types."]}])
    assert out[0] == {"stage": "patrol_datamodel", "code": "team", "severity": "blocking",
                      "title": "Create the patrol team Alpha", "detail": "",
                      "fix": "Django admin > Teams.\nRe-run.", "affected": {"count": 0, "patrols": []}, "values": [],
                      "key": "checklist.team", "params": {"name": "Alpha"}}
    assert out[1]["severity"] == "warning"
    assert findings.has_blocking(out) and not findings.has_blocking(out[1:])


def test_preflight_findings_keep_their_patrols_capped(findings):
    many = [f"{i:032x}" for i in range(80)]
    out = findings.from_preflight({"blocking": [{"code": "team_missing", "level": "blocking", "message": "7 teams missing",
                                                 "fix": "Create them", "count": 7, "examples": ["A", "B"],
                                                 "affected_patrols": many}],
                                   "warnings": [{"code": "collection_type", "level": "warning", "message": "m", "fix": "f",
                                                 "count": 0, "examples": [], "affected_patrols": []}]})
    assert out[0]["stage"] == "preflight" and out[0]["severity"] == "blocking" and out[0]["title"] == "7 teams missing"
    assert out[0]["detail"] == "A\nB" and out[0]["affected"] == {"count": 80, "patrols": many[:50]}
    assert out[1]["severity"] == "warning"


def test_failed_patrols_become_one_blocking_finding(findings):
    out = findings.from_failed_patrols({"u1": "500 on track", "u2": "timeout"}, {"u1": "P-1", "u2": "P-2"})
    assert len(out) == 1 and out[0]["code"] == "patrols_failed" and out[0]["stage"] == "import"
    assert out[0]["title"] == "2 patrols failed to import" and "P-1: 500 on track" in out[0]["detail"]
    assert out[0]["affected"] == {"count": 2, "patrols": ["u1", "u2"]}


def test_token_rejected_is_a_blocking_finding(findings):
    f = findings.token_rejected("401 Unauthorized")
    assert f["severity"] == "blocking" and f["code"] == "site_token_rejected" and "register" in f["fix"].lower()


def test_build_plan_groups_dry_run_writes(findings):
    calls = [("post_event_category", ({"value": "smart-050500", "display": "Albay"},), {}),
             ("post_event_type", ({"value": "smart-ca-import_animals", "display": "Animals"},), {}),
             ("patch_event_type", ({"value": "smart-ca-import_threats", "display": "Threats"},), {}),
             ("get_event_types", (), {})]
    changes = [{"kind": "patrol_type", "action": "created", "value": "patrol_foot"},
               {"kind": "choice", "action": "updated", "value": "law", "id": "c1", "field": "smart_threat", "before": {}},
               {"kind": "choice", "action": "updated", "value": "old", "id": "c2", "field": "smart_threat", "before": {"is_active": True}},
               {"kind": "choice", "action": "created", "value": "foot", "field": "smart_threat", "id": None},
               {"kind": "patrol_type", "action": "updated", "value": "patrol_boat", "before": {"is_active": True}},
               {"kind": "subject", "action": "created", "id": "dry-run", "name": ""},
               {"kind": "subject", "action": "created", "id": "dry-run", "name": "Ana Cruz"},   # a plan's creates have no id
               {"kind": "subject", "action": "updated", "id": "s3", "name": "Carla Diaz", "before": {"name": "C. Diaz"}},
               {"kind": "subject", "action": "updated", "id": "s4", "name": None, "before": {"is_active": True}},
               {"kind": "subject", "action": "updated", "id": "s2", "name": "Old Login", "before": {"is_active": True}},
               {"kind": "universal_patrol_fields", "action": "written", "before_file": None}]
    plan = findings.build_plan(datamodel_stats={"event_types_unchanged": 5, "categories_existing": 1},
                               dry_calls=calls, pd_changes=changes,
                               pd_stats={"schema_written": True, "schema_skipped": None, "subjects_grouped": 2},
                               roster_group="Rangers",
                               patrols=[{"uuid": "a", "start_date": "2019-03-04"}, {"uuid": "b", "start_date": "2024-11-30"}],
                               ledger_done={"a"}, counts={"observations": 10, "track_points": 400})
    assert plan["event_categories"] == {"create": [{"value": "smart-050500", "label": "Albay"}], "update": [], "unchanged": 1}
    assert plan["event_types"]["create"] == [{"value": "smart-ca-import_animals", "label": "Animals"}]
    assert plan["event_types"]["update"] == [{"value": "smart-ca-import_threats", "label": "Threats"}]
    assert plan["event_types"]["unchanged"] == 5
    assert plan["patrol_types"] == {"create": [{"value": "patrol_foot", "label": "patrol_foot"}], "update": [],
                                    "deactivate": [{"value": "patrol_boat", "label": "patrol_boat"}]}
    assert plan["choices"] == {"create": [{"value": "smart_threat.foot", "label": "foot"}], "update": [{"value": "smart_threat.law", "label": "law"}],
                               "deactivate": [{"value": "smart_threat.old", "label": "old"}]}   # switching a choice off is shown
    assert plan["subjects"] == {"create": [{"value": None, "label": "(unnamed)"}, {"value": None, "label": "Ana Cruz"}],
                                "update": [{"value": "s3", "label": "Carla Diaz"}],
                                "deactivate": [{"value": "s4", "label": "s4"},   # a nameless subject is labelled by its id
                                               {"value": "s2", "label": "Old Login"}]}
    assert plan["universal_patrol_fields"] == "write" and plan["roster"] == {"group": "Rangers", "add": 2}
    assert plan["patrols"] == {"total": 2, "first": "2019-03-04", "last": "2024-11-30", "already_done": 1,
                               "events": 10, "track_points": 400}


def test_build_plan_caps_long_lists(findings):
    calls = [("post_event_type", ({"value": f"t{i}", "display": f"T{i}"},), {}) for i in range(250)]
    plan = findings.build_plan(datamodel_stats={}, dry_calls=calls, pd_changes=[], pd_stats={}, roster_group=None,
                               patrols=[], ledger_done=set(), counts={})
    assert len(plan["event_types"]["create"]) == 200 and plan["event_types"]["more"] == {"create": 50}   # per list
    assert plan["patrols"]["first"] is None


def test_failed_patrol_detail_is_capped(findings):
    failed = {f"u{i}": "x" * 2000 for i in range(250)}
    out = findings.from_failed_patrols(failed, {})
    lines = out[0]["detail"].split("\n")
    assert len(lines) == 201 and lines[-1] == "… and 50 more; see log.txt"
    assert all(len(line) <= 500 for line in lines)
    assert out[0]["affected"]["count"] == 250 and out[0]["title"] == "250 patrols failed to import"


def _pre(code, level="blocking", message="m"):
    return {"stage": "preflight", "code": code, "severity": level, "title": message}


def test_plan_mode_adjust_marks_what_the_run_creates(findings):
    given = [_pre("patrol_types", message="1 patrol type(s) the legs need are missing or inactive"),
             _pre("segment_schema"), _pre("subjects"), _pre("choices", "warning"),
             _pre("event_types", message="2 observed SMART categor(ies) have no active event type on the site"),
             _pre("event_types", message="3 categor(ies) match more than one event type (several data model pushes)"),
             _pre("event_types", message="1 observed categor(ies) exist only as configurable model variants"),
             _pre("teams"), _pre("permissions"), _pre("feature_flag"), _pre("timezone"), _pre("collection_type", "warning"),
             {"stage": "patrol_datamodel", "code": "team", "severity": "blocking", "title": "Create the patrol team A"}]
    out = findings.plan_mode_adjust(given)
    assert findings.CREATED_BY_RUN == {"event_types", "patrol_types", "segment_schema", "subjects", "choices"}
    assert [f["severity"] for f in out[:5]] == ["info"] * 5
    assert out[0]["title"] == "Will be created by this load: 1 patrol type(s) the legs need are missing or inactive"
    assert out[5:] == given[5:]          # ambiguous, variants and what a run cannot create stay
    assert given[0]["severity"] == "blocking"   # the input is not changed
    assert findings.has_blocking(out) and not findings.has_blocking(out[:5])


def test_ca_identifier_is_a_valid_event_category(findings):
    assert findings.ca_identifier("050500") == "smart-050500"
    assert findings.ca_identifier("A B/c") == "smart-a-b-c"
    assert findings.EVENT_CATEGORY.fullmatch(findings.ca_identifier("x" * 80))


def test_checklist_findings_carry_the_exact_values_to_type(findings):
    out = findings.from_checklist([
        {"code": "team", "title": "Create the patrol team SMART team 7097b461",
         "steps": ["Django admin > Patrol configuration > Teams > add a team with display `SMART team 7097b461`.",
                   "Members (from SMART): none recorded.", "Re-run `er-smart-sync patrol-datamodel`."]},
        {"code": "roster_group", "title": "Put the ranger subjects in the patrol roster subject group",
         "steps": ["Admin > member subject groups: choose or create the group (for example `Rangers`).",
                   "Add them to that group, or re-run with `--roster-group <name>` to let the tool do it."]},
        {"code": "permission_subjects", "title": "Grant", "steps": ["Django admin > Users > the operator > add `observations | subject | Can view/add/change subject`."]},
        {"code": "station_names", "title": "Name the stations", "steps": ["Rename `Unnamed station 0a1b2c3d`, `Unnamed station 4e5f6a7b` in admin > Choices (field `patrol_station`)."]},
        {"code": "patrol_type_icons", "title": "Pick icons", "steps": ["Admin > Patrol types."]},
        {"code": "permission_subject_group", "title": "Add the subjects to the `Rangers` subject group",
         "steps": ["The operator cannot change subject-group membership; an admin adds the subjects in Django admin > Subject groups."]},
        {"code": "team", "title": "Create the patrol team K9--Unit <North>",
         "steps": ["Django admin > Patrol configuration > Teams > add a team with display `K9--Unit <North>`."]}])
    assert out[0]["values"] == [{"label": "Team name", "value": "SMART team 7097b461", "label_key": "team_name"}]
    assert out[1]["values"] == []   # `Rangers` there is an example, not the name to use
    assert out[2]["values"] == [{"label": "Permission", "value": "observations | subject | Can view/add/change subject", "label_key": "permission"}]
    assert out[3]["values"] == [{"label": "Station name", "value": "Unnamed station 0a1b2c3d", "label_key": "station_name"},
                                {"label": "Station name", "value": "Unnamed station 4e5f6a7b", "label_key": "station_name"}]
    assert out[4]["values"] == []
    assert out[5]["values"] == [{"label": "Subject group", "value": "Rangers", "label_key": "subject_group"}]
    assert out[6]["values"] == [{"label": "Team name", "value": "K9--Unit <North>", "label_key": "team_name"}]   # odd characters are still a name


def test_preflight_team_findings_name_each_team(findings):
    out = findings.from_preflight({"blocking": [
        {"code": "teams", "level": "blocking", "message": "2 patrol team(s) are missing or inactive", "fix": "f", "count": 2,
         "examples": ["SMART team 7097b461 (missing, 52 patrols)", "Night shift (inactive, 3 patrols)"], "affected_patrols": []},
        {"code": "event_types", "level": "blocking", "message": "m", "fix": "f", "count": 1, "examples": ["x"], "affected_patrols": []}],
        "warnings": []})
    assert out[0]["values"] == [{"label": "Team name", "value": "SMART team 7097b461", "label_key": "team_name"}, {"label": "Team name", "value": "Night shift", "label_key": "team_name"}]
    assert out[1]["values"] == []


# ---- part 3: each finding names its message
PRE = lambda code, level, message, **kw: {"code": code, "level": level, "message": message, "fix": "x", "count": kw.pop("count", 2),
                                          "examples": kw.pop("examples", ["a", "b"]), "affected_patrols": [], **kw}


def test_every_finding_names_its_message_and_the_values_it_uses(findings):
    cl = findings.from_checklist([
        {"code": "team", "title": "Create the patrol team Alpha Team", "steps": ["add a team with display `Alpha Team`."]},
        {"code": "permission_subject_group", "title": "Add the subjects to the `Rangers` subject group", "steps": []},
        {"code": "roster_group", "title": "Put the ranger subjects in the patrol roster subject group", "steps": []}])
    assert [(f["key"], f["params"]) for f in cl] == [("checklist.team", {"name": "Alpha Team"}),
        ("checklist.permission_subject_group", {"group": "Rangers"}), ("checklist.roster_group", {})]
    assert cl[0]["values"] == [{"label": "Team name", "value": "Alpha Team", "label_key": "team_name"}]
    assert cl[0]["title"] == "Create the patrol team Alpha Team", "the stored English is untouched"
    pre = findings.from_preflight({"blocking": [PRE("patrol_types", "blocking", "2 patrol type(s) the legs need are missing or inactive")],
                                   "warnings": [PRE("leg_span", "warning", "3 leg(s) start on SMART's 1970-01-01 placeholder or span more than a year (41 leg days as stored)", count=3)]})
    assert (pre[0]["key"], pre[0]["params"]) == ("preflight.patrol_types", {"count": 2})
    assert (pre[1]["key"], pre[1]["params"]) == ("preflight.leg_span", {"count": 3, "days": 41})
    assert findings.from_failed_patrols({"u1": "boom"}, {})[0]["key"] == "import.patrols_failed"
    assert findings.from_failed_patrols({"u1": "boom"}, {})[0]["params"] == {"count": 1}
    assert findings.token_rejected("401")["key"] == "datamodel.site_token_rejected"


@pytest.mark.parametrize("level, message, key", [
    ("blocking", "4 observed SMART categor(ies) have no active event type on the site", "preflight.event_types.unmatched"),
    ("blocking", "1 categor(ies) match more than one event type (several data model pushes on this site)", "preflight.event_types.ambiguous"),
    ("warning", "2 observed categor(ies) map to an inactive event type (a SMART parent or retired category)", "preflight.event_types.inactive"),
    ("blocking", "3 observed categor(ies) exist only as configurable model variants (one event type per form)", "preflight.event_types.variants"),
])
def test_the_four_event_type_findings_are_told_apart(findings, level, message, key):
    assert findings.from_preflight({"blocking": [PRE("event_types", level, message)]})[0]["key"] == key


def test_retired_and_stranded_members_are_told_apart(findings):
    f = findings.from_preflight({"warnings": [PRE("inactive_members", "warning", "2 patrol member(s) are retired (inactive subjects)")],
                                 "blocking": [PRE("inactive_members", "blocking", "1 retired member(s) are in no configured member group, so reactivating them would still leave them off the roster", count=1)]})
    assert {x["key"] for x in f} == {"preflight.inactive_members.retired", "preflight.inactive_members.stranded"}


def test_a_finding_the_rules_do_not_recognise_has_no_key(findings):
    f = findings.from_preflight({"blocking": [PRE("brand_new_code", "blocking", "something new"),
                                              PRE("event_types", "blocking", "reworded beyond recognition"),
                                              PRE("leg_span", "warning", "reworded, with no day count"),
                                              PRE("check_failed", "blocking", "check_teams could not run: KeyError: 'x'")]})
    assert [x["key"] for x in f] == [None, None, None, None] and all(x["params"] == {} for x in f)
    cl = findings.from_checklist([{"code": "team", "title": "A reworded team title", "steps": []}, {"code": "unheard_of", "title": "x", "steps": []}])
    assert [x["key"] for x in cl] == [None, None]


def test_every_key_the_module_can_emit_is_listed(findings):
    assert {"checklist.team", "preflight.event_types.unmatched", "preflight.inactive_members.stranded", "import.patrols_failed",
            "datamodel.site_token_rejected"} <= findings.FINDING_KEYS
    assert "preflight.check_failed" not in findings.FINDING_KEYS and len(findings.FINDING_KEYS) == 33


def test_a_plans_findings_for_what_the_run_creates_say_so(findings):
    pre = findings.from_preflight({"blocking": [PRE("patrol_types", "blocking", "2 patrol type(s) the legs need are missing or inactive"),
                                                PRE("teams", "blocking", "1 patrol team(s) are missing or inactive", count=1)]})
    out = findings.plan_mode_adjust(pre)
    assert out[0]["created_by_run"] is True and out[0]["severity"] == "info" and out[0]["key"] == "preflight.patrol_types"
    assert "created_by_run" not in out[1] and out[1]["severity"] == "blocking"


def test_only_the_inferred_timezone_finding_is_named(findings):
    f = findings.from_preflight({"warnings": [PRE("timezone", "warning", "the bundle's timezone Asia/Manila was inferred from waypoint positions")],
                                 "blocking": [PRE("timezone", "blocking", "timezone 'Asia/Tokyo' is configured but the bundle was written for 'Asia/Manila' (inferred)")]})
    by = {x["severity"]: (x["key"], x["params"]) for x in f}
    assert by == {"warning": ("preflight.timezone", {"zone": "Asia/Manila"}), "blocking": (None, {})}


def test_every_key_has_an_english_title_and_fix_and_no_message_is_left_over(findings):
    en = json.loads((ROOT / "web" / "static" / "locales" / "en.json").read_text())["findingText"]
    have = set()
    def walk(node, path):
        if any(k in node for k in ("title", "title_one", "title_other", "fix")):
            assert "fix" in node and ("title" in node or {"title_one", "title_other"} <= set(node)), path
            have.add(path)
        else:
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
    walk(en, "")
    assert have == set(findings.FINDING_KEYS)


def test_every_key_a_rule_assigns_is_one_the_module_lists(findings):
    cl = findings.from_checklist([{"code": c, "title": {"team": "Create the patrol team A", "permission_subject_group": "Add the subjects to the `A`b` subject group"}.get(c, "x"), "steps": []}
                                  for c in ("team", "permission_subject_group", *findings._CHECKLIST_PLAIN)])
    pre = findings.from_preflight({"blocking": [PRE(c, "blocking", "x") for c in findings._PREFLIGHT_COUNTED]
                                   + [PRE("event_types", "blocking", phrase) for phrase, _ in findings._EVENT_TYPE_VARIANTS]
                                   + [PRE("inactive_members", "blocking", "x"), PRE("leg_span", "warning", "x (3 leg days as stored)")],
                                   "warnings": [PRE("inactive_members", "warning", "x"), PRE("timezone", "warning", "the bundle's timezone Asia/Manila was inferred")]})
    keys = [f["key"] for f in cl + pre] + [findings.from_failed_patrols({"u": "e"}, {})[0]["key"], findings.token_rejected("x")["key"],
                                        findings.shared_set_changes(datamodel_stats={"event_types_unchanged": 1, "choices_created": 1}, dry_calls=[])["key"]]
    assert None not in keys and set(keys) == set(findings.FINDING_KEYS)
    assert cl[1]["params"] == {"group": "A`b"}, "the whole name between the outer backticks"


def test_one_set_name_one_key(findings):
    F = findings
    assert F.set_key("R5 Model") == F.set_key("  r5   model ") == F.set_key("Ｒ５ Model")
    assert F.set_key("R5 Model") != F.set_key("R6 Model")
    assert len(F.set_key("R5 Model")) == 32 and int(F.set_key("R5 Model"), 16) >= 0


def test_the_set_key_is_pinned(findings):
    # the namespace must never change: a changed key orphans every set already on a site
    assert findings.set_key("R5 Model") == "04768b84429f56a7a491f88351f55a03"


def test_the_set_prefix(findings):
    F = findings
    assert F.set_prefix(None) == "smart-ca-import"
    assert F.set_prefix("R5 Model") == "smart-ca-import_" + F.set_key("R5 Model")


def test_the_default_category_of_a_set(findings):
    F = findings
    assert F.set_category("R5 Model") == "smart-r5-model"
    for name in ("A very long configurable model name indeed", "模型", "-", "x"):
        assert F.EVENT_CATEGORY.fullmatch(F.set_category(name)), name


def test_a_plan_warns_only_when_a_set_already_on_the_site_would_change(findings):
    F = findings
    patch = ("patch_event_type", (), {"event_type": {"value": "smart-ca-import_k_fire", "display": "Fire"}})
    post = ("post_event_type", (), {"event_type": {"value": "smart-ca-import_k_new"}})
    on_site = {"event_types_unchanged": 3, "event_types_updated": 1, "choices_created": 2}
    f = F.shared_set_changes(datamodel_stats=on_site, dry_calls=[patch, post])
    assert f["severity"] == "warning" and not F.has_blocking([f]) and f["stage"] == "datamodel"
    assert f["values"] == ["smart-ca-import_k_fire"] and "changes: 1" in f["detail"] and "adds: 2" in f["detail"]
    # options added to a set the site has, with no event type changed
    assert F.shared_set_changes(datamodel_stats={"event_types_unchanged": 3, "choices_created": 2}, dry_calls=[])["values"] == []
    # the same model again: nothing would change
    assert F.shared_set_changes(datamodel_stats={"event_types_unchanged": 4, "choices_created": 0}, dry_calls=[]) is None
    # a set new to the site: everything is created, nothing is shared yet
    assert F.shared_set_changes(datamodel_stats={"event_types_created": 4, "choices_created": 9}, dry_calls=[post]) is None
