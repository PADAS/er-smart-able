# Support View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Named support addresses can see every dataset, site and load, read-only, and each such view is logged.

**Architecture:** A second, weaker permission, `can_view`, beside `can_read`. The loaders in `web/app.py` stay strict by default and accept `can_view` only where a read route passes `view=True`. Every dataset, site and load in a response says how the viewer reached it (`access`), and the page builders draw no controls for `"support"`.

**Tech Stack:** FastAPI (`web/app.py`, `web/auth.py`, `web/store.py`), plain JavaScript page builders (`web/static/pages.js`, `web/static/app.js`), pytest, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-18-support-view-design.md`

## Global Constraints

- `SUPPORT_EMAILS` holds whole addresses only, separated by spaces, commas or semicolons, compared lower-cased. Unset or empty: nobody is support. An entry starting with `@` is ignored.
- A support address must still pass `ALLOWED_EMAILS`.
- The role is computed on every request; nothing about it is stored in the session, Firestore or a cookie.
- No route that writes changes its check. `_load`, `_load_site` and `_load_load` default to `can_read`.
- A site token is never written to Firestore, logs, an API response, rendered HTML, or any file outside `web-data/secrets/`. The record line holds no token, file contents or ranger name.
- Someone who is neither a reader nor support gets 404 on a dataset, site or load, as today.
- All text in `pages.js` is made with `T`, `t` or `tn`; a new phrase goes in `en.json` first, then `fr`, `es`, `pt`, `sw`.
- When an English help or guide page changes, its four translations change in the same commit, with the same steps, notes, links and code spans.
- Tests: `/Users/chrisdo/padas/er-smart-able/.venv/bin/python -m pytest -q` and `node --test "tests/js/*.test.js"`. Site build: `.venv/bin/python scripts/build_pages.py`.
- Local runs listen on `127.0.0.1:8090` only.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Review Focus

1. **A support user who also owns a dataset, or is in its `shared_with`.** They keep full owner or reader rights on it; `access` is `"owner"` or `"shared"`, not `"support"`; no record line is written. (Task 1, Task 2)
2. **`?all=1` from an ordinary user.** They get exactly their usual list, with status 200. (Task 1)
3. **A sloppy `SUPPORT_EMAILS`:** mixed case, an `@domain` entry, doubled separators, a trailing comma. Only whole addresses count. (Task 1)
4. **A dataset or load page left open, polling.** One record line per viewer, kind and id in ten minutes, not one per poll. (Task 2)
5. **A load whose site was removed, or a dataset that failed, seen through support view.** The page still draws, with the support line, the stored error and log, and no Delete, Run or Plan again. (Task 3)

---

### Task 1: The role, `can_view`, and the read routes

**Files:**
- Modify: `web/auth.py`, `web/store.py`, `web/app.py`
- Test: `tests/test_web_support.py` (create), `tests/test_auth.py`

**Interfaces:**
- Produces, `web/auth.py`:
  - `SUPPORT_EMAILS: str` from the environment, default `""`
  - `support_entries() -> list[str]`: lower-cased whole addresses; `@` entries dropped
  - `is_support(email: str) -> bool`
  - the user dict from `_dev_user` and `_from_decoded` gains `"support": bool`; `GET /api/me` returns it
  - at import, one `logger.warning` naming how many `@` entries were ignored (the count only)
- Produces, `web/store.py`:
  - `can_view(doc: dict, user: dict) -> bool`: `can_read(doc, user) or bool(user.get("support"))`
  - `access(doc: dict, user: dict) -> str | None`: `"owner"`, `"shared"`, `"support"`, or `None`, in that order of precedence
- Produces, `web/app.py`:
  - `_load(id, user, owner=False, view=False)` and `_load_load(id, user, view=False)`; `view=True` checks `can_view`
  - `GET /api/datasets` and `GET /api/sites` take the query parameter `all` (declare it as `everyone: bool = Query(False, alias="all")`); it applies only when `user["support"]`
  - `_public` and `_site_public` add `"access"`; `_site_public` leaves out `token_hint` when access is `"support"`
  - `_load_public` adds `"access"`: `"support"` when the viewer's access to the load's dataset is `"support"`, else `"owner"` if they own the load, else `"shared"`
  - `GET /api/datasets/{id}` returns `log_tail` to the owner and to support

Routes that pass `view=True`: `get_dataset`, `list_loads`, `get_load`, `load_file`, `site_index`, `site_file`. No other route does.

- [ ] **Step 1: Write the failing tests for the role** in `tests/test_auth.py` (follow that file's way of re-importing `auth` with an environment):

```python
def test_support_is_whole_addresses_only(monkeypatch):
    auth = _auth(monkeypatch, SUPPORT_EMAILS="Sup@EarthRanger.com,, @earthranger.com ; two@partner.org,")
    assert auth.support_entries() == ["sup@earthranger.com", "two@partner.org"]
    assert auth.is_support("SUP@earthranger.com") and auth.is_support("two@partner.org")
    assert not auth.is_support("other@earthranger.com") and not auth.is_support("")

