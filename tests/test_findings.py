"""Findings and the plan are data the UI renders; the job only assembles them."""
from __future__ import annotations

import importlib
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
                      "fix": "Django admin > Teams.\nRe-run.", "affected": {"count": 0, "patrols": []}}
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
               {"kind": "choice", "action": "updated", "value": "law", "id": "c1", "before": {}},
               {"kind": "subject", "action": "created", "id": "s1", "value": "Ana Cruz"},
               {"kind": "subject", "action": "deactivated", "id": "s2"},
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
    assert plan["patrol_types"] == {"create": [{"value": "patrol_foot", "label": "patrol_foot"}], "update": []}
    assert plan["choices"]["update"] == [{"value": "law", "label": "law"}]
    assert plan["subjects"] == {"create": [{"value": "s1", "label": "Ana Cruz"}], "update": [],
                                "deactivate": [{"value": "s2", "label": "s2"}]}
    assert plan["universal_patrol_fields"] == "write" and plan["roster"] == {"group": "Rangers", "add": 2}
    assert plan["patrols"] == {"total": 2, "first": "2019-03-04", "last": "2024-11-30", "already_done": 1,
                               "events": 10, "track_points": 400}


def test_build_plan_caps_long_lists(findings):
    calls = [("post_event_type", ({"value": f"t{i}", "display": f"T{i}"},), {}) for i in range(250)]
    plan = findings.build_plan(datamodel_stats={}, dry_calls=calls, pd_changes=[], pd_stats={}, roster_group=None,
                               patrols=[], ledger_done=set(), counts={})
    assert len(plan["event_types"]["create"]) == 200 and plan["event_types"]["more"] == 50
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
