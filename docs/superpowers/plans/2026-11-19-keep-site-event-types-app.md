# Keep the Site's Event Types (app) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A load leaves the event types and dropdown options a site already has as they are unless the operator asks for an update from SMART, and the plan names every event type that differs.

**Architecture:** A load option, `existing_event_types` (`keep` or `update`). For `keep` the load job pushes the data model in the library's `create-only` mode. The library's stats carry a list of the site's event types that differ from the model; the job takes the list out of the stats, puts it in the plan and turns it into one of two warnings.

**Tech Stack:** Python 3.12, FastAPI, plain JavaScript, pytest, `node --test`. Tests: `.venv/bin/python -m pytest -q` (398 passed, 2 skipped before this change), `node --test "tests/js/*.test.js"` (126). The end-to-end load tests need the library: `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py` (the library checkout installed editable; rebuild it as `web/DEPLOY.md`, "Running locally", says if it is gone).

**Spec:** `docs/superpowers/specs/2026-11-19-keep-site-event-types-design.md`. Ticket GUNDI-5949.

**Depends on:** the library's plan, `docs/superpowers/plans/2026-11-19-create-only-choices.md` in `PADAS/earthranger-smart-utils` (local checkout `/Users/chrisdo/padas/earthranger-smart-utils`). Task 1 here needs nothing from it. Tasks 2 and 3 need its code to test against and its release tag to pin.

## Global Constraints

- `options.existing_event_types`: `"keep"` or `"update"`. Absent or null on create: `"keep"`. Anything else: `400 existing_event_types_invalid`. A stored load without the key reads and runs as `"update"`.
- `keep` → `push_datamodel_files(..., mode="create-only", additive=True)`; `update` → as today (`additive=True`, default mode).
- The differences list (`datamodel_stats["event_type_differences"]`) is removed from the stats before they are logged or stored with the stage. It reaches only the plan.
- Both new findings are warnings and appear in a plan only. `FINDING_KEYS` goes from 33 to 35.
- The site token is never written to Firestore, logs, `log_tail`, any API response, rendered HTML, or any file under `web-data/` except `web-data/secrets/`.
- No real conservation area's rangers, customer host or token in tests, docs or commits; `example.pamdas.org` only.
- New interface text goes in all five locale files (`en`, `fr`, `es`, `pt`, `sw`) and follows `docs/translation-glossary.md`; help pages change in all five languages, with code spans unchanged across languages.
- The pinned library version is the tag the user chooses. Do not tag either repository.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Review Focus

1. **A load planned before this release and run after it.** No option stored: it runs as `update`, and its page says so. (Task 1)
2. **A `keep` load into an empty site.** Everything is created; no difference, no warning. (Task 2)
3. **A `keep` load whose model has an event type the site lacks.** It is created, in the set's category. (Task 3)
4. **Hundreds of differing event types.** The plan's list is capped with a count of the rest; the stage's stored stats and the log carry none of it. (Task 2)
5. **A difference with no field on either side** (`other` or `name` only). Listed in the plan; counted by `event_types_overwritten`; not by `event_types_missing_fields`. (Task 2)

---

### Task 1: The option, from the form to the load