def test_nobody_is_support_when_unset(monkeypatch):
    auth = _auth(monkeypatch)
    assert auth.support_entries() == [] and not auth.is_support("dev@earthranger.com")
```

(`_auth` is whatever helper `tests/test_auth.py` already uses to import `auth` under an environment; add one if it has none.)

- [ ] **Step 2: Write the failing route tests** in `tests/test_web_support.py`. The fixture is the one in `tests/test_web_sites.py` plus `monkeypatch.setenv("SUPPORT_EMAILS", "sup@earthranger.com")`. Three callers by header: the owner (no header, `dev@earthranger.com`), `SUP = {"X-Dev-User": "sup@earthranger.com"}`, `OTHER = {"X-Dev-User": "other@earthranger.com"}`. A helper `seed(app)` makes, owned by the owner: a dataset with `status="ready"`, `log_tail="extract log"` and one `export` entry; a site with token `"tok-secret-1234"`; a load of that dataset into that site with one stored file `plan.json`. Tests:

```python
def test_me_says_who_is_support(client): ...
    # /api/me: support True for SUP, False for OTHER and the owner

def test_all_lists_everything_for_support_only(client): ...
    # SUP  GET /api/datasets        -> []            GET /api/sites        -> []
    # SUP  GET /api/datasets?all=1  -> [the dataset], access == "support", mine is False
    # SUP  GET /api/sites?all=1     -> [the site], access == "support", "token_hint" value is None, "tok-secret" not in r.text
    # OTHER GET /api/datasets?all=1 -> 200, []       OTHER GET /api/sites?all=1 -> 200, []
    # owner GET /api/sites          -> token_hint == "1234", access == "owner"

def test_support_opens_every_read_route(client): ...
    # as SUP, each is 200: /api/datasets/{ds} (access "support", log_tail == "extract log"),
    # /api/datasets/{ds}/loads (each access "support"), /api/loads/{load} (access "support"),
    # /api/loads/{load}/files/plan.json, /d/{ds}/, /d/{ds}/index.html

def test_a_stranger_still_gets_404(client): ...
    # as OTHER, each route in the test above is 404

def test_support_keeps_owner_and_reader_rights(client): ...
    # SUP creates a dataset of their own: access "owner", and POST .../share succeeds
    # the owner shares the seeded dataset with sup@: access "shared" for SUP, and
    # SUP DELETE /api/loads/{load} is 200 (a reader may, as today)

def test_every_write_route_is_refused_through_support_view(client): ...
```

The last test is the guard. It walks `app.app.routes`, takes every `APIRoute` method other than `GET`, `HEAD` and `OPTIONS`, and requires each `(method, path)` to be a key of a table in the test. The table's value is either `"own"` (the route creates something of the caller's own or concerns only their session: `POST /api/session`, `POST /api/signout`, `POST /api/datasets`, `POST /api/sites`) or a function `(c, ids) -> response` that makes the call as SUP against the seeded dataset, site or load. Every such response must have status 404 or 403, and afterwards the seeded dataset, site and load are unchanged (compare the stored docs before and after, and `store.read_site_token(site) == "tok-secret-1234"`). A route missing from the table fails with a message naming it.

- [ ] **Step 3: Run them and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_auth.py tests/test_web_support.py`
Expected: FAIL (`support_entries` not defined; `access` missing)

