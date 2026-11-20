# Sidebar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One left sidebar replaces the top band, the breadcrumb line and the dataset's tabs in the app, and the top band and view list in the data browser, with the same entries in both.

**Architecture:** A new pure script, `web/static/nav.js`, holds the entries and builds the sidebar's HTML from a state object; `web/static/nav.css` styles it. The app loads both as files. The data browser, which must also open from a local folder, carries a copy of each between markers, written by a small script and checked by a test, as its design tokens are today. Each document supplies its own state and wires its own clicks.

**Tech Stack:** Plain JavaScript (no build step), CSS with the EarthRanger tokens, FastAPI/Jinja for the app's one template, pytest, `node --test`. Tests: `.venv/bin/python -m pytest -q` (404 passed, 2 skipped before this change), `node --test "tests/js/*.test.js"` (128).

**Spec:** `docs/superpowers/specs/2026-11-20-sidebar-navigation-design.md`

## Global Constraints

- Addresses do not change, in either document. The browser's first view keeps the id `overview` in its hash and in `TABS`; only its name becomes "Summary".
- The browser opens from a local folder (`file://`) and asks no server for anything there. There its sidebar is the Data group and the fold control only.
- The sidebar shows only what the page's own requests return; it never names a dataset, owner or address the reader may not see.
- From every page the list of datasets is one click away, except `quirks.html`, which keeps a plain band with a link back to the browser.
- The sidebar is a light surface with the colour logo (`web/static/img/er-lockup-h.svg`) and a pale highlight on the current entry; in the dark theme the dark surface and the white logo. Colours come from the tokens in `web/static/er-tokens.css`; `web/static/app.css` and `web/static/nav.css` hold no raw colour (`tests/test_static_assets.py` checks the first; extend it to the second).
- Fold state: `localStorage.sidenav`, values `open` and `closed`, read and written by both documents. Theme: `localStorage.theme`. Language: `localStorage.lang`. Support switch: `localStorage.allUsers`. Every storage access is in try/catch, as today.
- New and changed interface text goes in all five locale files (`en`, `fr`, `es`, `pt`, `sw`) and follows `docs/translation-glossary.md`. Help pages change in all five languages.
- No real conservation area's rangers, customer host or token in tests, docs, mockups or commits; `example.pamdas.org` only.
- The site token rule is untouched: nothing here reads or shows it.
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Do not push, tag or choose a version.

## Review Focus

1. **A dataset the reader can open but that is not ready** (extracting, failed). Data entries are shown and disabled, are not links, and the Migration entries follow `tabAllowed`. (Task 1)
2. **The browser's request for the sidebar's language fails**, or the stored language is one the app no longer has. The sidebar stays in English and the pages work. (Task 4)
3. **Storage blocked** (private window). The sidebar opens on a wide screen, folds for the page's life, and nothing throws. (Tasks 2 and 4)
4. **A long dataset name, and a name with markup in it.** It is escaped, does not widen the sidebar, and is cut with an ellipsis; folded, it does not show. (Task 1)
5. **Back and forward across the two documents** (app → browser view → app). Each address opens its page with its entry marked; a load's page marks Loads. (Tasks 2 and 4)

## File Structure

| File | Responsibility |
|---|---|
| `web/static/nav.js` (new) | The entries, their order and icons; `renderRail(state, label)`. No DOM, no storage, no i18n of its own |
| `web/static/nav.css` (new) | The sidebar's styles and the page layout beside it |
| `scripts/sync_nav.py` (new) | Writes the two files into `browse/index.html` between their markers |
| `web/templates/index.html`, `web/static/app.js`, `web/static/pages.js`, `web/static/app.css` | The app's shell: sidebar in place of band, breadcrumb and tabs; the sites page |
| `browse/index.html`, `browse/build_quirks.py` | The browser's shell; the notes page keeps a band |
| `web/static/locales/*.json`, `web/help/**`, `docs/decisions.md` | Text |

---

### Task 1: The sidebar, as a pure builder

**Files:**
- Create: `web/static/nav.js`, `web/static/nav.css`, `tests/js/nav.test.js`
- Modify: `web/static/locales/{en,fr,es,pt,sw}.json`, `tests/js/shim.js` (load `nav.js` after `i18n.js`), `tests/test_static_assets.py` (no raw colour in `nav.css`)