**Files:**
- Modify: `web/app.py` (`create_load`, `_load_public`), `web/static/app.js` (the load dialog), `web/static/pages.js` (`loadFacts`), `web/static/locales/{en,fr,es,pt,sw}.json`
- Test: the file that tests `create_load` (where `event_type_set_invalid` is tested), `tests/js/` (the file that tests the load's option line)

**Interfaces:**
- Produces, the API: `options.existing_event_types` as in Global Constraints. `create_load` stores `"keep"` or `"update"`; `_load_public`'s defaults give `"update"` to a load document without the key.
- Produces, the client: a select `#ldExisting` in the load dialog, after the event category, always shown, values `keep` (selected) and `update`, with a hint under it; kept when the dialog is drawn again (the `ids` list); sent as `existing_event_types`. `loadFacts` shows one of two lines.
- Message keys: `loadDialog.existing` ("Event types already on the site"), `loadDialog.existingKeep` ("Leave them as they are"), `loadDialog.existingUpdate` ("Update them from SMART"), `loadDialog.existingHint` ("The load always creates event types and dropdown options the site lacks. Updating replaces the name and fields of an event type that differs from SMART, which removes fields added on the site."), `load.existingKeep` ("existing event types kept"), `load.existingUpdate` ("existing event types updated from SMART"), `errors.existing_event_types_invalid`.

- [ ] **Step 1: Write the failing tests.** `create_load`: no option stores `keep`; `null` stores `keep`; `update` is stored; `"merge"` and `1` are `400 existing_event_types_invalid` (the error body is `{"detail","code","values"}`); a load document written without the key comes back from the API with `update`. Client: the option line of a load with `keep` includes `load.existingKeep`'s text, with `update` the other.

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q -k existing_event_types`
Expected: FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run both suites**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/app.py web/static tests
git commit -m "Loads: a choice to keep the event types the site has, or update them from SMART"
```

---

### Task 2: The job keeps or updates, and the plan says which differ

**Files:**
- Modify: `web/load_job.py` (`ErSmartSyncMigration.push_datamodel`, the datamodel stage of the runner, both `build_plan` calls), `web/findings.py` (`FINDING_KEYS`, `shared_set_changes`, two new findings, `build_plan`), `web/static/pages.js` (the plan's event types group near line 543; the stage tally near line 444 gains `skipped_by_mode` for choices), `web/static/locales/{en,fr,es,pt,sw}.json`, `web/help/05-stops.md` and its four copies, `web/requirements-load.txt`
- Test: `tests/test_findings.py`, `tests/test_load_e2e.py`, `tests/js/` (the file that tests the plan page)

**Interfaces:**
- Consumes, from the library: `mode="create-only"`; `datamodel_stats["event_type_differences"]`, a list of `{"value","display","name","active","site_only","smart_only","changed","other"}`; `datamodel_stats["choices_skipped_by_mode"]`.
- Produces, `ErSmartSyncMigration`: `existing: str` (`options.get("existing_event_types") or "update"`); `push_datamodel() -> dict` passes `mode="create-only"` when `existing == "keep"`, pops `event_type_differences` from the stats into `self.differences: list` and returns the stats without it.
- Produces, `web/findings.py`:
  - `event_types_overwritten(differences: list) -> dict | None`: code `event_types_overwritten`, key `datamodel.event_types_overwritten`, stage `datamodel`, severity `warning`, `values` every differing event type's value. English title "This load replaces event types the site has changed"; detail `f"Event types that differ from SMART: {n}. Of those, with fields SMART lacks: {m}."`; fix "Each one gets SMART's name and fields, and fields added on the site are removed. To keep them, make a new plan with 'Leave them as they are'." `None` for an empty list.
  - `event_types_missing_fields(differences: list) -> dict | None`: code `event_types_missing_fields`, key `datamodel.event_types_missing_fields`, same stage and severity, `values` the event types whose `smart_only` is not empty. Title "Event types on the site lack fields this conservation area records"; detail `f"Event types: {n}. Fields: {total of smart_only}."`; fix "Add the fields to these event types on the site, or make a new plan with 'Update them from SMART'." `None` when no entry has `smart_only`.
  - `shared_set_changes(*, datamodel_stats: dict) -> dict | None`: fires when the set was on the site (the sum it uses today) and `choices_created` is not 0; no `values`; title "This load adds dropdown options to lists the site already has"; detail `f"Dropdown options it adds: {added}."`; fix "Other conservation areas loaded into this site share these lists. Nothing is deactivated. To keep this area's model apart, make a new plan with another event type set name."
  - `build_plan(..., differences=(), existing="update")`: `plan["event_types"]["differ"]` is the differences as `{"value", "label" (the site's display), "name", "active", "site_only", "smart_only", "changed", "other"}`, capped through `_group` as the other lists are; `plan["existing_event_types"] = existing`.
- The runner, in a plan: appends `event_types_overwritten(m.differences)` when `m.existing == "update"`, else `event_types_missing_fields(m.differences)`; then `shared_set_changes` as today.
- Produces, the plan page: under the event types group, a list headed `plan.differKept` ("Differ from SMART and are left as they are") or `plan.differUpdated` ("Differ from SMART and get SMART's name and fields"), one line per event type with the parts that apply: `plan.diffName` ("name"), `plan.diffActive` ("active or not"), `plan.diffSiteOnly` ("only on the site: {fields}"), `plan.diffSmartOnly` ("only in SMART: {fields}"), `plan.diffChanged` ("changed: {fields}"), `plan.diffOther` ("layout or settings"). Every value goes through `esc`.
- Message keys also: `findingText.datamodel.event_types_overwritten`, `findingText.datamodel.event_types_missing_fields`, the rewritten `findingText.datamodel.shared_set_changes`, in the form the other findings use.
- Help, `05-stops.md` in five languages: `### This load replaces event types the site has changed {#finding-event_types_overwritten}`, `### Event types on the site lack fields this conservation area records {#finding-event_types_missing_fields}`, and the rewritten `#finding-shared_set_changes` section (the findings tests check that every key has its anchor).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_findings.py
D = [{"value": "p_a", "display": "A", "name": False, "active": False, "site_only": ["note"], "smart_only": [], "changed": [], "other": False},
     {"value": "p_b", "display": "B", "name": True, "active": False, "site_only": [], "smart_only": ["x", "y"], "changed": [], "other": False}]

def test_overwritten_names_every_differing_event_type():
    f = F.event_types_overwritten(D)
    assert f["values"] == ["p_a", "p_b"] and f["severity"] == "warning" and not F.has_blocking([f])
    assert "2" in f["detail"] and "1" in f["detail"]
    assert F.event_types_overwritten([]) is None

def test_missing_fields_names_only_those_smart_has_more_of():
    f = F.event_types_missing_fields(D)
    assert f["values"] == ["p_b"] and not F.has_blocking([f])
    assert F.event_types_missing_fields(D[:1]) is None

def test_shared_set_changes_is_about_options_only():
    assert F.shared_set_changes(datamodel_stats={"event_types_on_site": 3, "choices_created": 0, "event_types_updated": 2}) is None
    assert F.shared_set_changes(datamodel_stats={"event_types_on_site": 3, "choices_created": 4})["values"] in ([], None)
    assert F.shared_set_changes(datamodel_stats={"choices_created": 4}) is None

def test_the_plan_carries_the_differences():
    # build_plan(..., differences=D, existing="keep"): plan["event_types"]["differ"][0] has value "p_a",
    # label "A", site_only ["note"]; plan["existing_event_types"] == "keep";
    # LIST_CAP + 3 differences: the list is LIST_CAP long and plan["event_types"]["more"]["differ"] == 3
```

Update the count test to 35 keys. In `tests/test_load_e2e.py`, with `_migration`, `_export` and `FakeSite`:

```python
def _add_field(site, value, key="site_note"):
    # add a string property `key` to the stored event type's schema json.properties

@pytest.mark.parametrize("existing", ["keep", "update"])
def test_the_plan_names_an_event_type_changed_on_the_site(smart_parquet, tmp_path, load_job, existing):
    # push the export for real; _add_field on one event type; a dry-run migration with existing_event_types=existing:
    #  - stats = m.push_datamodel(): "event_type_differences" not in stats
    #  - m.differences has one entry, that value, site_only == ["site_note"]
    #  - keep: no patch_event_type in m.dry_calls; update: one, for that value

def test_a_plan_through_the_job_warns_by_the_loads_choice(smart_parquet, tmp_path, monkeypatch):
    # through LoadJob as test_the_job_records_the_set_and_its_category does, into a site prepared as above:
    #  - update: findings include event_types_overwritten with that value, not event_types_missing_fields
    #  - keep: neither (the site has a field more, SMART none)
    #  - keep, with a model property removed from the site's event type instead: event_types_missing_fields
    #  - plan["event_types"]["differ"] has the entry; plan["existing_event_types"] is the choice
    #  - the load document's datamodel stage stats and its log_tail do not contain "event_type_differences" or "site_note"

def test_a_keep_plan_into_an_empty_site_has_no_difference(smart_parquet, tmp_path, load_job):
    # m.differences == [] and every event type is in the post_event_type calls
```

Adjust `test_the_plan_warns_when_a_shared_set_would_change` to the new signature and meaning (options added, not event types updated). Client: a plan with one `differ` entry renders its value, the heading for the plan's `existing_event_types`, and "site_note".

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_findings.py -k "overwritten or missing_fields or options_only or carries_the_differences"`
Expected: FAIL (`findings` has no `event_types_overwritten`)

- [ ] **Step 3: Implement**, and pin the library's new tag in `web/requirements-load.txt`.

- [ ] **Step 4: Run every way**

Run: `.venv/bin/python -m pytest -q`, `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py`, `node --test "tests/js/*.test.js"`
Expected: PASS in all three

- [ ] **Step 5: Commit**

```bash
git add web tests
git commit -m "Load job: keep the site's event types or update them, and the plan names the ones that differ"
```

---

### Task 3: A field added on the site survives a load; and say so

**Files:**
- Modify: `web/help/03-loading.md` and its `es`, `fr`, `pt`, `sw` copies, `docs/decisions.md`
- Test: `tests/test_load_e2e.py`

**Interfaces:**
- Consumes: Task 2's migration and `_add_field`.

- [ ] **Step 1: Write the test.**

```python
def test_a_field_added_on_the_site_is_still_there_after_a_keep_load(smart_parquet, tmp_path, load_job):
    # area A pushed for real. On the site: _add_field on one event type, change one option's display,
    # deactivate one event type and one option.
    # area B (_another_area(..., differs=True): one option more, another conservation area) pushed for real with keep:
    #  - the added field is in the event type's schema; the option's display is the site's;
    #    the event type and the option are still inactive
    #  - B's new option exists; an event type deleted from the site before B's push exists again

def test_an_update_load_removes_it(smart_parquet, tmp_path, load_job):
    # the same site, existing_event_types="update": the field is gone and the display is SMART's
```

Run the first against `push_datamodel` with the `mode` argument commented out once, locally, and confirm it fails, so the test is known to catch today's behaviour; restore the argument.

- [ ] **Step 2: Run**

Run: `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py`
Expected: PASS

- [ ] **Step 3: Write it down.**
  - `web/help/03-loading.md`, in all five languages, a section "Changes made on the site" after "Several conservation areas in one site": the two choices and that "Leave them as they are" is chosen; what a load never touches under it (an existing event type's name, fields and active state; an existing option's text, order and active state) and what it still creates; when to choose an update (the SMART model itself changed) and what it costs (fields added on the site are removed); that the plan lists every event type that differs, with the fields on each side; that the choice does not cover patrol types or the universal patrol fields. Correct the sentence in "Several conservation areas in one site" that says a later load writes this area's name and fields over a differing event type: now only with an update.
  - `docs/decisions.md`: the decision, in that file's style: keep by default; why not a merge (the push cannot tell a field added on the site from one removed in SMART); why no patrols-only load; that loads made before run as updates; that whether a site accepts an event with a field its event type lacks is not established and is checked by hand.

- [ ] **Step 4: Run everything and build the site**

Run: `.venv/bin/python -m pytest -q`, `node --test "tests/js/*.test.js"`, and the site build the repository's checks already run
Expected: PASS; the help pages build in five languages

- [ ] **Step 5: Commit**

```bash
git add web/help docs tests
git commit -m "Keeping site edits: the test of the ticket, the help page and the decision"
```

---

## After the tasks: a check by hand

Not a task for an agent to run unprompted, because it writes to a site: with the user's go-ahead and a test site of their choosing, add a field to a migrated event type, load with "Leave them as they are" and confirm the field is still there; then import one event whose details carry a key the site's event type lacks and record what the site does. If the site refuses the event, `event_types_missing_fields` becomes blocking. Record the result in the pull request.