- [ ] **Step 4: Implement** the interfaces above in `web/auth.py`, `web/store.py`, `web/app.py`. Update the route list in the docstring at the top of `web/app.py` (`?all=1`, and who may read).

- [ ] **Step 5: Run the whole Python suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, nothing skipped that was not skipped before (348 passed, 2 skipped before this change)

- [ ] **Step 6: Commit**

```bash
git add web/auth.py web/store.py web/app.py tests/test_auth.py tests/test_web_support.py
git commit -m "Support view: named support addresses can read every dataset, site and load"
```

---

### Task 2: The record

**Files:**
- Modify: `web/app.py`
- Test: `tests/test_web_support.py`

**Interfaces:**
- Consumes: `access(doc, user)` and `user["support"]` from Task 1
- Produces, `web/app.py`:
  - `SUPPORT_LOG_EVERY_SECONDS = 600`
  - `_record_view(user: dict, kind: str, id: str = "", owner: str = "")`: logs at INFO on the logger named `support`, `support_view viewer=%s kind=%s id=%s owner=%s`, unless the same `(viewer, kind, id)` was logged within `SUPPORT_LOG_EVERY_SECONDS` in this process. It keeps the times in a module dict keyed by that triple, read with `time.monotonic()`, and empties the dict when it passes 10,000 entries.

Where it is called, only when the viewer's access is `"support"`:

| Route | kind | id |
| --- | --- | --- |
| `get_dataset`, `list_loads` | `dataset` | dataset id |
| `get_load` | `load` | load id |
| `load_file` | `load_file` | `<load id>/<name>` |
| `site_index`, `site_file` | `browser` | dataset id |
| `list_datasets`, `list_sites` with `all` applied | `list` | `datasets` or `sites`, owner empty |

- [ ] **Step 1: Write the failing tests** (use `caplog.at_level("INFO", logger="support")`):

```python
def test_a_support_view_is_recorded_once_in_ten_minutes(client, caplog): ...
    # SUP GET /api/datasets/{ds} twice, then /api/datasets/{ds}/loads:
    #   exactly one record, "support_view viewer=sup@earthranger.com kind=dataset id=<ds> owner=dev@earthranger.com"
    # monkeypatch app.time.monotonic forward by 601 s, GET again: a second record

def test_the_record_covers_each_kind(client, caplog): ...
    # SUP: ?all=1 lists, a load, a load file, /d/{ds}/ then /d/{ds}/index.html
    #   kinds seen == {"list", "load", "load_file", "browser"}; browser logged once

def test_no_record_for_an_owner_or_a_reader(client, caplog): ...
    # the owner opens their dataset; SUP opens one shared with them; SUP opens their own: no records

def test_the_record_holds_no_token(client, caplog): ...
    # after every route above, "tok-secret" not in caplog.text
```

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_web_support.py -k record`
Expected: FAIL (no records)

- [ ] **Step 3: Implement `_record_view`** and its calls.

- [ ] **Step 4: Run the whole Python suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/app.py tests/test_web_support.py
git commit -m "Support view: each view of someone else's data is logged, once in ten minutes"
```

---

### Task 3: The pages and their words

**Files:**
- Modify: `web/static/pages.js`, `web/static/locales/{en,fr,es,pt,sw}.json`, `web/static/app.css`, `docs/translation-glossary.md`
- Test: `tests/js/home.test.js`, `tests/js/dataset.test.js`, `tests/js/loadpage.test.js`, `tests/js/sites.test.js`, `tests/js/pseudo.test.js`