**Interfaces:**
- Produces, in `nav.js` (top-level `var`/`function`, so the test shim and both documents see them):
  - `NAV_DATA`: `[['overview','Summary','dashboard'],['patrols','Patrols','hiking'],['rangers','Rangers','groups'],['map','Map','map'],['observations','Observations','visibility'],['datamodel','Data model','account_tree'],['profiles','Profiles','badge'],['schema','Schema','schema']]` (id, English, icon).
  - `NAV_MIGRATION`: `[['loads','Loads',icon],['rangers','Match rangers',icon],['backup','Backup',icon]]`; the id is the app's tab name.
  - `renderRail(state, label) -> string`. `label(key, english) -> string` returns escaped text; the app passes `(k) => T(k)`, the browser its own lookup with the English as fallback.
  - `state`: `{ doc: 'app' | 'browser', hosted: bool, signedIn: bool, dataset: null | { id, name, ready: bool, loadTabs: bool }, current: 'home' | 'sites' | 'overview' | 'data:<id>' | 'migration:<id>' | null, lang: string, languages: [{code, name}], theme: 'system' | 'light' | 'dark', email: string, version: string }`.
  - Markup contract (ids both documents bind to): root `<nav id="rail">`; fold control `#railToggle`; entries are `<a>` with `data-nav="<current value>"`, the current one with `class="on"` and `aria-current="page"`; a disabled entry is `<span class="off" aria-disabled="true">`; the dataset's name in `.rail-dataset`; the conservation area slot `#railFilter` (empty; the browser moves its filter in); theme radios `name="theme"`; language `<select id="lang">`; `#helpBtn`; `#signOut`; the address in `#whoEmail`.
  - Links. In `doc: 'app'`: Datasets `#/`, Sites `#/sites`, Overview `#/datasets/{id}`, Migration `#/datasets/{id}/{tab}`, Data `/d/{id}/#{view}`. In `doc: 'browser'`: Data entries are `<a href="#{view}">`; Datasets `/#/`; Overview and Migration `/#/datasets/{id}...`.
  - What is shown: no dataset → Datasets, Sites; a dataset → "‹ Datasets", the name, Overview, Data, Migration (no Sites). `hosted: false` → Data group and `#railToggle` only. `signedIn: false` → Theme and Language only. The Data heading carries `label('dataset.browseInEnglish', 'in English')` when `lang !== 'en'`.
- Message keys (English): `nav.datasets` "Datasets", `nav.sites` "Sites", `nav.overview` "Overview", `nav.data` "Data", `nav.migration` "Migration", `nav.fold` "Collapse the list", `nav.unfold` "Open the list", `nav.account` "Account", `nav.view.overview` "Summary", `nav.view.patrols`, `nav.view.rangers`, `nav.view.map`, `nav.view.observations`, `nav.view.datamodel`, `nav.view.profiles`, `nav.view.schema`, `nav.loads` "Loads", `nav.matchRangers` "Match rangers", `nav.backup` "Backup". `rangers.title` becomes "Match rangers" in every language (it heads that page).

- [ ] **Step 1: Write the failing tests** in `tests/js/nav.test.js`, with `const P = load(); const L = (k, en) => P.T(k);` and a helper `rail(over)` that fills a full state:

