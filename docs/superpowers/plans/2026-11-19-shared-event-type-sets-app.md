# Shared Event Type Sets (app) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conservation areas whose configurable models have one name share one set of event types and choice lists on a site, and a load never takes away what another area's load put there.

**Architecture:** A load gets a set name (the configurable model's name unless the operator changes it). A key derived from that name takes the place of the model's own uuid in every event type value and choice list name, so two areas' copies of one model write the same set. The load job checks the site for a set written under the old uuid and keeps using it if there is one. Every push is additive (the library's new mode).

**Tech Stack:** Python 3.12, FastAPI, plain JavaScript, pytest, `node --test`. Tests: `.venv/bin/python -m pytest -q` (391 passed, 2 skipped before this change), `node --test "tests/js/*.test.js"` (126). The end-to-end load tests need the library: `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py` (the library checkout installed editable; rebuild it as `web/DEPLOY.md`, "Running locally", says if it is gone).

**Spec:** `docs/superpowers/specs/2026-11-19-shared-event-type-sets-design.md`. Ticket GUNDI-5946.

**Depends on:** the library's plan, `docs/superpowers/plans/2026-11-19-additive-push.md` in `PADAS/earthranger-smart-utils` (local checkout `/Users/chrisdo/padas/earthranger-smart-utils`). Task 1 here needs nothing from it. Tasks 2 and 3 need its code to test against and its release tag to pin.

## Global Constraints

- Set name: 1 to 60 characters after trimming. Only a load with a configurable model has one; its default is that model's `label` in the dataset's export entry.
- Key: `uuid.uuid5(SET_NAMESPACE, normalised).hex`, where `normalised` is the name after Unicode NFKC, `casefold()`, runs of white space made one space, and `strip()`. `SET_NAMESPACE = uuid.UUID("6f0b1a52-7c3e-5d0a-9a41-2e5d8c7b4f10")`, a constant that must never change.
- Prefix: `smart-ca-import_<key>` with a set name; `smart-ca-import` without. The old prefix is `smart-ca-import_<the model's own uuid>`, the uuid written as the export entry has it.
- A site that has any event type (active or not) whose value starts with the old prefix followed by `_` keeps the old prefix for that load.
- The model's own uuid still selects `configurable_model_<uuid>.xml`.
- Default event category: with a set name, `smart-<set name>` made safe by `findings.ca_identifier`'s rule (lower case, runs of other characters to `-`, 2 to 30 characters); without, `smart-<conservation area id>` as today.
- Every push the load job makes passes `additive=True`.
- The site token is never written to Firestore, logs, `log_tail`, any API response, rendered HTML, or any file under `web-data/` except `web-data/secrets/`.
- No real conservation area's rangers, customer host or token in tests, docs or commits; `example.pamdas.org` only. The model name "R05 Lawin" and the two local Region 5 exports stay out of the repository.
- New interface text goes in all five locale files (`en`, `fr`, `es`, `pt`, `sw`) and follows `docs/translation-glossary.md`; help pages change in all five languages.
- The pinned library version is the tag the user chooses. Do not tag either repository.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Review Focus

1. **A load created before this change and continued after it.** Its options have no set name; it gets the model's name, and the old-prefix check keeps it on the event types it already wrote. (Task 2)
2. **Names that differ only in case, spacing or Unicode form** ("R05  Lawin", "r05 lawin", a full-width digit). One key. (Task 1)
3. **A set name sent without a configurable model.** Refused, not ignored. (Task 1)
4. **The old-prefix check in a plan.** It is a read, so a plan makes it and reports the same prefix the run will use. (Task 2)
5. **Two areas loaded into one site in either order.** One set, and the first area's event types, categories and active options are as they were. (Task 3)

---

### Task 1: The set name, from the form to the load