**Interfaces:**
- Consumes: `access` on datasets, sites and loads; `token_hint` absent on a support-viewed site
- Produces, `web/static/pages.js`:
  - `renderHome(datasets, sites, sitesError, opts)`, `opts = { support: bool, all: bool }` (absent: neither). When `opts.support`, the page head holds `<label class="switch"><input type="checkbox" id="allUsers"> …</label>`, checked when `opts.all`.
  - `supportLine(owner)`: `<p class="support-line">…</p>` from the message `support.line`
  - `renderDatasetPage`, `renderLoadTitle`: draw `supportLine` under the title when `access === 'support'`
  - `renderLoadsTab`: no `#loadBtn` when `d.access === 'support'`
  - `renderLoadTitle`: no `data-run`, `data-replan` or `data-del` button when `l.access === 'support'`
  - `renderSites`: a row with no `token_hint` shows `sites.checkedAs` in place of `sites.tokenAs`

New messages (English; the other four languages are machine translated to match, and the glossary gains "support view" and "support staff" with the term each language uses):

| Key | English |
| --- | --- |
| `home.allUsers` | `All users` |
| `home.allUsersTitle` | `Show every user's datasets and sites (support view)` |
| `support.line` | `Support view: read-only. Owned by {{owner}}.` |
| `sites.checkedAs` | `Token checked as {{user}}` |

- [ ] **Step 1: Write the failing tests.** In each file, follow its existing way of loading `pages.js`:

```js
// home.test.js
test('only support sees the all-users switch', () => {
  assert.ok(!renderHome(DATASETS, SITES).includes('id="allUsers"'));
  assert.ok(!renderHome(DATASETS, SITES, null, { support: false, all: true }).includes('id="allUsers"'));
  assert.match(renderHome(DATASETS, SITES, null, { support: true, all: false }), /id="allUsers"(?![^>]*checked)/);
  assert.match(renderHome(DATASETS, SITES, null, { support: true, all: true }), /id="allUsers"[^>]*checked/);
});

// dataset.test.js: a ready dataset with a bundle, a present backup, access 'support', mine false
test('a dataset in support view draws the line and no controls', () => {
  for (const tab of ['overview', 'loads', 'backup']) {
    const html = renderDatasetPage(supportDs, tab, { loads: [] });
    assert.ok(html.includes('support-line') && html.includes('dev@earthranger.com'));
    for (const id of ['shareBtn', 'extractBtn', 'deleteBtn', 'deleteBackupBtn', 'loadBtn']) assert.ok(!html.includes('id="' + id + '"'), tab + ' ' + id);
  }
});
test('a failed dataset in support view still shows its error', () => { /* status failed, error set: error text present, support line present */ });

// loadpage.test.js: for each status in planned, needs_attention, failed, done, and a stale running one,
// and one with site: null
test('a load in support view has no run, plan-again or delete', () => {
  // html has support-line; no 'data-run', 'data-replan', 'data-del'
});
test('the same loads without support view keep their buttons', () => { /* access 'shared': data-del present */ });

// sites.test.js
test('a site seen through support view shows who the token is, not its hint, and no actions', () => {
  // { access: 'support', mine: false, checked_as: 'migration' } with no token_hint:
  // no 'undefined', no 'data-act=', includes 'migration'
});
```

In `tests/js/pseudo.test.js`, add fixtures for the new states: `renderHome` with `{ support: true, all: true }`, a support-view dataset on each tab, a support-view load, a support-view site.

- [ ] **Step 2: Run and see them fail**

Run: `node --test "tests/js/*.test.js"`
Expected: FAIL in the new tests; `locales.test.js` still passes

- [ ] **Step 3: Implement** the builders, add the four messages to all five files, the glossary rows, and styles for `.support-line` and `.switch` in `web/static/app.css` (beside the page-head styles; use the existing `--er-ui-*` tokens, no new colours).

- [ ] **Step 4: Run both suites**

Run: `node --test "tests/js/*.test.js"` then `.venv/bin/python -m pytest -q`
Expected: PASS (120 Node tests before this change, more now)

- [ ] **Step 5: Commit**

```bash
git add web/static/pages.js web/static/locales web/static/app.css docs/translation-glossary.md tests/js
git commit -m "Support view: the pages say so and draw no controls"
```

---

### Task 4: Wiring the switch

**Files:**
- Modify: `web/static/app.js`
- Test: by hand, locally (there is no browser harness for `app.js`)

**Interfaces:**
- Consumes: `ME.support` from `/api/me`; `renderHome(..., opts)` from Task 3
- Produces: the switch's state in `localStorage.allUsers` (`'1'` or absent), read and written inside try/catch like `localStorage.lang`