```js
test('outside a dataset the rail lists datasets and sites', () => {
  const h = rail({ current: 'home', dataset: null });
  assert.match(h, /<a[^>]*href="#\/"[^>]*class="on"[^>]*aria-current="page"/); assert.match(h, /href="#\/sites"/);
  assert.doesNotMatch(h, /rail-dataset/);
});
test('inside a dataset it shows that dataset in two groups, and no sites', () => {
  const h = rail({ current: 'migration:loads', dataset: { id: 'a1', name: 'Area', ready: true, loadTabs: true } });
  const order = ['Datasets', 'Overview', 'Data', 'Summary', 'Patrols', 'Rangers', 'Map', 'Observations', 'Data model', 'Profiles', 'Schema', 'Migration', 'Loads', 'Match rangers', 'Backup'];
  let at = -1; for (const w of order) { const i = h.indexOf('>' + w, at + 1); assert.ok(i > at, w); at = i; }
  assert.match(h, /href="\/d\/a1\/#patrols"/); assert.match(h, /href="#\/datasets\/a1\/loads"[^>]*class="on"/);
  assert.doesNotMatch(h, /#\/sites/);
});
test('a dataset that is not ready has its data entries off, not linked', () => {
  const h = rail({ current: 'overview', dataset: { id: 'a1', name: 'Area', ready: false, loadTabs: false } });
  assert.doesNotMatch(h, /href="\/d\/a1\//); assert.equal((h.match(/class="off" aria-disabled="true"/g) || []).length, 8 + 2);   // eight views, Loads and Match rangers
  assert.match(h, /href="#\/datasets\/a1\/backup"/);
});
test('the name is escaped', () => { assert.match(rail({ dataset: { id: 'a1', name: 'R5 <b>', ready: true, loadTabs: true } }), /R5 &lt;b&gt;/); });
test('the browser links back to the app, and its views are its own', () => {
  const h = rail({ doc: 'browser', current: 'data:map', dataset: { id: 'a1', name: 'Area', ready: true, loadTabs: true } });
  assert.match(h, /href="\/#\/"/); assert.match(h, /href="\/#\/datasets\/a1\/loads"/); assert.match(h, /href="#map"[^>]*class="on"/);
});
test('from a folder there is only the data group and the fold control', () => {
  const h = rail({ doc: 'browser', hosted: false, signedIn: false, dataset: null, current: 'data:overview' });
  assert.match(h, /id="railToggle"/); assert.match(h, /href="#patrols"/);
  for (const no of ['/#/', 'id="lang"', 'id="helpBtn"', 'id="signOut"', 'name="theme"', 'Migration']) assert.ok(!h.includes(no), no);
});
test('signed out, only theme and language', () => {
  const h = rail({ signedIn: false, dataset: null, current: null });
  assert.match(h, /name="theme"/); assert.match(h, /id="lang"/); assert.doesNotMatch(h, /href="#\/"|id="signOut"|id="helpBtn"/);
});
test('another language says the data pages are in English', () => {
  assert.match(rail({ lang: 'fr', dataset: { id: 'a1', name: 'A', ready: true, loadTabs: true } }), /in English/);
  assert.doesNotMatch(rail({ lang: 'en', dataset: { id: 'a1', name: 'A', ready: true, loadTabs: true } }), /in English/);
});
test('the browser view ids are the browser\'s', () => { assert.deepEqual(P.NAV_DATA.map(e => e[0]), ['overview', 'patrols', 'rangers', 'map', 'observations', 'datamodel', 'profiles', 'schema']); });
```

- [ ] **Step 2: Run and see them fail**

Run: `node --test tests/js/nav.test.js`
Expected: FAIL (`P.renderRail is not a function`)