**Files:**
- Modify: `web/findings.py` (the key and the category default live beside `ca_identifier`, which the service and the job both import), `web/app.py` (`create_load`, the load's default options), `web/static/app.js` (the load dialog), `web/static/pages.js` (the load's option line), `web/static/locales/{en,fr,es,pt,sw}.json`
- Test: `tests/test_findings.py`, `tests/test_web_loads.py` (or the file that already tests `create_load`), `tests/js/` (the file that tests the load's option line)

**Interfaces:**
- Produces, `web/findings.py`:
  - `SET_NAMESPACE`, `SET_NAME_MAX = 60`
  - `set_key(name: str) -> str` (32 hex characters)
  - `set_prefix(name: str | None) -> str`
  - `set_category(name: str) -> str` (the default event category for a set name)
- Produces, the API: `options.event_type_set` on `POST /api/datasets/{id}/loads`. Absent, null or blank with a configurable model: the model's label. Present without a configurable model: `400 set_without_model`. Not a string, or over 60 characters after trimming: `400 event_type_set_invalid`. Stored trimmed in the load's options; `null` for a load without a configurable model. When the event category is not given and the load has a set name, the category is `set_category(name)`.
- Produces, the client: a text field `#ldSet` in the load dialog, shown only while a configurable model is chosen, filled with that model's label each time the choice changes, with a hint; its value sent as `event_type_set`. While it is shown and the operator has not typed in the category field, the category placeholder follows the set name. The load's option line shows the set name. Message keys: `loadDialog.eventTypeSet`, `loadDialog.eventTypeSetHint`, `load.eventTypeSet`, `errors.set_without_model`, `errors.event_type_set_invalid`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_findings.py
def test_one_name_one_key():
    assert F.set_key("R5 Model") == F.set_key("  r5   model ") == F.set_key("Ｒ５ Model")
    assert F.set_key("R5 Model") != F.set_key("R6 Model")
    assert len(F.set_key("R5 Model")) == 32 and int(F.set_key("R5 Model"), 16) >= 0

def test_the_key_is_pinned():
    # the namespace must never change: a changed key orphans every set already on a site
    assert F.set_key("R5 Model") == "<the value computed once in Step 3 and pasted here>"

def test_the_prefix():
    assert F.set_prefix(None) == "smart-ca-import"
    assert F.set_prefix("R5 Model") == "smart-ca-import_" + F.set_key("R5 Model")

def test_the_default_category_of_a_set():
    assert F.set_category("R5 Model") == "smart-r5-model"
    assert F.EVENT_CATEGORY.fullmatch(F.set_category("A very long configurable model name indeed"))
    assert F.EVENT_CATEGORY.fullmatch(F.set_category("模型"))
```

For `create_load` (in the style of the tests already there): a load with a configurable model and no set name stores the model's label and the category `set_category(label)`; a given set name is stored trimmed; a set name without a model is `400 set_without_model`; 61 characters is `400 event_type_set_invalid`; a given event category still wins; a load without a model stores `event_type_set: None` and the category of today.

For the client: the option line of a load whose options carry `event_type_set` includes it.

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_findings.py -k "key or prefix or category_of_a_set"`
Expected: FAIL (`findings` has no `set_key`)

- [ ] **Step 3: Implement.** Compute `set_key("R5 Model")` once and paste it into the pinned test. Hint text, in English: "Conservation areas loaded with the same name share one set of event types and dropdown lists on the site. Change it to keep this model's apart."

- [ ] **Step 4: Run both suites**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/findings.py web/app.py web/static tests
git commit -m "Loads: a set name, so areas with one configurable model share its event types"
```

---

### Task 2: The load job writes the shared set

**Files:**
- Modify: `web/load_job.py` (`ErSmartSyncMigration`, the datamodel stage of the job, the plan), `web/findings.py` (`build_plan`, the new finding), `web/static/pages.js` (the load page: the set, its category, the old-set note), `web/static/locales/{en,fr,es,pt,sw}.json`, `web/requirements-load.txt`
- Create: `tests/fake_site.py` (a test helper: an in-memory stand-in for the ER client that keeps event categories, version 2 event types and choices, and answers the reads and writes a data model push makes)
- Test: `tests/test_load_e2e.py`, `tests/test_load_job.py`, `tests/test_findings.py`

**Interfaces:**
- Consumes, from the library: `push_datamodel_files(..., additive=True)`; its stats carry `"event_category": str`. From Task 1: `F.set_key`, `F.set_prefix`.
- Produces, `ErSmartSyncMigration`:
  - `set_name: str | None`: `options["event_type_set"]`, else the model's label read from the export's `datamodel.json` (`configurable_models[].label` for the chosen uuid), else `None` without a model.
  - `resolve_set() -> dict`: called once by the job before `push_datamodel`. Lists the site's event types (inactive included); if any value starts with `smart-ca-import_<model uuid>_`, the load is on the old set. Returns and keeps `{"name": str | None, "prefix": str, "old": bool}`, and sets `self.event_type_prefix` and the key `push_datamodel` passes as `cm_uuid`. Without a model: `{"name": None, "prefix": "smart-ca-import", "old": False}` and no read.
  - `push_datamodel()` passes `additive=True` and the resolved key.
  - `self.event_type_prefix` is not set in `__init__` any more; `preflight` and the import read it after `resolve_set`.
- Produces, the load document: `event_type_set: {"name", "prefix", "old", "category"}`, written when the datamodel stage ends (`category` from the push's stats); the plan carries the same under `plan["event_type_set"]`.
- Produces, `web/findings.py`: `shared_set_changes(*, updated: list[str], options_added: int) -> dict | None`: a warning finding with code `shared_set_changes`, stage `datamodel`, the event type values in `values`; `None` when there is nothing to report. The job adds it in a plan when the set was already on the site (the push's stats show at least one event type unchanged or updated) and the dry run plans an event type update or a choice creation.
- Produces, the load page: a line naming the set and the event category its event types are in; when `old` is true, a note that this conservation area was loaded before sets were shared and keeps its own event types. Message keys: `load.set`, `load.setCategory`, `load.oldSet`, and the finding's `findings.datamodel.shared_set_changes.{title_one,title_other,detail,fix}` in the form the other findings use.

- [ ] **Step 1: Write the failing tests.** With a bundle and configurable model exported from the `smart_parquet` fixture (find how `tests/test_load_e2e.py` already gets an export with a model; if the fixture has none, add one to the fixture's data, not a real one):

```python
def test_two_copies_of_one_model_write_one_prefix(...):
    # the same export twice, the second with its configurable model's uuid changed (file renamed, uuid in
    # datamodel.json changed) and the same label: both migrations resolve the same prefix, which is
    # F.set_prefix(label) and contains neither uuid

def test_a_site_with_the_old_set_keeps_it(...):
    # FakeSite holding one event type "smart-ca-import_<model uuid>_x": resolve_set() gives old=True and the
    # old prefix; push_datamodel is called with the model's own uuid; the plan's event_type_set says old

def test_a_load_made_before_set_names_gets_the_models_label(...):
    # options without "event_type_set": set_name is the label from datamodel.json

def test_a_load_without_a_model_reads_nothing_to_resolve_its_set(...):
    # resolve_set() makes no call on the client

def test_the_job_records_the_set_and_its_category(...):
    # a plan through LoadJob: the load document's event_type_set has name, prefix, old False and the
    # category the push reported; plan["event_type_set"] is the same

def test_the_plan_warns_when_a_shared_set_would_change(...):
    # area A pushed for real into FakeSite; a plan of a second export whose model differs (one option
    # added, one category's schema changed): findings include shared_set_changes naming that event type;
    # a plan of an identical second export has no such finding; a plan into an empty site has none
```

In `tests/test_findings.py`: `shared_set_changes(updated=[], options_added=0) is None`; with values it is a warning that does not block (`F.has_blocking([f])` is false).

- [ ] **Step 2: Run and see them fail**

Run: `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py -k "prefix or old_set or set_names or resolve or records_the_set or shared_set"`
Expected: FAIL (`ErSmartSyncMigration` has no `resolve_set`)

- [ ] **Step 3: Implement**, and pin the library's new tag in `web/requirements-load.txt`.

- [ ] **Step 4: Run every way**

Run: `.venv/bin/python -m pytest -q`, `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py tests/test_load_job.py`, `node --test "tests/js/*.test.js"`
Expected: PASS in all three

- [ ] **Step 5: Commit**

```bash
git add web tests
git commit -m "Load job: a shared set's event types are keyed by its name, and a load only adds to them"
```

---

### Task 3: Two areas, one site; and say so

**Files:**
- Modify: `web/help/03-loading.md` and its `es`, `fr`, `pt`, `sw` copies, `docs/decisions.md`, `docs/translation-glossary.md` (the term chosen for "set")
- Test: `tests/test_load_e2e.py`

**Interfaces:**
- Consumes: `tests/fake_site.py` and the migrations of Task 2.

- [ ] **Step 1: Write the test.**

```python
@pytest.mark.parametrize("order", ["a_then_b", "b_then_a"])
def test_two_areas_share_one_set_and_take_nothing_from_each_other(..., order):
    # area A: the fixture's export. Area B: a copy with another model uuid, the same label, one option
    # removed from a list and one added, and another conservation area id.
    # push_datamodel for the first, record the site; push_datamodel for the second:
    #  - the site's event type values are the union of the two plans, each once, all under one prefix
    #  - every event type the first push made is still in its category and still active
    #  - every option the first push made active is still active
    #  - the site has one event category
```

Run it against the library without `additive` (comment the argument out once, locally) and confirm it fails, so the test is known to catch today's behaviour; restore the argument.

- [ ] **Step 2: Run**

Run: `/tmp/smart-able-venv-load/bin/python -m pytest -q tests/test_load_e2e.py`
Expected: PASS

- [ ] **Step 3: Write it down.**
  - `web/help/03-loading.md`, in all five languages: what a set is and what the set name does; that a later load of another area adds to the set and removes nothing; that an option or event type removed from SMART stays active on the site until an administrator turns it off; that an area loaded before this release keeps its own event types; the corrected "Event category" section (new event types join the category the set is already in).
  - `docs/decisions.md`: the decision, in that file's style: one set per configurable model name; why the name and not the uuid, with the measured figures (18 event types and 22 lists per area, unshared); why not content hashing and why not one national set; that old sets are left alone.

- [ ] **Step 4: Run everything and build the site**

Run: `.venv/bin/python -m pytest -q`, `node --test "tests/js/*.test.js"`, and the site build the repository's checks already run
Expected: PASS; the help pages build in five languages

- [ ] **Step 5: Commit**

```bash
git add web/help docs tests
git commit -m "Shared sets: two areas into one site, the help page and the decision"
```

---

## After the tasks: a check by hand

Not a task for an agent to run unprompted, because it writes to a site: with the user's go-ahead and a test site of their choosing, load the data model of the two local Region 5 areas with their configurable models, one after the other, and confirm the site has 18 event types and 22 choice lists after both. Record the result in the pull request.