Behaviour:
- `showHome` and the home page's poll ask for `/api/datasets?all=1` and `/api/sites?all=1` when `ME.support` and the switch is on; otherwise the plain addresses.
- Changing `#allUsers` stores the choice and calls `showHome()`.
- The load dialog's `api('/api/sites')` stays plain.
- If `ME.support` is false, a stored `allUsers` is ignored.

- [ ] **Step 1: Implement** the above.

- [ ] **Step 2: Run both suites**

Run: `node --test "tests/js/*.test.js"` then `.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Walk it locally** with made-up data only (the seed and driver under `.superpowers/sdd/2026-11-17-language-support-app/walk/` can be reused). Start the service with `BACKEND=local AUTH_DISABLED=true SUPPORT_EMAILS=sup@earthranger.com` on `127.0.0.1:8090`. As `dev@earthranger.com` create a dataset, a site and a load. Then, with the `dev_user` cookie set to `sup@earthranger.com`, check and screenshot at 1280 px and 320 px:
  - home with the switch off: empty lists; on: the dataset and site, each with its owner; the choice survives a reload
  - the dataset's Overview, Loads and Backup tabs: the support line, no buttons
  - the load page: the support line, no buttons
  - the load dialog cannot be reached, and `POST /api/datasets/<id>/loads` as support answers 404
  - as `other@earthranger.com`: no switch
  - the service's output has one `support_view` line per item, not one per poll
  - the same pages in French: no English left in the new text

- [ ] **Step 4: Commit**

```bash
git add web/static/app.js
git commit -m "Support view: the all-users switch on the home page"
```

---

### Task 5: Telling people, and deploying it

**Files:**
- Modify: `web/help/01-overview.md`, `web/guide/01-before-you-start.md`, and the same pages under `fr/`, `es/`, `pt/`, `sw/`; `web/DEPLOY.md`; `.github/workflows/deploy.yml`
- Test: `tests/test_help.py`, `tests/test_pages_site.py` (existing shape checks); the site build

Two sentences today say nobody else sees your data. Each gains the exception, in the same paragraph, so the page's shape does not change:

- `web/help/01-overview.md`, the paragraph beginning "Everything you upload, extract and load is shared only with the people you share it with." Add after that sentence: `EarthRanger support staff can also view datasets and sites, to help with a migration; they cannot change them or load data.`
- `web/guide/01-before-you-start.md`, "Nobody else sees a dataset or a site until you share it with them." becomes: `Nobody else sees a dataset or a site until you share it with them, except EarthRanger support staff, who can view them to help with a migration but cannot change them or load data.`

`web/DEPLOY.md`:
- the repository variables table gains `SUPPORT_EMAILS`: whole addresses, separated by spaces; unset means nobody; who it should name (people who help users migrate, kept short); that a `@domain` entry is ignored
- a short section, "Support view": what support can open, that every write route refuses, that removing an address takes effect on the next deploy, and how to read the record (Cloud Logging, the service's log, the text `support_view`)
- "Data handling": the sentence on who can read a dataset's files now names support

`.github/workflows/deploy.yml`: add `SUPPORT_EMAILS=${{ vars.SUPPORT_EMAILS }}` beside `ALLOWED_EMAILS`.

- [ ] **Step 1: Make the edits**, all five languages of each page in this commit.

- [ ] **Step 2: Build the site and run the suites**

Run: `.venv/bin/python scripts/build_pages.py`, then `.venv/bin/python -m pytest -q`, then `node --test "tests/js/*.test.js"`
Expected: the build writes 40 pages with no shape error; both suites PASS

- [ ] **Step 3: Read each translated sentence back** against the English for meaning ("view" not "edit", "cannot load data"), and add any doubt to "Doubts for a reviewer" in `docs/translation-glossary.md`.

- [ ] **Step 4: Commit**

```bash
git add web/help web/guide web/DEPLOY.md .github/workflows/deploy.yml docs/translation-glossary.md
git commit -m "Support view: the help and guide say support staff can view; the deploy sets who they are"
```