- [ ] **Step 3: Implement** `nav.js`, `nav.css` (sidebar 220px open, 52px folded; `html[data-nav="closed"]` hides labels, the dataset's name, group headings and the filter; under 700px the open sidebar lies over the page with a scrim; the name cut with an ellipsis), and the message keys in five languages.

- [ ] **Step 4: Run both suites**

Run: `node --test "tests/js/*.test.js" && .venv/bin/python -m pytest -q tests/test_static_assets.py tests/test_web_i18n.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/static/nav.js web/static/nav.css web/static/locales tests
git commit -m "Navigation: the sidebar's entries and markup, as one pure builder"
```

---

### Task 2: The app wears the sidebar

**Files:**
- Modify: `web/templates/index.html` (the `<header>` and `#crumbs` go; `<nav id="rail">` beside `<main id="page">`; `nav.css`, `nav.js` loaded with the asset versions; the pre-paint script also sets `data-nav`), `web/static/app.js` (`mountHeader`, `setBreadcrumb` and their callers; theme, language, help, sign-out bindings), `web/static/pages.js` (`renderTabs`, `renderBreadcrumb`, `renderDatasetPage`, `renderSignIn`), `web/static/app.css`, `web/app.py` (the `assets` map, if it lists files by name)
- Test: `tests/js/shell.test.js`, `tests/js/dataset.test.js`, `tests/js/router.test.js`, `tests/test_static_assets.py`

**Interfaces:**
- Consumes: `renderRail(state, label)` and the markup contract of Task 1.
- Produces, in `pages.js`: `railState(route, me, extra) -> state` (pure; `extra`: `{ dataset, lang, languages, theme, version }`), mapping route to `current`: home → `'home'`, sites → `'sites'`, dataset tab `overview` → `'overview'`, `loads`/`rangers`/`backup` → `'migration:<tab>'`, load → `'migration:loads'`; `dataset.ready` is `d.status === 'ready'`, `dataset.loadTabs` is `hasLoadTabs(d)`. `renderTabs` and `renderBreadcrumb` are removed.
- Produces, in `app.js`: `setRail(route, extra)` draws `#rail` and binds it; it replaces every `mountHeader` and `setBreadcrumb` call. While a dataset or load is being fetched the rail shows the no-dataset form; a 404 or refused dataset leaves it so.
- The `<title>`, the machine-translation note above the content, the help drawer and the modal are unchanged.

- [ ] **Step 1: Write the failing tests.** `shell.test.js`: `railState` for each route (home, sites, each of the four dataset tabs, a load) gives the `current` above; a dataset with `status: 'extracting'` gives `ready: false`; signed out gives `signedIn: false`. Replace the breadcrumb test. `dataset.test.js`: `renderDatasetPage` output has no `class="tabs"` and still has the page head and the tab's body. `router.test.js`: every address in the spec's list parses as before. `tests/test_static_assets.py`: the served page has `id="rail"`, no `<header`, no `id="crumbs"`, and loads `/static/nav.js` and `/static/nav.css`. Also there: neither `nav.js` nor `pages.js` contains `localStorage` (the builders take the theme, language and fold state as arguments, so blocked storage cannot throw in them), and a long name: `railState` passes the name whole and `nav.css` has `text-overflow: ellipsis` on `.rail-dataset`.

- [ ] **Step 2: Run and see them fail**

Run: `node --test "tests/js/*.test.js"`
Expected: FAIL (`P.railState is not a function`)

- [ ] **Step 3: Implement.** A click on the fold control toggles `data-nav` on `<html>` and stores it; on a narrow screen a click on an entry folds the rail. The account menu's contents (address, sign out, version) sit at the foot of the rail.

- [ ] **Step 4: Run every suite, then look at it**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js"`
Expected: PASS
Then run the app as `web/DEPLOY.md`, "Running locally", says (127.0.0.1:8090, never 8080) and open home, a dataset on each entry, and a load, in light and dark, wide and at 390px. Expected: the rail on every page, the current entry marked, Back and Forward working, no top band.

- [ ] **Step 5: Commit**

```bash
git add web tests
git commit -m "App: a sidebar in place of the top band, the breadcrumb and the dataset's tabs"
```

---

### Task 3: Sites is a page of its own

**Files:**
- Modify: `web/static/app.js` (`renderRoute`, `showHome`, a new `showSites`, the callers that redraw after a site changes), `web/static/pages.js` (`renderHome` without the sites; `renderSitesPage(sites, error, opts)`), `web/static/locales/*.json` (only if a heading changes)
- Test: `tests/js/home.test.js`, `tests/js/sites.test.js`

**Interfaces:**
- Consumes: `setRail` (Task 2).
- Produces: `renderHome(datasets, opts)` (datasets only); `renderSitesPage(sites, sitesError, opts) -> string`, `opts`: `{ support, all }`, with the support switch (`#allUsers`) when `opts.support`, as home has. `showSites()` fetches `/api/sites` + `listQuery()`. `#/sites` opens it. A site added, edited, shared or removed redraws the page the reader is on.

- [ ] **Step 1: Write the failing tests.** `home.test.js`: `renderHome` output has no `id="sites"`. `sites.test.js`: `renderSitesPage` has the sites table; with `{ support: true, all: true }` it has `id="allUsers"` checked; with `support: false` it has none; with an error it shows the error and no table.

- [ ] **Step 2: Run and see them fail**

Run: `node --test tests/js/home.test.js tests/js/sites.test.js`
Expected: FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run both suites**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web tests
git commit -m "Sites: a page of their own, opened from the sidebar"
```

---

### Task 4: The data browser wears the same sidebar

**Files:**
- Create: `scripts/sync_nav.py`
- Modify: `browse/index.html` (the `<header>`, `#sidenav`, `buildHeader`, `hostedHeader`, `setNav`, the Summary view), `browse/build_quirks.py`, `web/app.py` (only if the browser needs a file it cannot yet fetch)
- Test: `tests/test_viewer_page.py`, `tests/test_quirks.py`, `tests/js/nav.test.js`

**Interfaces:**
- Consumes: `nav.js`, `nav.css` (Task 1), verbatim.
- Produces: in `browse/index.html`, the two files between the markers `/* nav.css:begin */ … /* nav.css:end */` (in a `<style>`) and `/* nav.js:begin */ … /* nav.js:end */` (in a `<script>`). `scripts/sync_nav.py` rewrites both from `web/static/`; `scripts/sync_nav.py --check` exits 1 when they differ.
- The browser's state: `doc: 'browser'`; `hosted` is whether the path matches `/^\/d\/([A-Za-z0-9]+)\//`; `current: 'data:' + TAB`, redrawn in `render()`. Hosted, it asks `/api/datasets/{id}` (name, status, `export`, as `hostedHeader` does today), `/api/me` (address), `/static/locales/languages.json`, `/static/i18n.js` and `/static/locales/{lang}.json` for `localStorage.lang`; any of these failing leaves English and whatever it has. Until they answer it shows the Data group.
- The conservation area filter (`#caSel`, `#caIcon`) moves into `#railFilter`. The Data entries keep the click behaviour the buttons have (`go(null, id)`, folding on a narrow screen).
- Sign out: `POST /api/signout`, then `location.href = '/'`. Help: a link to `/#/` opened in a new tab is acceptable. Language: stores `localStorage.lang` and redraws the sidebar.
- "SMART database {version}" (`#dbver`) moves to the head of the Summary view. The view's heading reads "Summary".
- `quirks.html` keeps a band: `build_quirks.py` no longer reads a band from `browse/index.html`; it takes the tokens from the same place as before and the white lockup from `web/static/img/er-lockup-white-h-short.svg`, inlined.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_viewer_page.py
def test_the_viewer_carries_the_apps_sidebar_verbatim():
    html = (ROOT / "browse" / "index.html").read_text()
    for name in ("nav.js", "nav.css"):
        src = (ROOT / "web" / "static" / name).read_text()
        body = html.split(f"/* {name}:begin */", 1)[1].split(f"/* {name}:end */", 1)[0]
        assert body.strip() == src.strip(), name

def test_the_viewer_has_no_band_and_no_list_of_its_own():
    html = (ROOT / "browse" / "index.html").read_text()
    assert "<header" not in html and 'id="sidenav"' not in html and "Back to dataset" not in html
    assert 'id="rail"' in html or "renderRail(" in html

def test_from_a_folder_the_viewer_asks_no_server():
    # every fetch of /api/ or /static/ in the document sits behind the hosted check:
    # assert the text has one function that makes them and that it returns first when the path is not /d/{id}/
```

Replace `test_the_viewer_lists_its_views_down_the_left_side` with the first two. In `tests/test_quirks.py`, `test_quirks_page_wears_the_app_theme` asserts the tokens and a lockup as before, from the new sources. In `tests/js/nav.test.js`, load the script between the `nav.js` markers of `browse/index.html` in a bare VM context and assert `renderRail` gives the same string as the file's for the folder state and a hosted dataset state.

- [ ] **Step 2: Run and see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_viewer_page.py tests/test_quirks.py`
Expected: FAIL (no marker in the document)

- [ ] **Step 3: Implement**, then run `scripts/sync_nav.py`.

- [ ] **Step 4: Run every suite, then look at it**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js" && .venv/bin/python scripts/sync_nav.py --check`
Expected: PASS, exit 0
Then, with the app running locally: open a dataset's Patrols from the app's rail, go to Loads from the browser's rail, use Back twice; switch the language to French in the browser and see the sidebar change and the app follow; fold the rail in one and see it folded in the other. Open `work/site/index.html` (after `./smart-able browse`, if a `work/parquet` exists) from the folder: only the Data group and the fold control, and no failed request in the browser's network panel. Open `quirks.html`: a band, and a link back. With the browser's developer tools, block `/static/locales/*` and reload a hosted view: the sidebar is in English and the page works. In a private window with storage blocked: the rail folds and opens, and nothing is reported in the console.

- [ ] **Step 5: Commit**

```bash
git add browse scripts/sync_nav.py tests web
git commit -m "Data browser: the app's sidebar in place of its band and its list of views"
```

---

### Task 5: Say so

**Files:**
- Modify: `web/help/*.md` and the `es`, `fr`, `pt`, `sw` copies (every place that names the tabs, the breadcrumb, "Back to dataset", the Rangers tab, or sites on the home page), `web/guide/` and `web/site/` only where they name the same, `docs/decisions.md`, `web/DEPLOY.md` if it describes the shell
- Test: `tests/test_help.py`, `tests/test_pages_site.py` (existing)

- [ ] **Step 1: Find every mention**

Run: `grep -rn -i "tab\b\|tabs\|breadcrumb\|back to dataset\|rangers tab" web/help web/guide web/site docs/*.md | grep -v superpowers`
Expected: a list; each line is changed or left on purpose.

- [ ] **Step 2: Rewrite them** to name the sidebar's entries as the interface does ("Match rangers", "Loads" under Migration, "Sites"), in five languages, code spans unchanged across languages.

- [ ] **Step 3: `docs/decisions.md`**, in that file's style: the decision (one sidebar, the dataset in two groups); the two rejected approaches and the rejected arrangement, from the spec; that the browser stays its own document and carries a checked copy; that `quirks.html` keeps a band; reopen if the copy drifts or the page load between Data and Migration is felt.

- [ ] **Step 4: Run everything and build the site**

Run: `.venv/bin/python -m pytest -q && node --test "tests/js/*.test.js" && .venv/bin/python scripts/build_pages.py --out /tmp/sidebar-site`
Expected: PASS; the help pages build in five languages

- [ ] **Step 5: Commit**

```bash
git add web/help web/guide web/site docs
git commit -m "Help and decisions: the sidebar"
```
